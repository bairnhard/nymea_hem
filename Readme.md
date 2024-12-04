# Nymea HEM Integration for Home Assistant

## Overview

This custom integration allows Home Assistant to interface with Nymea devices, fetching information about all connected devices (things) and their states. The integration automatically discovers sensors for each state of a device and displays their values.

**Note**: This integration was developed and tested using a **Consolinno Leaflet HEMS** running the Nymea system. While it may work with other Nymea servers, full compatibility cannot be guaranteed.

## Features

- **Automatic Discovery**: Fetch all devices and their states via `Integrations.GetThings`.
- **Dynamic Sensor Creation**: Creates sensors dynamically based on device states.
- **Unit Conversion**: Maps Nymea units to Home Assistant's standard units.
- **Device Classes**: Assigns device classes for improved Home Assistant integration.
- **Continuous Polling**: Updates sensor states at the configured polling interval.

## Requirements

- A running instance of Home Assistant.
- A Consolinno Leaflet HEMS (or other Nymea server) accessible on your local network.
- Valid credentials for your Nymea setup.

## Installation

1. **Download**: Download or clone this repository to your Home Assistant `custom_components` directory:

2. **Install Dependencies**:
   - No external dependencies are required; the integration uses the default Python libraries.

3. **Restart Home Assistant**: Navigate to **Settings > System > Restart** to load the integration.

## Configuration

1. **Add the Integration**:
   - Navigate to **Settings > Devices & Services > Add Integration**.
   - Search for **Nymea HEM Integration**.
   - Provide the following details:
     - **Host**: IP address of your Nymea server.
     - **Port**: Typically `2222`.
     - **Username**: Nymea username.
     - **Password**: Nymea password.

2. **Customize Polling Interval**:
   - The default polling interval is `30 seconds`. You can modify this in the integration options.

3. **Sensors and Units**:
   - Sensors are dynamically created for each state of a Nymea device.
   - Units are mapped from Nymea's system to Home Assistant's units (e.g., `UnitWatt` to `W`).

## Debugging

### Enable debug logs for detailed information

`yaml

logger:
  default: warning
  logs:
    custom_components.nymea_hem: debug
    custom_components.nymea_hem.sensor: debug
    custom_components.nymea_hem.nymea_client: debug
`

### Logs

Logs can help identify:

- **Connection issues**.
- **Errors in device state mapping**.
- **Issues with authentication or polling**.

## Known Issues

- Sensors may show `units` instead of `native_unit_of_measurement` in some versions of Home Assistant. This does not affect functionality.
- Ensure that your Nymea devices are reachable and properly configured to avoid errors during data fetching.

---

## Troubleshooting

### Common Errors

1. **Invalid Handler**  
   - Ensure all files are in the correct directory and correctly named.  
   - Restart Home Assistant after installation.

2. **Authentication Errors**  
   - Double-check your Nymea credentials in the integration settings.

3. **Missing Sensors**  
   - Check the Home Assistant logs for errors related to `get_thing_class_details` or `get_things`.

---

### Testing the Connection

Run the following Python script to verify Nymea connectivity:

`python
from nymea_client import NymeaClient
import asyncio

async def test_connection():
    client = NymeaClient("HOST", 2222, "USERNAME", "PASSWORD")
    await client.authenticate()
    things = await client.get_things()
    print(things)

asyncio.run(test_connection())

`

Replace HOST, USERNAME, and PASSWORD with your Nymea server details.

## Contributing

I love feedback and contributions to improve this integration.
Please open an issue or submit a pull request for any changes or feature requests.

## License

This project is licensed under the MIT License
