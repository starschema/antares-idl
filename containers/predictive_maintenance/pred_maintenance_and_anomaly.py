from typing import Protocol
import numpy as np
import pandas as pd
import pickle

# from typing_extensions import Protocol  # for Python <3.8


class ModellObj(Protocol):
    def fit(self):
        pass

    def predict(self):
        pass


class ModellHandler:
    @staticmethod
    def load(path: str) -> ModellObj:
        with open(path, "rb") as handle:
            model = pickle.load(
                handle,
            )
        return model

    @staticmethod
    def save(path: str):
        # don't think we need to save models
        pass


class PreProcessData:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def _calc_rw_stats(self, df_in):
        """Calculate mean and std of data buffer

        Args:
                df_in (dataframe)     : The input dataframe to be proccessed (training or test)

        Reurns:
                dataframe: contains the input dataframe with additional rolling mean and std for each sensor

        """
        sensor_cols = [c for c in df_in.columns if "sensor" in c]

        sensor_av_cols = [f + "_avg" for f in sensor_cols]
        sensor_sd_cols = [f + "_sd" for f in sensor_cols]

        df_sub = df_in[sensor_cols]

        # get rolling mean for the subset
        av = df_sub.mean()
        av.index = sensor_av_cols

        # get the rolling standard deviation for the subset
        sd = df_sub.std().fillna(0)
        sd.index = sensor_sd_cols

        # combine the two new subset dataframes columns to the engine subset
        rw_features_added = pd.concat([df_in.iloc[-1], av, sd], axis=0)

        # add percentiles
        for i in range(1, 10):
            temp_percentiles = df_sub.quantile(i / 10)
            temp_percentiles.index = [f + "_quant_" + str(i) + "0" for f in sensor_cols]
            rw_features_added = pd.concat([rw_features_added, temp_percentiles], axis=0)

        return rw_features_added

    def process(self, data: pd.DataFrame) -> pd.DataFrame:
        # extend last item with rolling window features
        rw_features_added = self._calc_rw_stats(data)
        return rw_features_added


