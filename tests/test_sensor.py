"""Check sensor metadata against the keyword-only, non-union DeviceInfo API."""

import ast
from collections import namedtuple
from pathlib import Path
from types import SimpleNamespace
import unittest


class DeviceInfo(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __or__(self, other):
        raise TypeError("DeviceInfo does not support unions")


class SensorTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).parents[1] / "custom_components/igrill_ble/sensor.py"
        tree = ast.parse(source.read_text())
        tree.body = [ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)] + [
            node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))
            and node.name in {"sensor_device_info_to_hass", "IGrillSensorEntity"}
        ]
        self.namespace = {
            "DeviceInfo": DeviceInfo,
            "SensorEntity": object,
            "DOMAIN": "igrill_ble",
            **{f"ATTR_{key.upper()}": key for key in [
                "name", "manufacturer", "model", "sw_version", "hw_version", "identifiers"
            ]},
            "sensor_update_to_bluetooth_data_update": lambda update: update,
        }
        exec(compile(ast.fix_missing_locations(tree), str(source), "exec"), self.namespace)

    def test_device_metadata_uses_keyword_only_constructor(self):
        info = SimpleNamespace(name="iGrill", manufacturer="Weber", model="Mini", sw_version=None, hw_version=None)
        self.assertEqual(self.namespace["sensor_device_info_to_hass"](info), {
            "name": "iGrill", "manufacturer": "Weber", "model": "Mini"
        })

    def test_entity_metadata_preserves_names_and_identifiers(self):
        for device_id, devices in [(None, {}), ("probe", {"probe": DeviceInfo(manufacturer="Weber")})]:
            with self.subTest(device_id=device_id):
                entity_key = namedtuple("EntityKey", ["key", "device_id"])("probe_1", device_id)
                update = SimpleNamespace(devices=devices, entity_names={}, entity_data={entity_key: 25})
                data = SimpleNamespace(address="AA:BB", bt_name="iGrill Mini")
                entity = self.namespace["IGrillSensorEntity"](entity_key, object(), data, update)
                suffix = "-probe" if device_id else ""
                self.assertEqual(entity._attr_device_info["identifiers"], {("igrill_ble", f"AA:BB{suffix}")})
                self.assertEqual(entity._attr_device_info["name"], "iGrill Mini")
                if device_id:
                    self.assertEqual(entity._attr_device_info["manufacturer"], "Weber")
                self.assertEqual(entity.native_value, 25)


if __name__ == "__main__":
    unittest.main()
