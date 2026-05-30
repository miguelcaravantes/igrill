# Weber iGrill BLE Integration for Home Assistant

> **Fork Notice:** This is a maintained fork of the original [sanjay900/igrill](https://github.com/sanjay900/igrill) integration, which is no longer actively maintained and does not work with current versions of Home Assistant. This fork adds compatibility fixes, auto-reconnection, and error handling for modern HA versions.

## Tested Devices

This fork has been tested with:
- **iGrill Mini**

Other devices from the original integration may work but have not been verified.

## Installation

1. Copy the `custom_components/igrill_ble` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Add the integration via the UI (Settings → Devices & Services → Add Integration → Weber iGrill BLE)

## Changes from Original

- Added automatic reconnection with exponential backoff when BLE disconnects
- Added comprehensive error handling for all GATT operations
- Fixed missing `await` on heating element characteristic read
- Added connection lock to prevent concurrent connection attempts
- Improved logging for debugging connection issues
- Compatible with Home Assistant 2024.x+

## Troubleshooting

If pairing fails, try:
```bash
bluetoothctl
scan on
pair <mac address>
```

If things get stuck, restarting the bluetooth service can help:
```bash
systemctl restart bluetooth
```

## Original Note

It has been noted that the following can help with pairing in some cases:
> Open up a terminal, run bluetoothctl, scan on, pair <<mac address>>

If things ever get stuck, `systemctl restart bluetooth` can help as well.
