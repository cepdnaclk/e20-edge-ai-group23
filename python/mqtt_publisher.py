"""
mqtt_publisher.py – Stand-alone publisher script (Task 3).

Run directly:
    python mqtt_publisher.py

Publishes sensor readings to:
    sensors/<group>/<project>/data

You can modify the simulator parameters here to change the sensor data
characteristics (as required by the lab sheet).
"""

import json
import logging
import os
import sys
import time

# Allow running without Docker (local dev)
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

import config
from mqtt_client import MQTTClient
from simulator   import BatchReactorSimulator

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.LOG_FILE, mode="a"),
    ],
)
logger = logging.getLogger("publisher")


def main():
    os.makedirs("logs", exist_ok=True)
    logger.info("=" * 60)
    logger.info("Batch Reactor MQTT Publisher")
    logger.info("Topic : %s", config.TOPIC_DATA)
    logger.info("Broker: %s:%d", config.MQTT_BROKER, config.MQTT_PORT)
    logger.info("=" * 60)

    client = MQTTClient(client_id=f"{config.GROUP_ID}-publisher")
    if not client.connect():
        logger.critical("Could not connect to broker. Exiting.")
        sys.exit(1)

    sim = BatchReactorSimulator(
        readings_per_batch   = config.READINGS_PER_BATCH,
        publish_interval_sec = config.PUBLISH_INTERVAL_SEC,
    )

    try:
        while True:
            reading          = sim.next_reading()
            payload          = reading.to_dict()
            payload["group"] = config.GROUP_ID
            payload["project"] = config.PROJECT_ID

            client.publish(config.TOPIC_DATA, payload)
            logger.info(
                "Batch #%03d | Phase: %-10s | T=%.1f°C | P=%.2f bar | "
                "P_kW=%.2f | E_kWh=%.4f",
                payload["batch_id"],
                payload["cycle_phase"],
                payload["temperature_c"],
                payload["pressure_bar"],
                payload["power_kw"],
                payload["energy_kwh"],
            )
            time.sleep(config.PUBLISH_INTERVAL_SEC)

    except KeyboardInterrupt:
        logger.info("Publisher stopped by user.")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
