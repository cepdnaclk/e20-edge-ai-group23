"""
train_model.py – Offline model training / evaluation script.

Run once to pre-train the Isolation Forest on a large synthetic dataset
before deploying to Docker. The saved model is then loaded by main.py.

Usage:
    python train_model.py [--batches N]
"""

import argparse
import json
import logging
import os
import sys

import numpy as np
import joblib

sys.path.insert(0, os.path.dirname(__file__))

from sklearn.ensemble        import IsolationForest
from sklearn.preprocessing   import StandardScaler
from sklearn.metrics         import classification_report, confusion_matrix

import config
from simulator import BatchReactorSimulator

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train")

os.makedirs("models", exist_ok=True)


def generate_dataset(n_batches: int):
    sim      = BatchReactorSimulator(
        readings_per_batch   = config.READINGS_PER_BATCH,
        publish_interval_sec = config.PUBLISH_INTERVAL_SEC,
    )
    features = []
    labels   = []
    total    = n_batches * config.READINGS_PER_BATCH

    for _ in range(total):
        r = sim.next_reading()
        features.append([
            r.temperature_c,
            r.pressure_bar,
            r.power_kw,
            r.flow_rate_lpm,
            r.energy_kwh,
        ])
        labels.append(1 if r.anomaly_injected else 0)

    return np.array(features), np.array(labels)


def main():
    parser = argparse.ArgumentParser(description="Train Isolation Forest")
    parser.add_argument("--batches", type=int, default=200,
                        help="Number of simulated batches for training")
    args = parser.parse_args()

    logger.info("Generating %d simulated batches …", args.batches)
    X, y = generate_dataset(args.batches)
    logger.info("Dataset shape: %s | Anomaly rate: %.1f%%",
                X.shape, 100 * y.mean())

    scaler  = StandardScaler()
    X_scale = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators  = 300,
        contamination = config.ISOLATION_CONTAMINATION,
        random_state  = 42,
        n_jobs        = -1,
    )
    model.fit(X_scale)
    logger.info("Model trained.")

    # Evaluate (qualitative – IF is unsupervised)
    preds = model.predict(X_scale)  # -1=anomaly, 1=normal
    preds_binary = (preds == -1).astype(int)

    logger.info("\n%s", classification_report(y, preds_binary,
                                               target_names=["Normal", "Anomaly"]))
    logger.info("Confusion matrix:\n%s", confusion_matrix(y, preds_binary))

    joblib.dump(model,  "models/isolation_forest.pkl")
    joblib.dump(scaler, "models/scaler.pkl")
    logger.info("✅ Model saved to models/")


if __name__ == "__main__":
    main()
