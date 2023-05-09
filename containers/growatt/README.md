# Growatt to MQTT/Sparkplug B

This project is a Node.js utility that loads telemetry data from a Growatt inverter and stores it in an MQTT broker using the [Sparkplug B](https://www.ignitionplatform.com/resources/white-papers/understanding-ignitions-mqtt-data-protocol-sparkplug) protocol.

## Prerequisites

- Node.js v12 or higher
- An MQTT broker that supports the Sparkplug B protocol (tested with EMQX and HiveMQ)
- Access to the telemetry data from a Growatt inverter

## Installation

1. Clone this repository and navigate to the project directory
2. Install the dependencies:

```
npm install
```

## Configuration

1. Rename the .env.example file to .env.
2. Open the .env file and set the following variables:

`GROWATT_USER`: The username to use when accessing the Growatt inverter.
`GROWATT_PASSWORD`: The password to use when accessing the Growatt inverter.
`GROWATT_PLANT_ID`: Your plant identification number to use (integer).
`MQTT_HOST`: The hostname of the MQTT broker.
`MQTT_PORT`: The port of your MQTT broker (optional, default is 1883).
`MQTT_USER`: The username to use when connecting to the MQTT broker (optional).
`MQTT_PASSWORD`: The password to use when connecting to the MQTT broker (optional).

## Usage

To start the utility, run the following command:

```
node growatt.js
```

The telemetry data will be published to the MQTT broker at the growatt/telemetry topic.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
