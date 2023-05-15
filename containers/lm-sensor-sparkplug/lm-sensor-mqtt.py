import os
import time

from mqtt_spb_wrapper import MqttSpbEntityDevice

_DEBUG = True  # Enable debug messages

mqtt_broker_host = os.environ.get("MQTT_HOST") or "hivemq-hivemq-mqtt"
mqtt_broker_port = int(os.environ.get("MQTT_PORT") or 1883)
polling_interval = int(os.environ.get("POLLING_INTERVAL") or 5)
devices = {}


def net_dev():
    """
    Return a dictionary containing the network interface statistics
    as reported in /proc/net/dev.
    """
    dev_file = "/proc/net/dev" if os.path.exists("/proc/net/dev") else "dev"
    lines = open(dev_file, "r").readlines()

    columnLine = lines[1]
    _, receiveCols, transmitCols = columnLine.split("|")
    receiveColsM = map(lambda a: "recv_" + a, receiveCols.split())
    transmitColsM = map(lambda a: "trans_" + a, transmitCols.split())

    cols = list(receiveColsM) + list(transmitColsM)

    faces = {}
    for line in lines[2:]:
        if line.find(":") < 0:
            continue
        face, data = line.split(":")
        faceData = dict(zip(cols, data.split()))
        faces[face.strip()] = faceData

    return faces


def callback_command(payload):
    print("DEVICE received CMD: %s" % (payload))


def callback_message(topic, payload):
    print("Received MESSAGE: %s - %s" % (topic, payload))


# Create the spB entity object
def prepare_rebirth():
    group_name = "Kube"
    edge_node_name = os.environ.get("HOSTNAME") or os.environ.get("HOST") or "localhost"

    for iface, data in net_dev().items():
        device = MqttSpbEntityDevice(group_name, edge_node_name, iface, _DEBUG)

        device.on_message = callback_message  # Received messages
        device.on_command = callback_command  # Callback for received commands

        # Set the device Attributes, Data and Commands that will be sent on the DBIRTH message --------------------------

        # Attributes
        device.attribures.set_value("description", "Kubernetes Pod")
        device.attribures.set_value("type", "linux-vm")
        device.attribures.set_value("version", "0.01")

        # Data / Telemetry
        device.data.set_dictionary(data)

        # Commands
        device.commands.set_value("rebirth", False)

        devices[iface] = device


def connect():
    # Connect to the MQTT broker and send the birth message
    for device in devices.values():
        _connected = False
        while not _connected:
            print("Trying to connect to broker...")
            _connected = device.connect(mqtt_broker_host, mqtt_broker_port)
            if not _connected:
                print("  Error, could not connect. Trying again in a few seconds ...")
                time.sleep(3)
        # Send birth message
        device.publish_birth()


def publish_data():
    while True:
        data = net_dev()
        for iface, device in devices.items():
            # Update the data value
            device.data.set_dictionary(data[iface])

            # Send data values
            device.publish_data()

            # Sleep some time
        time.sleep(polling_interval)


prepare_rebirth()
connect()
publish_data()
