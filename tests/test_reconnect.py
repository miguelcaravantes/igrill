"""Exercise the production connection class without installing Home Assistant."""

import ast
import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock


class BluetoothData:
    def _finish_update(self):
        return None


def load_peripheral():
    source = Path(__file__).parents[1] / "custom_components/igrill_ble/igrill.py"
    tree = ast.parse(source.read_text())
    tree.body = [ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)] + [
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name in {"UUIDS", "IDevicePeripheral"}
    ]
    namespace = {
        "asyncio": asyncio,
        "BluetoothData": BluetoothData,
        "BleakClient": object,
        "callback": lambda function: function,
        "_LOGGER": logging.getLogger("test_igrill"),
        "RECONNECT_INTERVAL": 30,
        "MAX_RECONNECT_INTERVAL": 300,
        "async_call_later": Mock(),
        "establish_connection": AsyncMock(),
    }
    exec(compile(ast.fix_missing_locations(tree), str(source), "exec"), namespace)
    return namespace


class ReconnectTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.namespace = load_peripheral()
        self.device = self.namespace["IDevicePeripheral"]("iGrill Mini", 0, has_battery=False)
        self.device._hass = Mock()
        self.device.retrieved_device_info = True
        self.ble_device = SimpleNamespace(name="iGrill Mini", address="70:91:8F:98:E6:8F")
        self.device._last_ble_device = self.ble_device
        self.client = SimpleNamespace(
            is_connected=True,
            pair=AsyncMock(),
            write_gatt_char=AsyncMock(),
            read_gatt_char=AsyncMock(return_value=bytes(16)),
            disconnect=AsyncMock(),
            services=SimpleNamespace(get_characteristic=Mock(return_value=None)),
        )
        self.namespace["establish_connection"].return_value = self.client
        self.namespace["async_call_later"].return_value = Mock()

    async def test_timer_reconnect_reaches_connection_and_authentication(self):
        await self.device._reconnect()
        self.namespace["establish_connection"].assert_awaited_once()
        self.assertEqual(self.client.write_gatt_char.await_count, 2)
        self.assertEqual(self.device._reconnect_attempts, 0)
        self.assertFalse(self.device._connecting)
        self.namespace["async_call_later"].assert_not_called()

    async def test_failed_connection_schedules_retry_after_releasing_guard(self):
        self.namespace["establish_connection"].side_effect = TimeoutError("timeout")
        await self.device.async_init(self.ble_device)
        self.assertFalse(self.device._connecting)
        self.assertEqual(self.device._reconnect_attempts, 1)
        timer = self.namespace["async_call_later"]
        self.assertEqual(timer.call_args.args[1], 60)
        self.assertIsNotNone(self.device._reconnect_cancel)
        timer.call_args.args[2](None)
        reconnect = self.device._hass.async_create_task.call_args.args[0]
        await reconnect
        self.assertEqual(self.namespace["establish_connection"].await_count, 2)
        self.assertEqual(self.device._reconnect_attempts, 2)
        self.assertEqual(timer.call_args.args[1], 120)

    async def test_pairing_disconnect_does_not_authenticate_missing_client(self):
        async def disconnect_during_pair(**kwargs):
            self.device._on_disconnect(self.client)
            raise ConnectionResetError("connection reset")

        self.client.pair.side_effect = disconnect_during_pair
        await self.device.async_init(self.ble_device)
        self.client.write_gatt_char.assert_not_awaited()
        self.assertIsNone(self.device.client)
        self.namespace["async_call_later"].assert_called_once()

    async def test_pairing_error_can_continue_if_connection_is_alive(self):
        self.client.pair.side_effect = NotImplementedError("pairing unsupported")
        await self.device.async_init(self.ble_device)
        self.assertEqual(self.client.write_gatt_char.await_count, 2)
        self.namespace["async_call_later"].assert_not_called()

    async def test_authentication_failure_disconnects_and_retries(self):
        self.client.write_gatt_char.side_effect = ConnectionError("authentication failed")
        await self.device.async_init(self.ble_device)
        self.client.disconnect.assert_awaited_once()
        self.assertIsNone(self.device.client)
        self.namespace["async_call_later"].assert_called_once()

    async def test_concurrent_attempt_does_not_connect_twice(self):
        started = asyncio.Event()
        release = asyncio.Event()

        async def connect(*args, **kwargs):
            started.set()
            await release.wait()
            return self.client

        self.namespace["establish_connection"].side_effect = connect
        task = asyncio.create_task(self.device.async_init(self.ble_device))
        await started.wait()
        await self.device.async_init(self.ble_device)
        release.set()
        await task
        self.namespace["establish_connection"].assert_awaited_once()

    async def test_close_cancels_pending_retry(self):
        self.namespace["establish_connection"].side_effect = TimeoutError("timeout")
        await self.device.async_init(self.ble_device)
        cancel = self.device._reconnect_cancel
        await self.device.close()
        cancel.assert_called_once()
        await self.device._reconnect()
        self.namespace["establish_connection"].assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
