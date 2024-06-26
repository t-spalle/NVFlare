# Copyright (c) 2023, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import csv
from typing import Dict, List, Tuple

import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


def to_dataset_tuple(data: dict):
    dataset_tuples = {}
    for dataset_name, dataset in data.items():
        dataset_tuples[dataset_name] = _to_data_tuple(dataset)
    return dataset_tuples


def _to_data_tuple(data):
    data_num = data.shape[0]
    # split to feature and label
    x = data.iloc[:, 1:]
    y = data.iloc[:, 0]
    return x.to_numpy(), y.to_numpy(), data_num


def load_features(feature_data_path: str) -> List:
    try:
        features = []
        with open(feature_data_path, "r") as file:
            # Create a CSV reader object
            csv_reader = csv.reader(file)
            line_list = next(csv_reader)
            features = line_list
        return features
    except Exception as e:
        raise Exception(f"Load header for path'{feature_data_path} failed! {e}")


def load_data(
    data_path: str,data_path2 :str, data_features: List, skip_rows=None) -> Dict[str, pd.DataFrame]:
    try:
        df: pd.DataFrame = pd.read_csv(
            data_path, names=data_features, sep=r"\s*,\s*", engine="python", na_values="?", skiprows=skip_rows
        )
        df=df.iloc[1:]
        #train, test = train_test_split(df, test_size=0.5, random_state=random_state)
        train=df
        #for testing data using recent data 

        df2: pd.DataFrame = pd.read_csv(
            data_path2, names=data_features, sep=r"\s*,\s*", engine="python", na_values="?", skiprows=skip_rows
        )
        df2=df2.iloc[1:]
        test=df2

        return {"train": train, "test": test}
    except Exception as e:
        raise Exception(f"Load data for path '{data_path}' failed! {e}")



def transform_data(data: Dict[str, Tuple]) -> Dict[str, Tuple]:
    # Standardize features by removing the mean and scaling to unit variance
    scaler = StandardScaler()
    scaled_datasets = {}
    for dataset_name, (x_data, y_data, data_num) in data.items():
        x_scaled = scaler.fit_transform(x_data)
        scaled_datasets[dataset_name] = (x_scaled, y_data, data_num)
    return scaled_datasets


def main():
    parser = define_args_parser()
    args = parser.parse_args()
    data_root_dir = args.data_root_dir
    #random_state = args.random_state
    #test_size = args.test_size
    skip_rows = args.skip_rows

    site_name = "site-1"
    feature_data_path = f"{data_root_dir}/{site_name}_header.csv"
    features = load_features(feature_data_path)
    n_features = len(features) - 1  # remove label

    data_path = f"{data_root_dir}/{site_name}.csv"
    data_path2 = f"{data_root_dir}/test.csv"
    data = load_data(data_path=data_path,data_path2=data_path2, data_features=features, skip_rows=skip_rows)

    data = to_dataset_tuple(data)
    dataset = transform_data(data)
    x_train, y_train, train_size = dataset["train"]
    x_test, y_test, test_size = dataset["test"]

    # convert to xgboost data matrix
    dmat_train = xgb.DMatrix(x_train, label=y_train)
    dmat_test = xgb.DMatrix(x_test, label=y_test)

    xgb_params = {
        "eta": 0.1,
        "objective": "binary:logistic",
        "max_depth": 8,
        "eval_metric": "auc",
        "nthread": 16,
        "num_parallel_tree": 1,
        "subsample": 1.0,
        "tree_method": "hist",
    }

    # Train the model on the training set
    model = xgb.train(
        xgb_params,
        dmat_train,
        num_boost_round=100,
        evals=[(dmat_train, "train"), (dmat_test, "test")],
    )

    # evaluate model
    auc = evaluate_model(x_test, model, y_test)

    # Print the results
    print(f"local model AUC: {auc:.5f}")


def evaluate_model(x_test, model, y_test):
    # Make predictions on the testing set
    dtest = xgb.DMatrix(x_test)
    y_pred = model.predict(dtest)

    # Evaluate the model
    auc = roc_auc_score(y_test, y_pred)
    return auc


def define_args_parser():
    parser = argparse.ArgumentParser(description="scikit learn linear model with SGD")
    parser.add_argument("--data_root_dir", type=str, help="root directory path to csv data file")
    #parser.add_argument("--random_state", type=int, default=0, help="random state")
    #parser.add_argument("--test_size", type=float, default=0.2, help="test ratio, default to 20%")
    parser.add_argument(
        "--skip_rows",
        type=str,
        default=None,
        help="""If skip_rows = N, the first N rows will be skipped, 
       if skiprows=[0, 1, 4], the rows will be skip by row indices such as row 0,1,4 will be skipped. """,
    )
    return parser


if __name__ == "__main__":
    main()
