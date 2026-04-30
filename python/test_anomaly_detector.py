import unittest
import config
from anomaly_detector import AnomalyDetector

class TestAnomalyDetector(unittest.TestCase):
    def setUp(self):
        # Initialize the detector
        self.detector = AnomalyDetector()
        
    def test_normal_reading(self):
        reading = {
            "temperature_c": 50.0,
            "pressure_bar": 3.0,
            "energy_kwh": 10.0,
            "cycle_phase": "heating",
            "power_kw": 20.0,
            "flow_rate_lpm": 15.0
        }
        batch_energy = 10.0
        is_anomaly, reason, severity = self.detector._check_rules(reading, batch_energy)
        self.assertFalse(is_anomaly)
        self.assertEqual(severity, 0)
        
    def test_temperature_runaway(self):
        reading = {
            "temperature_c": config.TEMPERATURE_MAX_C + 5.0,
            "pressure_bar": 3.0,
            "cycle_phase": "heating"
        }
        batch_energy = 10.0
        is_anomaly, reason, severity = self.detector._check_rules(reading, batch_energy)
        self.assertTrue(is_anomaly)
        self.assertEqual(severity, 2)
        self.assertIn("Temperature runaway", reason)

    def test_pressure_surge(self):
        reading = {
            "temperature_c": 50.0,
            "pressure_bar": config.PRESSURE_MAX_BAR + 1.0,
            "cycle_phase": "heating"
        }
        batch_energy = 10.0
        is_anomaly, reason, severity = self.detector._check_rules(reading, batch_energy)
        self.assertTrue(is_anomaly)
        self.assertEqual(severity, 2)
        self.assertIn("Pressure surge", reason)

    def test_energy_spike(self):
        reading = {
            "temperature_c": 50.0,
            "pressure_bar": 3.0,
            "cycle_phase": "heating"
        }
        batch_energy = config.ENERGY_UPPER_THRESHOLD + 5.0
        is_anomaly, reason, severity = self.detector._check_rules(reading, batch_energy)
        self.assertTrue(is_anomaly)
        self.assertEqual(severity, 2)
        self.assertIn("Energy spike", reason)

    def test_energy_sag_at_discharge(self):
        reading = {
            "temperature_c": 50.0,
            "pressure_bar": 3.0,
            "cycle_phase": "discharge"
        }
        # batch_energy needs to be > 0 but < config.ENERGY_LOWER_THRESHOLD
        batch_energy = config.ENERGY_LOWER_THRESHOLD - 5.0
        is_anomaly, reason, severity = self.detector._check_rules(reading, batch_energy)
        self.assertTrue(is_anomaly)
        self.assertEqual(severity, 1)
        self.assertIn("Energy sag", reason)

if __name__ == '__main__':
    unittest.main()
