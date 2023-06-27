import pandas as pd


def get_test_data():
    TEST_DATA_PATH = "test_data_looped.csv"
    test_set = pd.read_csv(TEST_DATA_PATH).sort_values("time_in_cycles")
    test_set = test_set.sort_values(by=["new_cycle", "engine_no"])
    test_set = test_set.drop("new_cycle", axis=1)
    return test_set


def rename_sensors(row, pred_feautures, anomaly_features):
    sensor_names = [
        "Total temperature at fan inlet",
        "Total temperature at LPC outlet",
        "Total temperature at HPC outlet",
        "Total Temperature LPT outlet",
        "Pressure at fan inlet",
        "Total pressure in bypass-duct",
        "Total pressure at HPC outlet",
        "Physical fan speed",
        "Physical core speed",
        "Engine pressure ratio (P50/P2)",
        "Static pressure at HPC outlet",
        "Ratio of fuel flow to Ps",
        "Corrected fan speed",
        "Corrected core speed",
        "Bypass Ratio",
        "Burner fuel-air ratio",
        "Bleed enthalpy",
        "Demanded fan speed",
        "Demanded corrected fan speed",
        "HPT coolant bleed",
        "LPT coolant bleed",
    ]

    sid_to_fname = {f"sensor_{i+1}": name for i, name in enumerate(sensor_names)}

    col_rename_dict = {
        "engine_no": "Engine ID",
        "time_in_cycles": "Completed cycles",
        "op_setting_1": "Altitude",
        "op_setting_2": "Mach number",
        **sid_to_fname,
    }

    row.index = [col_rename_dict[attr_name] for attr_name in row.index]
    top_predicitive_features = {
        f"top_{ind+1}_predictive_feature": col_rename_dict[f.replace("_avg", "")]
        for ind, f in enumerate(pred_feautures)
    }
    top_anomalous_features = {
        f"anomaly_feature_{ind+1}": col_rename_dict[f]
        for ind, f in enumerate(anomaly_features)
    }
    return row, top_predicitive_features, top_anomalous_features
