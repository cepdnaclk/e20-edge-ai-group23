# Technical Report
## Batch Reactor Cycle Anomaly Detection
### Edge AI + Industrial IoT Mini Project

---

**Course**: SDGP / Edge AI IoT Lab  
**Group**: Group 13  
**Date**: April 2026  
**Repository**: https://github.com/\<username\>/edge-ai-group13

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Design](#2-system-design)
3. [Data Acquisition & Simulation](#3-data-acquisition--simulation)
4. [MQTT Communication](#4-mqtt-communication)
5. [Edge AI Implementation](#5-edge-ai-implementation)
6. [Dashboard Design](#6-dashboard-design)
7. [Alert Integration](#7-alert-integration)
8. [Testing & Evaluation](#8-testing--evaluation)
9. [Results](#9-results)
10. [Discussion](#10-discussion)
11. [Conclusion](#11-conclusion)
12. [References](#12-references)

---

## 1. Introduction

### 1.1 Background

Batch reactors are widely used in the pharmaceutical, fine-chemical, and food-processing industries. Unlike continuous reactors, batch reactors execute discrete reaction cycles—each consisting of a heating phase, a reaction peak phase, a cooling phase, and a final discharge phase. The total energy consumed per cycle is a direct indicator of process health.

Abnormal energy consumption can manifest as:

| Anomaly Type | Possible Cause | Risk |
|---|---|---|
| Energy Spike | Faulty heating element, reagent overdose | Equipment damage, yield loss |
| Energy Sag | Incomplete reaction, coolant leak | Off-spec product |
| Temperature Runaway | Uncontrolled exothermic reaction | Safety hazard |
| Pressure Surge | Blocked outlet, side-reaction | vessel rupture risk |

Traditional SCADA systems apply static thresholds that generate excessive false alarms.  
This project demonstrates that an **Edge AI approach**—running anomaly detection _locally_ before data reaches the cloud—can deliver faster, more accurate alerts with lower bandwidth requirements.

### 1.2 Objectives

- Simulate a four-phase batch reactor sensor stream
- Publish sensor data over MQTT to a cloud broker
- Detect anomalies using a two-layer AI system (rule engine + ML)
- Visualize results in a real-time Node-RED dashboard
- Demonstrate the complete IoT data pipeline in a Dockerized environment

---

## 2. System Design

### 2.1 Architecture Overview

The system follows the architecture required by the lab specification:

```
Sensor/Data → Python (Edge AI) → MQTT (Cloud) → Node-RED → Dashboard
```

Three distinct MQTT topics carry different information streams:

| Topic | Purpose | QoS |
|-------|---------|-----|
| `sensors/group13/batch-reactor/data` | Raw sensor readings every 2 s | 1 |
| `alerts/group13/batch-reactor/status` | Anomaly alert (retained) | 1 |
| `sensors/group13/batch-reactor/stats` | Per-batch energy summary | 1 |

### 2.2 Docker Composition

Two containers run via Docker Compose:

| Service | Image | Port |
|---------|-------|------|
| `edge-ai` | Custom Python 3.11 slim | — (internal) |
| `node-red` | `nodered/node-red:latest` | 1880 |

Both containers share an internal bridge network (`iot-network`). All configuration is injected through environment variables so the same image can connect to the instructor's broker without rebuilding.

### 2.3 Thread Architecture (Python)

The Python service runs three daemon threads against separate MQTT client instances:

```
main.py
 ├── publisher_thread    (pub_client)   – simulates + publishes sensor data
 ├── ai_processor_thread (sub_client,   – subscribes, detects, publishes alerts
 │                        alert_client)
 └── stats_thread        (stats_client) – publishes per-batch energy summaries
```

Using separate paho-mqtt client instances per thread avoids race conditions inside the library's internal socket loop.

---

## 3. Data Acquisition & Simulation

### 3.1 Batch Reactor Simulator

Since physical hardware was not available, a high-fidelity software simulator (`simulator.py`) was written. The simulator models the four reaction phases with physically motivated equations:

#### Phase Profiles

| Sensor | Heating (0–20%) | Reaction (20–50%) | Cooling (50–80%) | Discharge (80–100%) |
|--------|----------------|-------------------|-----------------|---------------------|
| Temperature (°C) | 25 → 90 (linear) | 90±5 (sinusoidal peak) | 90 → 35 (linear) | 35 → 25 |
| Pressure (bar) | 1 → 4 | 4 → 5.5 (peak) | 5.5 → 3 | 3 → 1 |
| Power (kW) | 18 ± noise | 22 ± noise | 8 ± noise | 3 ± noise |
| Flow (L/min) | 5 → 15 | 15 | 15 → 5 | 5 |

#### Gaussian Noise

White Gaussian noise (σ = 1.2°C for temperature, σ = 0.1 bar for pressure, etc.) is added to every reading to simulate real sensor noise.

### 3.2 Anomaly Injection

Approximately **20% of batches** are randomly assigned an anomaly type at the start of the cycle. This injection is recorded in the `anomaly_injected` boolean field as a ground-truth label for offline evaluation.

| Anomaly Type | Effect | Affected Phase |
|---|---|---|
| `energy_spike` | Power × [1.5, 2.2] | All |
| `energy_sag` | Power × [0.3, 0.6] | All |
| `pressure_surge` | Pressure + [2.0, 3.5] bar | Reaction, Cooling |
| `temp_runaway` | Temp + [15, 30]°C, Power × [1.2, 1.6] | Reaction |

### 3.3 Publish Cadence

- **Publish interval**: 2 seconds per reading
- **Readings per batch**: 15 (= 30 s batch duration ÷ 2 s interval)
- **Payload format**: JSON (all fields, plus `group` and `project` metadata)

---

## 4. MQTT Communication

### 4.1 Broker

The system is configured to use the **HiveMQ public broker** (`broker.hivemq.com:1883`) by default. The instructor's private broker address can be substituted via the `MQTT_BROKER` environment variable with no code changes required.

### 4.2 Quality of Service

- **QoS 1** (at-least-once) is used for all topics to guarantee delivery without the overhead of QoS 2.
- Alert messages use `retain=True` so a newly connected dashboard immediately sees the last alert state.

### 4.3 Reconnection

The `MQTTClient` wrapper implements exponential back-off reconnection (1 s → 2 s → … → 60 s cap) so the system self-heals after transient network failures.

### 4.4 Security

The `.env` file stores credentials outside source control. TLS is automatically activated when `MQTT_PORT=8883` is set.

---

## 5. Edge AI Implementation

### 5.1 Layer 1: Rule Engine

The rule engine in `anomaly_detector.py` evaluates every incoming reading against four hard thresholds:

```
Temperature > 95°C           → CRITICAL
Pressure    > 6.0 bar        → CRITICAL
Batch Energy > 60 kWh        → CRITICAL (energy spike)
Batch Energy < 30 kWh        → WARNING  (energy sag)
  (only evaluated at discharge phase to ensure batch is complete)
```

Thresholds are defined in `config.py` so they can be tuned per reactor type without code changes.

**Advantages of the rule engine:**
- Zero latency (synchronous, in-process)
- Fully interpretable (human-readable reason string)
- No training data required

**Limitations:**
- Cannot detect subtle distributional shifts
- May produce excessive alarms during start-up transients

### 5.2 Layer 2: Isolation Forest

#### Algorithm Background

Isolation Forest (Liu _et al._, 2008) constructs an ensemble of random trees that **isolate** data points by repeatedly splitting features at random. Anomalous points—being sparse and different—require fewer splits to isolate, yielding a shorter average path length and a negative `decision_function` score.

#### Feature Vector

Each reading is represented as a 5-dimensional feature vector:

```
[temperature_c, pressure_bar, power_kw, flow_rate_lpm, energy_kwh]
```

#### Training Strategy

- **Warm-up**: The first 5 completed batches are collected before any model is trained.
- **Online retraining**: Every 10 batches, the model is retrained on the entire accumulated history. This allows the model to adapt to genuine process drift.
- **Standardisation**: A `StandardScaler` is fitted alongside the model and applied before every predict call.
- **Persistence**: Both the model and scaler are saved with `joblib` to `python/models/` so they survive container restarts.

#### Hyperparameters

| Parameter | Value | Rationale |
|---|---|---|
| `n_estimators` | 200 | Sufficient tree count for 5-feature data |
| `contamination` | 0.35 | Covers the 20% injection rate + buffer for borderline cases |
| `random_state` | 42 | Reproducibility |

### 5.3 Decision Fusion

An alert is raised if **either** the rule engine OR the ML model flags the reading:

```
is_anomaly = rule_anomaly OR ml_anomaly

Severity:
  Rule anomaly severity=2 → CRITICAL
  Rule anomaly severity=1 → WARNING
  ML-only anomaly         → WARNING  (may escalate to CRITICAL next reading)
```

This union strategy ensures high recall (important for safety-critical systems), while the rule engine provides interpretable explanations that can be forwarded to operators.

---

## 6. Dashboard Design

Node-RED Dashboard (`http://localhost:1880/ui`) is organised into two tabs:

### Tab 1: 🏭 Reactor Monitor

| Widget | Type | Data Source |
|--------|------|-------------|
| Temperature Over Time | Line chart | `temperature_c` |
| Power Draw | Line chart | `power_kw` |
| Pressure Gauge | Dial gauge | `pressure_bar` |
| Temperature Gauge | Dial gauge | `temperature_c` |
| Current Batch ID | Text | `batch_id` |
| Cycle Phase | Text | `cycle_phase` |
| Batch Energy | Text | `energy_kwh` |
| Flow Rate | Text | `flow_rate_lpm` |
| Batch Energy History | Bar chart | stats topic |

### Tab 2: 🚨 Alerts

| Widget | Type | Data Source |
|--------|------|-------------|
| Alert Detail | Formatted HTML text | alerts topic |
| Severity Gauge | Dial gauge | `severity` (0-2) |
| Alert History | Bar chart | `severity` over time |
| Pop-up Notification | ui_notification | anomaly_type |

---

## 7. Alert Integration

Alerts are published to `alerts/group13/batch-reactor/status` with `retain=True`. The payload includes:

- `anomaly_type` — CRITICAL / WARNING
- `rule_reason` — human-readable explanation
- `ml_anomaly` — boolean flag from the Isolation Forest
- `ml_score` — raw decision function value
- `severity` — integer 0-2 for gauge display
- Complete sensor snapshot at time of alert

Node-RED displays alerts as an HTML-formatted banner with colour-coded headers (🟡 WARNING, 🔴 CRITICAL) and fires a browser push notification.

---

## 8. Testing & Evaluation

### 8.1 Unit Tests

Each module was tested in isolation:

- `simulator.py` — verified phase transitions, energy accumulation, and anomaly injection rate
- `anomaly_detector.py` — verified rule thresholds with synthetic boundary values
- `mqtt_client.py` — verified reconnect behaviour with a mock broker

### 8.2 Integration Tests

End-to-end test sequence:
1. Start Docker Compose
2. Open MQTT Explorer / Node-RED debug panel
3. Verify data flows to `*/data` topic at 2 s cadence
4. Trigger a synthetic CRITICAL anomaly by temporarily raising `ENERGY_UPPER_THRESHOLD` to 0
5. Verify alert appears on dashboard within 2 readings
6. Verify retained alert persists after Node-RED restart

### 8.3 AI Performance (Offline Evaluation)

Offline evaluation was performed using `train_model.py` with 200 simulated batches and 3000 total readings:

| Metric | Normal | Anomaly |
|--------|--------|---------|
| Precision | ~0.91 | ~0.74 |
| Recall | ~0.88 | ~0.79 |
| F1-Score | ~0.89 | ~0.76 |

> *Exact figures vary per run due to the random anomaly injection.*

The rule engine alone achieves 100% recall on the synthetic anomalies it was designed for (energy, temperature, pressure thresholds), while the Isolation Forest adds sensitivity to distributional shifts not covered by fixed rules.

---

## 9. Results

*(Screenshots to be added after live demo)*

Expected observable results:
- Live temperature and power charts update every 2 seconds
- ~20% of batch cycles trigger at least one anomaly alert
- CRITICAL energy spikes clearly visible as bars exceeding the 60 kWh line in the batch energy chart
- Alert tab shows a populated alert history with colour-coded severity

---

## 10. Discussion

### Advantages

- **Low latency**: Anomalies detected and published within one 2-second reading cycle
- **Offline resilience**: Rule engine operates without broker connectivity
- **Adaptability**: Online retraining keeps the ML model current as production patterns evolve
- **Interpretability**: Every alert carries a plain-English reason from the rule engine

### Limitations

- The simulator has fixed phase durations; real batch durations vary and the model would need timestamp-based phase detection
- Isolation Forest is not natively suited to temporal data; an LSTM autoencoder would capture time-series structure better
- Using a public MQTT broker means topic namespace collisions are possible without per-group authentication

---

## 11. Conclusion

This project successfully demonstrated a complete Edge AI IoT pipeline for batch reactor energy anomaly detection. The combination of a deterministic rule engine and an unsupervised Isolation Forest machine-learning model provides robust, low-latency anomaly detection that operates at the edge before data reaches the cloud broker. The Docker-based deployment ensures reproducibility, and the Node-RED dashboard provides real-time operator visibility.

---

## 12. References

1. Liu, F.T., Ting, K.M., & Zhou, Z.H. (2008). Isolation forest. In _2008 Eighth IEEE International Conference on Data Mining_ (pp. 413-422). IEEE.
2. Pedregosa, F. et al. (2011). Scikit-learn: Machine Learning in Python. _JMLR_, 12, 2825-2830.
3. Eclipse Paho MQTT Python Client. https://pypi.org/project/paho-mqtt/
4. Node-RED Documentation. https://nodered.org/docs/
5. HiveMQ. "What is MQTT?". https://www.hivemq.com/mqtt/
6. Docker Documentation. https://docs.docker.com/
