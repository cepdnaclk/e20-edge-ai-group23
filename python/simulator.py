"""
simulator.py – Simulates a Batch Reactor sensor data stream.

Each "batch cycle" progresses through four phases:
  1. Heating  – energy rises, temperature climbs
  2. Reaction – peak energy and temperature
  3. Cooling  – energy falls, temperature decreases
  4. Discharge – minimal energy, pressure drops

Anomalies are randomly injected to train/test the AI model:
  - Energy spike (faulty heating element / over-dosing)
  - Energy sag  (underperforming reaction / leak)
  - Pressure surge
  - Temperature runaway
"""

import math
import random
import time
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class SensorReading:
    timestamp:       str
    batch_id:        int
    cycle_phase:     str          # heating | reaction | cooling | discharge
    step_in_batch:   int
    temperature_c:   float        # °C
    pressure_bar:    float        # bar
    power_kw:        float        # instantaneous power draw
    flow_rate_lpm:   float        # coolant / feed flow (L/min)
    energy_kwh:      float        # cumulative energy this batch
    anomaly_injected: bool        # ground-truth label for evaluation

    def to_dict(self) -> dict:
        return asdict(self)


class BatchReactorSimulator:
    """
    Simulates one batch reactor running continuously.
    Call next_reading() at PUBLISH_INTERVAL_SEC cadence.
    """

    # Phase transition points (fraction of READINGS_PER_BATCH)
    PHASE_BOUNDARIES = [0.20, 0.50, 0.80, 1.00]
    PHASES           = ["heating", "reaction", "cooling", "discharge"]

    # Baseline power profile per phase (kW)
    BASELINE_POWER = {
        "heating":   18.0,
        "reaction":  22.0,
        "cooling":    8.0,
        "discharge":  3.0,
    }

    def __init__(self, readings_per_batch: int = 15, publish_interval_sec: int = 2):
        self.readings_per_batch   = readings_per_batch
        self.publish_interval_sec = publish_interval_sec
        self.batch_id             = 0
        self.step                 = 0
        self.cumulative_energy    = 0.0
        self._anomaly_type: Optional[str] = None

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _current_phase(self) -> str:
        fraction = self.step / self.readings_per_batch
        for i, boundary in enumerate(self.PHASE_BOUNDARIES):
            if fraction <= boundary:
                return self.PHASES[i]
        return self.PHASES[-1]

    def _phase_fraction(self, phase: str) -> float:
        """0→1 progress within the current phase."""
        boundaries = [0.0] + self.PHASE_BOUNDARIES
        idx        = self.PHASES.index(phase)
        lo         = boundaries[idx]
        hi         = boundaries[idx + 1]
        total_frac = self.step / self.readings_per_batch
        return max(0.0, min(1.0, (total_frac - lo) / (hi - lo)))

    def _maybe_inject_anomaly(self):
        """Randomly decide what anomaly (if any) to inject in this batch."""
        roll = random.random()
        if roll < 0.80:                          # 80 % of batches are anomalous
            self._anomaly_type = random.choice([
                "energy_spike",
                "energy_sag",
                "pressure_surge",
                "temp_runaway",
            ])
        else:
            self._anomaly_type = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def next_reading(self) -> SensorReading:
        import datetime

        # New batch?
        if self.step == 0:
            self.batch_id          += 1
            self.cumulative_energy  = 0.0
            self._maybe_inject_anomaly()

        phase          = self._current_phase()
        phase_progress = self._phase_fraction(phase)
        base_power     = self.BASELINE_POWER[phase]

        # ── Temperature model ──────────────────────────────────────────────────
        temp_profiles = {
            "heating":   lambda p: 25 + 65 * p,
            "reaction":  lambda p: 90 + 5 * math.sin(math.pi * p),
            "cooling":   lambda p: 90 - 55 * p,
            "discharge": lambda p: 35 - 10 * p,
        }
        temp = temp_profiles[phase](phase_progress)
        temp += random.gauss(0, 1.2)

        # ── Pressure model ─────────────────────────────────────────────────────
        pressure_profiles = {
            "heating":   lambda p: 1.0 + 3.0 * p,
            "reaction":  lambda p: 4.0 + 1.5 * math.sin(math.pi * p),
            "cooling":   lambda p: 5.5 - 2.5 * p,
            "discharge": lambda p: 3.0 - 2.0 * p,
        }
        pressure = pressure_profiles[phase](phase_progress)
        pressure += random.gauss(0, 0.1)

        # ── Flow rate model ────────────────────────────────────────────────────
        flow_profiles = {
            "heating":   lambda p: 5.0 + 10.0 * p,
            "reaction":  lambda p: 15.0,
            "cooling":   lambda p: 15.0 - 10.0 * p,
            "discharge": lambda p: 5.0,
        }
        flow = flow_profiles[phase](phase_progress)
        flow += random.gauss(0, 0.3)

        # ── Power draw (with possible anomaly injection) ───────────────────────
        power          = base_power + random.gauss(0, 1.0)
        anomaly_active = False

        if self._anomaly_type == "energy_spike":
            power         *= random.uniform(1.5, 2.2)
            anomaly_active = True
        elif self._anomaly_type == "energy_sag":
            power         *= random.uniform(0.3, 0.6)
            anomaly_active = True
        elif self._anomaly_type == "pressure_surge" and phase in ("reaction", "cooling"):
            pressure      += random.uniform(2.0, 3.5)
            anomaly_active = True
        elif self._anomaly_type == "temp_runaway" and phase in ("reaction",):
            temp          += random.uniform(15.0, 30.0)
            power         *= random.uniform(1.2, 1.6)
            anomaly_active = True

        # ── Clamp to physically plausible ranges ───────────────────────────────
        temp     = max(15.0,  min(150.0, temp))
        pressure = max(0.5,   min(12.0,  pressure))
        flow     = max(0.0,   min(30.0,  flow))
        power    = max(0.0,   min(80.0,  power))

        # ── Cumulative energy (kWh = kW × h) ───────────────────────────────────
        # Simulate each reading as 10 minutes of elapsed industrial time (10 min = 10/60 hours)
        simulated_step_hours = 10.0 / 60.0
        self.cumulative_energy += power * simulated_step_hours

        reading = SensorReading(
            timestamp        = datetime.datetime.utcnow().isoformat() + "Z",
            batch_id         = self.batch_id,
            cycle_phase      = phase,
            step_in_batch    = self.step,
            temperature_c    = round(temp,     2),
            pressure_bar     = round(pressure, 3),
            power_kw         = round(power,    3),
            flow_rate_lpm    = round(flow,     2),
            energy_kwh       = round(self.cumulative_energy, 4),
            anomaly_injected = anomaly_active,
        )

        # Advance step counter
        self.step = (self.step + 1) % self.readings_per_batch

        return reading
