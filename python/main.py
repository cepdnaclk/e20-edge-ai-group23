"""
main.py – Edge AI orchestrator.

Runs three concurrent threads:
  1. Sensor Publisher   – simulates and publishes sensor data
  2. AI Processor       – subscribes to data, runs anomaly detection, publishes alerts
  3. Stats Aggregator   – publishes batch-level energy statistics every batch
"""

import json
import logging
import os
import sys
import threading
import time
import signal
import csv
from dataclasses import asdict

# Allow running without Docker
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

import config
from anomaly_detector import AnomalyDetector
from mqtt_client      import MQTTClient
from simulator        import BatchReactorSimulator

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.LOG_FILE, mode="a"),
    ],
)
logger = logging.getLogger("main")

# ── Shared state ───────────────────────────────────────────────────────────────
_stop_event     = threading.Event()
_batch_stats    = {}   # batch_id → {energy, anomalies}


# ── Thread 1: Sensor data publisher ───────────────────────────────────────────

def publisher_thread(pub_client: MQTTClient):
    sim = BatchReactorSimulator(
        readings_per_batch   = config.READINGS_PER_BATCH,
        publish_interval_sec = config.PUBLISH_INTERVAL_SEC,
    )
    logger.info("Publisher thread started.")

    # --- Open the CSV file for appending ---
    csv_path = "logs/local_historian.csv"
    with open(csv_path, mode="a", newline="") as file:
        writer = csv.writer(file)
        
        # Write the header row ONLY if the file is completely empty
        if file.tell() == 0:
            writer.writerow(["timestamp", "batch_id", "phase", "temperature", "pressure", "power"])

        while not _stop_event.is_set():
            reading  = sim.next_reading()
            payload  = reading.to_dict()
            payload["group"]   = config.GROUP_ID
            payload["project"] = config.PROJECT_ID
            
            # --- Save to CSV before publishing ---
            writer.writerow([
                payload["timestamp"], 
                payload.get("batch_id", 0), 
                payload.get("cycle_phase", "UNKNOWN"), 
                payload.get("temperature", 0.0), 
                payload.get("pressure", 0.0), 
                payload.get("power_draw", 0.0)
            ])
            file.flush() # Force to save to the hard drive immediately
            # -----------------------------------------------

            pub_client.publish(config.TOPIC_DATA, payload)
            _stop_event.wait(timeout=config.PUBLISH_INTERVAL_SEC)

    logger.info("Publisher thread stopped.")


# ── Thread 2: AI Processor ─────────────────────────────────────────────────────

def ai_processor_thread(sub_client: MQTTClient, alert_client: MQTTClient):
    detector = AnomalyDetector()
    logger.info("AI Processor thread started.")

    def on_message(client, userdata, msg):
        try:
            reading = json.loads(msg.payload.decode())
            result  = detector.detect(reading)

            bid = reading.get("batch_id", 0)
            if bid not in _batch_stats:
                _batch_stats[bid] = {"energy": 0.0, "anomalies": 0, "alerts": []}
            _batch_stats[bid]["energy"] = result.batch_energy
            if result.rule_anomaly or result.ml_anomaly:
                _batch_stats[bid]["anomalies"] += 1

            if result.anomaly_type != "NORMAL":
                alert_payload = {
                    "timestamp":    reading.get("timestamp"),
                    "batch_id":     bid,
                    "cycle_phase":  reading.get("cycle_phase"),
                    "anomaly_type": result.anomaly_type,
                    "rule_reason":  result.rule_reason,
                    "ml_anomaly":   bool(result.ml_anomaly),    # cast numpy bool_ → Python bool
                    "ml_score":     float(result.ml_score),     # cast numpy float64 → Python float
                    "severity":     int(result.severity),
                    "batch_energy": float(result.batch_energy),
                    "temperature":  float(result.current_temperature),
                    "pressure":     float(result.current_pressure),
                    "group":        config.GROUP_ID,
                    "project":      config.PROJECT_ID,
                }
                alert_client.publish(config.TOPIC_ALERT, alert_payload, retain=True)
                logger.warning(
                    "🚨 ALERT [%s] Batch #%d | %s | E=%.2f kWh",
                    result.anomaly_type, bid, result.rule_reason, result.batch_energy
                )
            else:
                logger.debug("Batch #%d – NORMAL (E=%.4f kWh)", bid, result.batch_energy)

        except Exception as exc:
            logger.error("AI Processor error: %s", exc, exc_info=True)

    sub_client.subscribe(config.TOPIC_DATA)
    sub_client._client.on_message = on_message

    while not _stop_event.is_set():
        _stop_event.wait(timeout=1)

    logger.info("AI Processor thread stopped.")


