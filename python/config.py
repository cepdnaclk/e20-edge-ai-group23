"""
config.py – Central configuration loaded from environment variables / .env
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── MQTT Settings ──────────────────────────────────────────────────────────────
MQTT_BROKER   = os.getenv("MQTT_BROKER",   "broker.hivemq.com")
MQTT_PORT     = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

# ── Identity ───────────────────────────────────────────────────────────────────
GROUP_ID   = os.getenv("GROUP_ID",   "group23")
PROJECT_ID = os.getenv("PROJECT_ID", "batch-reactor")

# ── MQTT Topics ────────────────────────────────────────────────────────────────
TOPIC_DATA   = f"sensors/{GROUP_ID}/{PROJECT_ID}/data"
TOPIC_ALERT  = f"alerts/{GROUP_ID}/{PROJECT_ID}/status"
TOPIC_STATS  = f"sensors/{GROUP_ID}/{PROJECT_ID}/stats"

# ── Batch Simulation Settings ──────────────────────────────────────────────────
BATCH_DURATION_SEC       = 30      # seconds per simulated batch cycle
PUBLISH_INTERVAL_SEC     = 2       # sensor reading cadence (seconds)
READINGS_PER_BATCH       = BATCH_DURATION_SEC // PUBLISH_INTERVAL_SEC

# ── Anomaly Detection Thresholds ───────────────────────────────────────────────
ENERGY_BASELINE_KWH      = 45.0    # expected energy per batch (kWh)
ENERGY_UPPER_THRESHOLD   = 60.0    # > this → HIGH anomaly
ENERGY_LOWER_THRESHOLD   = 30.0    # < this → LOW anomaly
TEMPERATURE_MAX_C        = 100.0    # max safe reactor temp
PRESSURE_MAX_BAR         = 6.0     # max safe pressure
ISOLATION_CONTAMINATION  = 0.35    # Isolation Forest contamination rate

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_FILE = "logs/edge_ai.log"
