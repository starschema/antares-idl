import time
import traceback
import json
import config
import pandas as pd
from publish import publish_msg
from data_help_funcs import get_test_data
import warnings

warnings.filterwarnings("ignore")

test_set = get_test_data()


def generate():
    while True:
        for idx, row in test_set.iterrows():
            try:
                formated_msg = {**row}
                formated_msg = json.dumps(formated_msg)
                print(formated_msg)
                publish_msg(formated_msg, config.raw_data_topic)
            except Exception as exc:
                print(traceback.format_exc())
                print(f"issue {exc}")


if __name__ == "__main__":
    generate()
