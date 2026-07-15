# Nymea HEM Integration for Home Assistant

## Overview

This custom integration allows Home Assistant to interface with Nymea devices, fetching information about all connected devices (things) and their states. The integration automatically discovers sensors for each state of a device and displays their values.

**Note**: This integration was developed and tested using a **Consolinno Leaflet HEMS** running the Nymea system. While it may work with other Nymea servers, full compatibility cannot be guaranteed.

## Features

- **Automatic Discovery**: Fetches all devices and their states via `Integrations.GetThings`.
- **Home Assistant Device Hierarchy**: Represents the Nymea server and its connected things as Home Assistant devices.
- **Dynamic Sensor Creation**: Creates sensors dynamically based on device states.
- **Unit Conversion**: Maps Nymea units to Home Assistant standard units.
- **Device and State Classes**: Assigns appropriate Home Assistant metadata for history, statistics, and dashboard use.
- **Energy Dashboard Support**: Makes compatible energy sensors available to the Home Assistant Energy dashboard.
- **Server Information**: Exposes Nymea server version and metadata.
- **Continuous Polling**: Updates sensor states at the configured polling interval.
- **Connection Recovery**: Adds connection checks, timeouts, re-authentication, and improved error handling.

## Requirements

- A running instance of Home Assistant.
- A Consolinno Leaflet HEMS, or another accessible Nymea server.
- Valid credentials for your Nymea setup.

## Installation

1. Download or clone this repository into your Home Assistant `custom_components` directory.
2. Restart Home Assistant through **Settings > System > Restart**.
3. Add **Nymea HEM Integration** through **Settings > Devices & Services > Add Integration**.

## Configuration

Provide the following details when adding the integration:

- **Host**: IP address or hostname of your Nymea server.
- **Port**: Typically `2222`.
- **Username**: Nymea username.
- **Password**: Nymea password.
- **SSL**: Whether to use an encrypted connection.
- **Polling interval**: Defaults to `60 seconds`.

Sensors are created for the states exposed by each Nymea thing. Units are mapped from Nymea values to Home Assistant units, for example `UnitWatt` to `W`.

## Debugging

Enable debug logging in Home Assistant:

```yaml
logger:
  default: warning
  logs:
    custom_components.nymea_hem: debug
    custom_components.nymea_hem.sensor: debug
    custom_components.nymea_hem.nymea_client: debug
```

Logs can help identify connection, authentication, polling, and device-state mapping problems.

## Troubleshooting

### Invalid handler

- Ensure all integration files are in the correct directory.
- Restart Home Assistant after installation or updates.

### Authentication errors

- Verify the Nymea username and password.
- Confirm that the configured SSL setting and port match the Nymea server.

### Missing sensors

- Check the Home Assistant logs for errors involving `get_thing_class_details` or `get_things`.
- Reload the integration after Nymea devices or state definitions have changed.

### Testing the connection

Run the following Python script from the integration directory to verify Nymea connectivity:

```python
import asyncio

from nymea_client import NymeaClient


async def test_connection():
    client = NymeaClient("HOST", 2222, "USERNAME", "PASSWORD")
    await client.authenticate()
    things = await client.get_things()
    print(things)
    await client.close_connection()


asyncio.run(test_connection())
```

Replace `HOST`, `USERNAME`, and `PASSWORD` with your Nymea server details.

## Contributing

Feedback and contributions are welcome. Please open an issue or submit a pull request for changes and feature requests.

Special thanks to [@fischit87](https://github.com/fischit87) for the substantial device-model, sensor-classification, energy-dashboard, and connection-resilience improvements included in version 1.1.0.

## Release Notes

### 1.1.0 — 2026-07-15

Community release incorporating the contributions from [@fischit87](https://github.com/fischit87) in pull request #6.

- Added a Home Assistant device hierarchy for the Nymea server and connected things.
- Added Nymea thing-class discovery and richer entity metadata.
- Added unit mapping, device-class inference, and state classes for statistics and history.
- Added support for compatible sensors in the Home Assistant Energy dashboard.
- Added protection against classifying datetime and non-numeric states as electrical measurements.
- Added a server information sensor with Nymea version and server metadata.
- Improved connection-state checks, timeouts, re-authentication, retry handling, and cleanup on unload.
- Improved handling of long and structured state values.
- Added the repository MIT license file.

### 1.0.3

- Fixed polling updates for existing entities by reading live state data from coordinator refreshes.
- Fixed `InvalidStateError` for oversized state values caused by Home Assistant's 255-character state limit.
- Exposed large and complex values in sensor attributes through `value_payload` instead of the entity state.

## License

This project is licensed under the [MIT License](LICENSE).
