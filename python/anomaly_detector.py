"""
anomaly_detector.py – Two-layer anomaly detection for Batch Reactor data.

Layer 1 – Rule Engine (threshold-based, instant alerts)
  • Energy per batch > ENERGY_UPPER_THRESHOLD → CRITICAL
  • Energy per batch < ENERGY_LOWER_THRESHOLD → WARNING (under-reaction)
  • Temperature       > TEMPERATURE_MAX_C     → CRITICAL
  • Pressure          > PRESSURE_MAX_BAR      → CRITICAL

Layer 2 – ML (Isolation Forest, trained on the first N clean batches)
  • Tags readings as anomalous based on the learned "normal" distribution
  • Retrained automatically every RETRAIN_INTERVAL batches
"""

import logging
import os
import joblib
import numpy as np
from dataclasses import dataclass
from typing import Optional

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

import config

logger = logging.getLogger(__name__)

MODEL_PATH  = "models/isolation_forest.pkl"
SCALER_PATH = "models/scaler.pkl"

os.makedirs("models", exist_ok=True)

RETRAIN_INTERVAL = 10   # retrain every N completed batches
WARMUP_BATCHES   = 5    # collect this many clean batches before first training


@dataclass
class DetectionResult:
    rule_anomaly:    bool
    ml_anomaly:      bool
    anomaly_type:    str         # NORMAL | WARNING | CRITICAL
    rule_reason:     str
    ml_score:        float       # Isolation Forest decision score (negative = anomalous)
    severity:        int         # 0=normal, 1=warning, 2=critical
    batch_energy:    float
    current_temperature: float
    current_pressure:    float


class AnomalyDetector:
    def __init__(self):
        self._model:   Optional[IsolationForest] = None
        self._scaler:  Optional[StandardScaler]  = None
        self._buffer:  list  = []   # feature rows for the current batch (accumulating)
        self._history: list  = []   # completed batch feature vectors (for training)
        self._batch_energies: list  = []
        self._current_batch_id: int = -1
        self._batches_since_retrain: int = 0

        # Try to load a previously saved model
        self._load_model()

    # ── Feature engineering ────────────────────────────────────────────────────

    @staticmethod
    def _extract_features(reading: dict) -> np.ndarray:
        """Convert a single sensor reading to feature vector."""
        return np.array([
            reading.get("temperature_c",  0.0),
            reading.get("pressure_bar",   0.0),
            reading.get("power_kw",       0.0),
            reading.get("flow_rate_lpm",  0.0),
            reading.get("energy_kwh",     0.0),
        ], dtype=float)

    # ── Rule-based layer ───────────────────────────────────────────────────────

    def _check_rules(self, reading: dict, batch_energy: float) -> tuple[bool, str, int]:
        """Returns (is_anomaly, reason, severity)."""
        temp     = reading.get("temperature_c", 0)
        pressure = reading.get("pressure_bar",  0)

        if temp > config.TEMPERATURE_MAX_C:
            return True, f"Temperature runaway: {temp:.1f}°C > {config.TEMPERATURE_MAX_C}°C", 2

        if pressure > config.PRESSURE_MAX_BAR:
            return True, f"Pressure surge: {pressure:.2f} bar > {config.PRESSURE_MAX_BAR} bar", 2

        if batch_energy > config.ENERGY_UPPER_THRESHOLD:
            return True, f"Energy spike: {batch_energy:.2f} kWh > {config.ENERGY_UPPER_THRESHOLD} kWh", 2

        if (reading.get("cycle_phase") == "discharge"
                and batch_energy < config.ENERGY_LOWER_THRESHOLD
                and batch_energy > 0):
            return True, f"Energy sag: {batch_energy:.2f} kWh < {config.ENERGY_LOWER_THRESHOLD} kWh", 1

        return False, "Normal", 0

    # ── ML layer ───────────────────────────────────────────────────────────────

    def _fit_model(self):
        if len(self._history) < WARMUP_BATCHES:
            logger.info("Waiting for warm-up data (%d/%d batches)",
                        len(self._history), WARMUP_BATCHES)
            return

        X = np.vstack(self._history)
        self._scaler = StandardScaler()
        X_scaled     = self._scaler.fit_transform(X)

        self._model = IsolationForest(
            n_estimators=200,
            contamination=config.ISOLATION_CONTAMINATION,
            random_state=42,
            n_jobs=-1,
        )
        self._model.fit(X_scaled)
        self._save_model()
        logger.info("Isolation Forest retrained on %d samples.", len(X))

    def _ml_predict(self, features: np.ndarray) -> tuple[bool, float]:
        """Returns (is_anomaly, decision_score). Score < 0 → anomalous."""
        if self._model is None or self._scaler is None:
            return False, 0.0
        X_scaled = self._scaler.transform(features.reshape(1, -1))
        score    = self._model.decision_function(X_scaled)[0]
        label    = self._model.predict(X_scaled)[0]  # -1=anomaly, 1=normal
        return (label == -1), float(score)

    # ── Model persistence ──────────────────────────────────────────────────────

    def _save_model(self):
        try:
            joblib.dump(self._model,  MODEL_PATH)
            joblib.dump(self._scaler, SCALER_PATH)
        except Exception as exc:
            logger.warning("Could not save model: %s", exc)

    def _load_model(self):
        try:
            if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
                self._model  = joblib.load(MODEL_PATH)
                self._scaler = joblib.load(SCALER_PATH)
                logger.info("Loaded existing Isolation Forest model.")
        except Exception as exc:
            logger.warning("Could not load model: %s", exc)

    # ── Main detect interface ──────────────────────────────────────────────────

    def detect(self, reading: dict) -> DetectionResult:
        batch_id    = reading.get("batch_id", 0)
        batch_energy = reading.get("energy_kwh", 0.0)

        # Detect batch transition → archive buffer, maybe retrain
        if batch_id != self._current_batch_id:
            if self._buffer:
                self._history.append(np.vstack(self._buffer))
                self._batches_since_retrain += 1
                if self._batches_since_retrain >= RETRAIN_INTERVAL:
                    self._fit_model()
                    self._batches_since_retrain = 0
            self._buffer          = []
            self._current_batch_id = batch_id
            logger.debug("New batch detected: %d", batch_id)

        features = self._extract_features(reading)
        self._buffer.append(features)

        # Rule-based check
        rule_anomaly, rule_reason, severity = self._check_rules(reading, batch_energy)

        # ML check
        ml_anomaly, ml_score = self._ml_predict(features)

        # Decision fusion: either layer can raise an alert
        is_anomaly = rule_anomaly or ml_anomaly

        if rule_anomaly:
            anomaly_type = "CRITICAL" if severity == 2 else "WARNING"
        elif ml_anomaly:
            anomaly_type = "WARNING"
            rule_reason  = "ML model flagged anomalous pattern"
            severity     = 1
        else:
            anomaly_type = "NORMAL"

        return DetectionResult(
            rule_anomaly         = rule_anomaly,
            ml_anomaly           = ml_anomaly,
            anomaly_type         = anomaly_type,
            rule_reason          = rule_reason,
            ml_score             = round(ml_score, 6),
            severity             = severity,
            batch_energy         = round(batch_energy, 4),
            current_temperature  = reading.get("temperature_c", 0.0),
            current_pressure     = reading.get("pressure_bar",  0.0),
        )
