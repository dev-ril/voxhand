"""
VOXHAND End-to-End Test Suite
-----------------------------
Verifies:
  1. Synthetic data generator bounds and shape
  2. Model serialization and inference
  3. Rejection threshold logic (< 0.70 confidence or REST_OR_NOISE)
  4. Mock hardware frame formatting
  5. FastAPI REST route logic (Health, Gestures, Predict, Simulate)
"""

import os
import sys
import unittest
import asyncio
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ml_pipeline.train_model import generate_synthetic_dataset, GESTURE_PROFILES
from ml_pipeline.inference import get_inference_engine, predict_gesture, CONFIDENCE_THRESHOLD, REJECTION_MESSAGE
from firmware.mock_esp32_streamer import MockESP32Glove
from backend.app import (
    health_check,
    list_gestures,
    predict_single_frame,
    simulate_gesture,
    TelemetryPayload,
    SimulateRequest,
)


class TestVoxhandMLPipeline(unittest.TestCase):
    """Tests ML data synthesis, model inference, and rejection logic."""

    def test_synthetic_dataset_bounds(self):
        X, y = generate_synthetic_dataset(samples_per_class=100, random_seed=42)
        self.assertEqual(X.shape[0], 100 * len(GESTURE_PROFILES))
        self.assertEqual(X.shape[1], 11)

        # Flex values must strictly be within [0.0, 1.0]
        flex_matrix = X[:, 0:5]
        self.assertTrue(np.all(flex_matrix >= 0.0), "Flex values below 0.0 detected")
        self.assertTrue(np.all(flex_matrix <= 1.0), "Flex values above 1.0 detected")

        # Accel in [-2.0, 2.0]
        accel_matrix = X[:, 5:8]
        self.assertTrue(np.all(accel_matrix >= -2.0) and np.all(accel_matrix <= 2.0))

        # Gyro in [-6.0, 6.0]
        gyro_matrix = X[:, 8:11]
        self.assertTrue(np.all(gyro_matrix >= -6.0) and np.all(gyro_matrix <= 6.0))

    def test_inference_gestures(self):
        engine = get_inference_engine()
        self.assertIsNotNone(engine.model)

        test_cases = [
            ("HELLO", [0.08, 0.06, 0.05, 0.06, 0.08, 0.08, 0.94, 0.15, 0.05, 0.05, 2.10]),
            ("THANK YOU", [0.12, 0.08, 0.08, 0.10, 0.12, 0.04, 0.50, 0.82, 1.80, 0.05, 0.05]),
            ("HELP", [0.08, 0.90, 0.93, 0.94, 0.92, 0.05, 0.96, 0.18, 0.06, 0.04, 0.05]),
            ("YES", [0.82, 0.92, 0.94, 0.95, 0.93, 0.05, 0.72, 0.62, 2.40, 0.10, 0.05]),
            ("NO", [0.60, 0.72, 0.70, 0.92, 0.93, 0.38, 0.82, 0.32, 0.10, 1.75, 0.35]),
        ]

        for expected_gesture, feature_vector in test_cases:
            res = predict_gesture(feature_vector)
            self.assertEqual(res["predicted_label"], expected_gesture)
            self.assertEqual(res["status"], "CONFIRMED")
            self.assertFalse(res["is_rejected"])
            self.assertGreaterEqual(res["confidence"], CONFIDENCE_THRESHOLD)
            self.assertEqual(res["text"], expected_gesture)

    def test_rejection_logic_on_noise(self):
        # Ambient noise / resting hand vector
        noise_vector = [0.45, 0.40, 0.42, 0.45, 0.45, 0.00, 0.50, 0.50, 0.00, 0.00, 0.00]
        res = predict_gesture(noise_vector)

        self.assertEqual(res["status"], "REJECTED")
        self.assertTrue(res["is_rejected"])
        self.assertEqual(res["text"], REJECTION_MESSAGE)

    def test_rejection_logic_on_forced_high_threshold(self):
        # Test that raising threshold to 0.9999 forces rejection
        vector = [0.08, 0.06, 0.05, 0.06, 0.08, 0.08, 0.94, 0.15, 0.05, 0.05, 2.10]
        res = predict_gesture(vector, threshold=0.9999)
        if res["confidence"] < 0.9999:
            self.assertEqual(res["status"], "REJECTED")
            self.assertEqual(res["text"], REJECTION_MESSAGE)


class TestMockHardwareStreamer(unittest.TestCase):
    """Tests synthetic frame generation adhering to physical glove schema."""

    def test_mock_frame_structure(self):
        glove = MockESP32Glove(current_gesture="HELLO")
        frame = glove.generate_frame()

        self.assertIn("flex", frame)
        self.assertIn("accel", frame)
        self.assertIn("gyro", frame)
        self.assertIn("timestamp", frame)

        self.assertEqual(len(frame["flex"]), 5)
        for f in frame["flex"]:
            self.assertGreaterEqual(f, 0.0)
            self.assertLessEqual(f, 1.0)

        for axis in ["x", "y", "z"]:
            self.assertIn(axis, frame["accel"])
            self.assertIn(axis, frame["gyro"])

    def test_mock_auto_cycle_transitions(self):
        glove = MockESP32Glove(current_gesture="AUTO")
        initial_gesture = glove.get_current_gesture_name()
        self.assertEqual(initial_gesture, "HELLO")


class TestBackendGatewayRoutes(unittest.TestCase):
    """Tests FastAPI REST endpoint handlers directly."""

    def test_health_route(self):
        data = asyncio.run(health_check())
        self.assertEqual(data["status"], "healthy")
        self.assertIn("HELLO", data["classes"])
        self.assertEqual(data["confidence_threshold"], 0.70)

    def test_gestures_route(self):
        data = asyncio.run(list_gestures())
        self.assertIn("HELLO", data["classes"])
        self.assertIn("THANK YOU", data["classes"])
        self.assertEqual(data["confidence_threshold"], 0.70)

    def test_predict_route(self):
        payload = TelemetryPayload(
            flex=[0.12, 0.08, 0.08, 0.10, 0.12],
            accel={"x": 0.04, "y": 0.50, "z": 0.82},
            gyro={"x": 1.80, "y": 0.05, "z": 0.05},
            timestamp=1714523456,
        )
        res = asyncio.run(predict_single_frame(payload))
        self.assertEqual(res["predicted_label"], "THANK YOU")
        self.assertEqual(res["status"], "CONFIRMED")
        self.assertGreaterEqual(res["confidence"], 0.70)

    def test_simulate_route(self):
        req = SimulateRequest(gesture="HELP")
        res = asyncio.run(simulate_gesture(req))
        self.assertIn("simulation", res)
        self.assertIn("inference", res)
        self.assertEqual(res["inference"]["predicted_label"], "HELP")
        self.assertEqual(res["inference"]["status"], "CONFIRMED")


if __name__ == "__main__":
    unittest.main()

