import time
import traceback
import json
import threading
import paho.mqtt.client as mqtt
import pandas as pd
import influxdb_client, os, time
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.write_api import WriteApi
import config
from pred_maintenance_and_anomaly import get_model_dict
from data_help_funcs import rename_sensors
from publish import publish_msg
import warnings

warnings.filterwarnings("ignore")

try:
    write_client = influxdb_client.InfluxDBClient(
        url=config.url, token=config.token, org=config.org
    )
except:
    print("Failed to init influx conn...")

model_dict = get_model_dict()


def predict_on_msg(client, userdata, message):
    print(f"Received message: {message.payload.decode('utf-8')}")
    row = json.loads(message.payload.decode("utf-8"))
    for k, v in row.items():
        row[k] = float(v)
    row["engine_no"] = int(row["engine_no"])
    row = pd.Series(row)

    engine_no = row["engine_no"]
    data = model_dict[engine_no].get_scores(row)
    row, top_predicitive_features, top_anomalous_features = rename_sensors(
        row, data[1], data[3]
    )

    formated_msg_orig = {
        "Probability of failure within 30 cycles": data[0],
        **top_predicitive_features,
        "Anomaly score": data[2],
        **top_anomalous_features,
        **row,
    }
    formated_msg = json.dumps(formated_msg_orig)
    publish_msg(formated_msg, config.predictions_topic)

    print(f"Sent msg: {formated_msg}")

    try:
        influx_send_msg(formated_msg_orig, engine_no)
    except Exception as exc:
        print(f"Failed to send data to influx due to: {exc}")


def influx_send_msg(formated_msg_orig, engine_no):
    write_api = write_client.write_api(write_options=SYNCHRONOUS)

    for key, value in formated_msg_orig.items():
        point = Point("measurement").tag("engine_no", int(engine_no)).field(key, value)
        point2 = Point("measurement2").field(key, value)
        write_api.write(bucket=config.bucket, org=config.org, record=point)
        write_api.write(bucket=config.bucket, org=config.org, record=point2)
        # time.sleep(0.1) # separate points by 1 second

    print("shared")


def listen_to_mqtt_topic():
    client = mqtt.Client()
    client.connect(config.broker_address, config.broker_port)
    client.subscribe(config.raw_data_topic)

    client.on_message = predict_on_msg

    client.loop_start()
    time.sleep(30)
    client.loop_stop()
    return True


class MQTTWatcher(threading.Thread):
    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.is_set():
            listen_to_mqtt_topic()

    def stop(self):
        self._stop_event.set()


def main():
    while True:
        mqtt_watcher = MQTTWatcher()
        mqtt_watcher.start()

        mqtt_watcher.join(timeout=36)

        if mqtt_watcher.is_alive():
            print("Thread is still running, terminating...")
            mqtt_watcher.stop()
        else:
            print("Thread has finished")


if __name__ == "__main__":
    main()