# ── Thread 3: Stats aggregator ─────────────────────────────────────────────────

def stats_thread(stats_client: MQTTClient):
    """Publish per-batch stats summary every BATCH_DURATION_SEC."""
    logger.info("Stats thread started.")
    last_batch = -1

    while not _stop_event.is_set():
        if _batch_stats:
            latest_bid = max(_batch_stats.keys())
            if latest_bid != last_batch:
                stats = _batch_stats[latest_bid]
                payload = {
                    "batch_id":       latest_bid,
                    "total_energy":   round(stats["energy"],    4),
                    "anomaly_count":  stats["anomalies"],
                    "status":         "ANOMALOUS" if stats["anomalies"] > 0 else "NORMAL",
                    "group":          config.GROUP_ID,
                    "project":        config.PROJECT_ID,
                }
                stats_client.publish(config.TOPIC_STATS, payload, retain=True)
                logger.info(
                    "📊 Stats | Batch #%d | Energy=%.4f kWh | Anomalies=%d | %s",
                    latest_bid, stats["energy"],
                    stats["anomalies"], payload["status"]
                )
                last_batch = latest_bid

        _stop_event.wait(timeout=5)

    logger.info("Stats thread stopped.")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    # --- Graceful Shutdown Handler for Docker ---
    def sigterm_handler(sig, frame):
        logger.info("🚨 SIGTERM received from Docker. Initiating graceful shutdown...")
        raise KeyboardInterrupt  # Routes the signal to existing cleanup block!
    
    signal.signal(signal.SIGTERM, sigterm_handler)
    # --------------------------------------------

    logger.info("=" * 60)
    logger.info("Batch Reactor Cycle Anomaly Detection – Edge AI System")
    logger.info("Group  : %s", config.GROUP_ID)
    logger.info("Broker : %s:%d", config.MQTT_BROKER, config.MQTT_PORT)
    logger.info("Data   : %s", config.TOPIC_DATA)
    logger.info("Alerts : %s", config.TOPIC_ALERT)
    logger.info("Stats  : %s", config.TOPIC_STATS)
    logger.info("=" * 60)

    # Create three separate MQTT clients (paho is not thread-safe for a single client)
    pub_client   = MQTTClient(client_id=f"{config.GROUP_ID}-publisher")
    sub_client   = MQTTClient(client_id=f"{config.GROUP_ID}-subscriber")
    alert_client = MQTTClient(client_id=f"{config.GROUP_ID}-alerter")
    stats_client = MQTTClient(client_id=f"{config.GROUP_ID}-stats")

    for c in (pub_client, sub_client, alert_client, stats_client):
        if not c.connect(timeout=30):
            logger.critical("Failed to connect MQTT client. Exiting.")
            sys.exit(1)

    threads = [
        threading.Thread(target=publisher_thread,    args=(pub_client,),                daemon=True, name="Publisher"),
        threading.Thread(target=ai_processor_thread, args=(sub_client, alert_client),    daemon=True, name="AIProcessor"),
        threading.Thread(target=stats_thread,        args=(stats_client,),              daemon=True, name="Stats"),
    ]

    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # --- This is where the sigterm_handler routes the shutdown command! ---
        logger.info("Shutdown signal received. Stopping threads...")
        _stop_event.set()
        for t in threads:
            t.join(timeout=5)
            
        logger.info("Disconnecting from MQTT broker...")
        for c in (pub_client, sub_client, alert_client, stats_client):
            c.disconnect()
            
        logger.info("✅ Edge AI Service shut down cleanly.")


if __name__ == "__main__":
    main()