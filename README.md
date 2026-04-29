# 🏭 Batch Reactor Cycle Anomaly Detection
### Edge AI + Industrial IoT Mini Project

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![MQTT](https://img.shields.io/badge/MQTT-paho-green.svg)](https://pypi.org/project/paho-mqtt/)
[![Node-RED](https://img.shields.io/badge/Node--RED-dashboard-red.svg)](https://nodered.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 👥 Group Members

| Name | Student ID | Role |
|------|-----------|------|
| 1 | *ID* | Edge AI / Python |
| 2 | *ID* | MQTT / Integration & Testing |
| 3 | *ID* | Node-RED / Dashboard & Documentation |

## 📋 Project Description

This project implements a complete **Edge AI IoT system** for industrial batch reactor monitoring. A batch reactor performs chemical reactions in discrete cycles (heating → reaction → cooling → discharge). Abnormal energy consumption per batch can indicate:

- 🔺 **Energy Spike** — faulty heating elements, over-dosing, or control failures
- 🔻 **Energy Sag** — incomplete reaction, feed shortfall, or coolant leak
- 🌡️ **Temperature Runaway** — exothermic event or sensor failure
- 💨 **Pressure Surge** — blocked discharge valve or unexpected side-reaction

The system uses a **two-layer detection approach**:

1. **Rule Engine** (instant) — threshold checks on temperature, pressure, and cumulative batch energy
2. **Machine Learning** — Isolation Forest trained on normal batch profiles; auto-retrains every 10 batches

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      EDGE (Local)                           │
│                                                             │
│  ┌──────────────┐    ┌─────────────────┐                   │
│  │  Batch Reactor│    │  Python Edge AI  │                   │
│  │  Simulator   │───▶│  - Simulator     │                   │
│  │  (4-phase)   │    │  - Rule Engine   │                   │
│  └──────────────┘    │  - Isolation     │                   │
│                      │    Forest ML     │                   │
│                      └────────┬─────────┘                   │
└───────────────────────────────│─────────────────────────────┘
                                │ MQTT Publish
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                   CLOUD / BROKER                             │
│                                                             │
│         ┌──────────────────────────────────┐               │
│         │    HiveMQ Public Broker          │               │
│         │  broker.hivemq.com:1883          │               │
│         │                                  │               │
│         │  sensors/group23/batch-reactor/data     │         │
│         │  alerts/group23/batch-reactor/status    │         │
│         │  sensors/group23/batch-reactor/stats    │         │
│         └──────────────┬───────────────────┘               │
└───────────────────────│─────────────────────────────────────┘
                        │ MQTT Subscribe
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  DASHBOARD (Node-RED)                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  🏭 Reactor Monitor Tab                              │   │
│  │  • Temperature chart      • Pressure gauge           │   │
│  │  • Power draw chart       • Temperature gauge        │   │
│  │  • Batch Energy Bar chart • Phase / Status text      │   │
│  │                                                      │   │
│  │  🚨 Alerts Tab                                       │   │
│  │  • Alert type + reason    • Severity gauge           │   │
│  │  • Alert history chart    • Pop-up notifications     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 How to Run

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- Git

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/<username>/edge-ai-group23.git
cd edge-ai-group23

# 2. Configure the broker (edit if instructor provides a different one)
cp .env.example .env
# Edit .env → set MQTT_BROKER, GROUP_ID, etc.

# 3. Build and start all services
docker-compose up --build

# 4. Open the dashboard
#    http://localhost:1880/ui
```

### Local Development (without Docker)

```bash
cd python

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac

pip install -r requirements.txt

# (Optional) Pre-train the model
python train_model.py --batches 200

# Run only the publisher
python mqtt_publisher.py

# OR run everything (publisher + AI + stats)
python main.py
```

---

## 📡 MQTT Topics Used

| Topic | Direction | Content |
|-------|-----------|---------|
| `sensors/group23/batch-reactor/data` | Publish | Raw sensor reading (JSON) |
| `alerts/group23/batch-reactor/status` | Publish | Anomaly alert details (JSON) |
| `sensors/group23/batch-reactor/stats` | Publish | Per-batch energy summary (JSON) |

### Sensor Data Payload Example
```json
{
  "timestamp":       "2024-01-15T10:23:45Z",
  "batch_id":        42,
  "cycle_phase":     "reaction",
  "step_in_batch":   7,
  "temperature_c":   91.3,
  "pressure_bar":    4.85,
  "power_kw":        22.4,
  "flow_rate_lpm":   15.0,
  "energy_kwh":      4.1833,
  "anomaly_injected": false,
  "group":           "group23",
  "project":         "batch-reactor"
}
```

### Alert Payload Example
```json
{
  "timestamp":    "2024-01-15T10:24:01Z",
  "batch_id":     43,
  "cycle_phase":  "heating",
  "anomaly_type": "CRITICAL",
  "rule_reason":  "Energy spike: 72.4 kWh > 60.0 kWh",
  "ml_anomaly":   true,
  "ml_score":     -0.3821,
  "severity":     2,
  "batch_energy": 72.4,
  "temperature":  88.1,
  "pressure":     4.2,
  "group":        "group23",
  "project":      "batch-reactor"
}
```

---

## 🤖 AI / Anomaly Detection Logic

### Layer 1 – Rule Engine

| Condition | Threshold | Alert Type |
|-----------|-----------|------------|
| Temperature | > 95 °C | CRITICAL |
| Pressure | > 6.0 bar | CRITICAL |
| Batch energy | > 60 kWh | CRITICAL |
| Batch energy | < 30 kWh (at discharge) | WARNING |

### Layer 2 – Isolation Forest

- **Algorithm**: `sklearn.ensemble.IsolationForest`
- **Features**: temperature, pressure, power, flow rate, cumulative energy
- **Contamination**: 35% (tuned to the 20% synthetic injection rate + buffer)
- **Auto-retrain**: every 10 completed batches using accumulated history
- **Model persistence**: saved to `python/models/` with joblib

---

## 📸 Results

> *(Add screenshots here after running the demo)*

---

## ⚠️ Challenges

1. **Multi-threaded MQTT** – paho-mqtt is not thread-safe; solved by using separate client instances per thread
2. **Unsupervised ML evaluation** – Isolation Forest has no ground-truth labels during live operation; solved by injecting known anomalies in the simulator
3. **Broker latency** – public HiveMQ occasionally drops messages; solved with QoS=1 and retained alerts
4. **Model cold-start** – first 5 batches have no ML model; rule engine covers this gap

---

## 🔮 Future Improvements

- [ ] Replace Isolation Forest with LSTM autoencoder for temporal anomaly detection
- [ ] Add OPC-UA data source for real PLC integration
- [ ] Implement Grafana + InfluxDB for long-term data storage
- [ ] ESP32 hardware sensor integration
- [ ] REST API for remote threshold configuration
- [ ] Telegram / email alert dispatch

---

## 📁 Repository Structure

```
project-root/
├── python/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config.py           # All configuration
│   ├── simulator.py        # Batch reactor sensor simulator
│   ├── anomaly_detector.py # Rule engine + Isolation Forest
│   ├── mqtt_client.py      # Thread-safe MQTT wrapper
│   ├── mqtt_publisher.py   # Stand-alone publisher (Task 3)
│   ├── main.py             # Orchestrator (publisher + AI + stats)
│   └── train_model.py      # Offline model training script
├── node-red/
│   ├── flows.json          # Node-RED dashboard flows
│   └── settings.js         # Node-RED configuration
├── docs/
│   └── report.md           # Technical report
├── docker-compose.yml
├── .env                    # Environment variables (not committed)
├── .env.example            # Template for .env
├── .gitignore
└── README.md
```