class PredictiveMaintanance:
    _base_data_required_shape = None

    def __init__(
        self,
        base_data_set: pd.DataFrame,
        preproc_data_help_variables: dict,
        predict_modell: ModellObj,
        predictive_features: list,
        anomaly_model: ModellObj,
        rolling_window_size: int,
    ):
        self.data_buffer = base_data_set
        self.rolling_window_size = rolling_window_size

        self.predict_modell = predict_modell
        self.predictive_features = predictive_features

        self.anomaly_model = anomaly_model

        self.data_preprocessor = PreProcessData(**preproc_data_help_variables)

    def get_scores(self, new_record: pd.DataFrame) -> tuple:
        self.set_current_work_data(new_record)
        pred_percent, top_predictive_feature = self.predict()
        anomaly_score, anomaly_feature_name = self.find_anomaly()
        return pred_percent, top_predictive_feature, anomaly_score, anomaly_feature_name

    def set_current_work_data(self, new_record: pd.DataFrame) -> None:
        self.data_buffer = self.data_buffer.append(new_record, ignore_index=True)

        # remove first record if buffer was full
        if len(self.data_buffer) > self.rolling_window_size:
            self.data_buffer.drop(index=self.data_buffer.index[0], axis=0, inplace=True)
        self.X = self.data_preprocessor.process(self.data_buffer)

    def predict(self) -> (float, str):
        # get probabilities for class 1, which is failure
        input_data = np.expand_dims(self.X[self.predictive_features], axis=0)
        prediction = self.predict_modell.predict_proba(input_data)[0, 0]

        # get explanations for class 1
        shap_values = self.predict_modell.predict_proba(input_data, pred_contrib=True)[
            0, :-1
        ]
        shap_series = pd.Series(
            index=self.predictive_features, data=shap_values
        ).sort_values(ascending=False)
        top3_features = shap_series[:3].index.values

        return prediction, top3_features

    def find_anomaly(self) -> (float, str):
        anomaly_feature_columns = [c for c in self.X.index if "sensor" in c]

        isolation_forest_model = self.anomaly_model[0]
        telemetry_stat_df = self.anomaly_model[1]

        input_data = pd.DataFrame(self.X[anomaly_feature_columns]).T

        # calculate anomaly scores
        # isolation forest
        score_isolationforest = isolation_forest_model.decision_function(input_data)[0]

        # mean+-std, percentiles
        result_dict = {}
        for f in anomaly_feature_columns:
            result_dict[(f + "_perc_anom")] = np.where(
                (input_data[f] < telemetry_stat_df.loc[1][f + "_percentile_1"])
                | (input_data[f] > telemetry_stat_df.loc[1][f + "_percentile_99"]),
                1,
                0,
            )
            result_dict[(f + "_dev")] = abs(
                (input_data[f] - telemetry_stat_df.loc[1][(f + "_mean")])
                / telemetry_stat_df.loc[1][(f + "_std")]
            )

        input_data = pd.concat([input_data, pd.DataFrame(result_dict)], axis=1)

        score_percentile = (
            input_data[[x for x in input_data.columns if "_perc_anom" in x]].sum(axis=1)
        ).iloc[0]
        score_dev = (
            input_data[[x for x in input_data.columns if "_dev" in x]].max(axis=1)
        ).iloc[0]

        anomaly_score = (
            5 * (-score_isolationforest + 0.13) * (100 / 0.30)
            + (score_percentile * (100 / 140))
            + (score_dev * (2))
        ) / 7

        if anomaly_score < 0:
            anomaly_score = 0
        elif anomaly_score > 100:
            anomaly_score = 100

        # select anomalous feature
        # anom_sensor1 = input_data[[ x for x in input_data.columns if '_dev' in x]].idxmax(axis=1).apply(lambda y: '_'.join(y.split('_')[:2]))
        dft = input_data[[x for x in input_data.columns if "_dev" in x]].T
        c = (dft.columns)[0]
        t3 = list(dft[[c]].sort_values([c], ascending=False).index)
        t4 = ["_".join(x.split("_")[:2]) for x in t3]
        top_anomalous_features = list(dict.fromkeys(t4))[:3]
        return (anomaly_score, top_anomalous_features)


PREDICTIVE_MODEL_PATH = "lgbm_last10.pickle"
predicitve_model = ModellHandler.load(PREDICTIVE_MODEL_PATH)

ANOMALY_MODEL_PATH = "anomaly_last10.pickle"
anomaly_model_cores = ModellHandler.load(ANOMALY_MODEL_PATH)

BASE_DATA_PATH = "first_9_records_test.csv"
base_data_set = pd.read_csv(BASE_DATA_PATH)

predictive_feature_list = [
    "sensor_11",
    "sensor_11_avg",
    "sensor_12",
    "sensor_12_avg",
    "sensor_15",
    "sensor_15_avg",
    "sensor_17",
    "sensor_17_avg",
    "sensor_2",
    "sensor_20",
    "sensor_20_avg",
    "sensor_21",
    "sensor_21_avg",
    "sensor_2_avg",
    "sensor_3_avg",
    "sensor_4",
    "sensor_4_avg",
    "sensor_7",
    "sensor_7_avg",
    "time_in_cycles",
]

rolling_window_size = 10


def get_model_dict():
    # for each engine in the test set, initialize model
    model_dict = {}
    for engine_no, group in base_data_set.groupby("engine_no"):
        pred_maintenance_obj = PredictiveMaintanance(
            base_data_set=group,
            predict_modell=predicitve_model,
            predictive_features=predictive_feature_list,
            anomaly_model=anomaly_model_cores,
            preproc_data_help_variables={},
            rolling_window_size=rolling_window_size,
        )
        model_dict[engine_no] = pred_maintenance_obj
    return model_dict


# TEST_DATA_PATH = "remaining_records_test.csv"
# test_set = pd.read_csv(TEST_DATA_PATH)


# row = test_set.loc[0]
# engine_no = row["engine_no"]
# print(model_dict[engine_no].get_scores(row))


# for idx, row in test_set.iterrows():
#    engine_no = row["engine_no"]
#    print(model_dict[engine_no].get_scores(row))
