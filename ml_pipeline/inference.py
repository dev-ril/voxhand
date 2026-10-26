"""
VOXHAND Inference Engine
------------------------
Loads the serialized classifier, validates sensor input, executes real-time inference,
computes calibrated confidence scores, and enforces the >= 0.70 confidence rejection threshold.
"""

import os
import json
from typing import Dict, Any, List, Union, Tuple
import numpy as np
import joblib

CONFIDENCE_THRESHOLD = 0.70
REJECTION_MESSAGE = "Unrecognized gesture - please repeat gesture clearly."


class VoxhandInference:
    """
    Inference wrapper for VOXHAND smart sign language glove telemetry.
    """

    def __init__(self, model_path: str = None, metadata_path: str = None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_path = model_path or os.path.join(base_dir, "model.joblib")
        self.metadata_path = metadata_path or os.path.join(base_dir, "model_metadata.json")

        self.model = None
        self.metadata = {}
        self.classes = []
        self._load_or_initialize()

    def _load_or_initialize(self):
        """Loads model and metadata. If not found, triggers on-the-fly training."""
        if not os.path.exists(self.model_path):
            print(f"[VoxhandInference] Model file not found at {self.model_path}. Training initial model...")
            from .train_model import train_and_evaluate
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.model, self.metadata = train_and_evaluate(output_dir=base_dir)
        else:
            self.model = joblib.load(self.model_path)
            if os.path.exists(self.metadata_path):
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)

        self.classes = [str(c) for c in self.model.classes_]
        print(f"[VoxhandInference] Model loaded successfully. Classes: {self.classes}")

    @staticmethod
    def extract_feature_vector(sensor_input: Union[List[float], Dict[str, Any], np.ndarray]) -> np.ndarray:
        """
        Parses diverse input formats into an (11,) float32 vector:
        Format A: Direct list/array of 11 floats:
          [flex_thumb, flex_index, flex_middle, flex_ring, flex_pinky, ax, ay, az, gx, gy, gz]
        Format B: Structured JSON dict:
          {
            "flex": [f0, f1, f2, f3, f4],
            "accel": {"x": ax, "y": ay, "z": az} or [ax, ay, az],
            "gyro": {"x": gx, "y": gy, "z": gz} or [gx, gy, gz]
          }
        """
        if isinstance(sensor_input, (list, tuple, np.ndarray)):
            arr = np.array(sensor_input, dtype=np.float32).flatten()
            if len(arr) != 11:
                raise ValueError(f"Expected 11 features, got {len(arr)}")
            return arr

        if isinstance(sensor_input, dict):
            flex = sensor_input.get("flex", [0.0] * 5)
            if len(flex) != 5:
                raise ValueError(f"Expected 5 flex values, got {len(flex)}")

            accel = sensor_input.get("accel", {"x": 0.0, "y": 0.0, "z": 0.0})
            if isinstance(accel, dict):
                ax = float(accel.get("x", 0.0))
                ay = float(accel.get("y", 0.0))
                az = float(accel.get("z", 0.0))
            else:
                ax, ay, az = float(accel[0]), float(accel[1]), float(accel[2])

            gyro = sensor_input.get("gyro", {"x": 0.0, "y": 0.0, "z": 0.0})
            if isinstance(gyro, dict):
                gx = float(gyro.get("x", 0.0))
                gy = float(gyro.get("y", 0.0))
                gz = float(gyro.get("z", 0.0))
            else:
                gx, gy, gz = float(gyro[0]), float(gyro[1]), float(gyro[2])

            vec = [
                float(flex[0]), float(flex[1]), float(flex[2]), float(flex[3]), float(flex[4]),
                ax, ay, az,
                gx, gy, gz
            ]
            return np.array(vec, dtype=np.float32)

        raise TypeError(f"Unsupported sensor_input type: {type(sensor_input)}")

    def predict(
        self,
        sensor_input: Union[List[float], Dict[str, Any], np.ndarray],
        threshold: float = CONFIDENCE_THRESHOLD,
    ) -> Dict[str, Any]:
        """
        Runs ML inference on a sensor frame and applies rejection logic.

        Returns:
            Dict containing:
                - text: The translated sign text or the rejection message
                - predicted_label: The raw argmax class label
                - confidence: Float score between 0.00 and 1.00
                - status: "CONFIRMED" or "REJECTED"
                - is_rejected: bool
                - probabilities: Dict mapping each gesture class to its probability
        """
        vec = self.extract_feature_vector(sensor_input).reshape(1, -1)
        probas = self.model.predict_proba(vec)[0]
        max_idx = int(np.argmax(probas))
        predicted_class = str(self.classes[max_idx])
        confidence = float(probas[max_idx])

        prob_dict = {str(cls_name): round(float(probas[i]), 4) for i, cls_name in enumerate(self.classes)}

        # Rejection threshold logic:
        # 1. Confidence < threshold (0.70)
        # 2. Predicted class is REST_OR_NOISE (ambient noise or resting hand)
        is_low_confidence = confidence < threshold
        is_rest_noise = predicted_class == "REST_OR_NOISE"

        if is_low_confidence or is_rest_noise:
            status = "REJECTED"
            is_rejected = True
            display_text = REJECTION_MESSAGE
        else:
            status = "CONFIRMED"
            is_rejected = False
            display_text = str(predicted_class)

        return {
            "text": str(display_text),
            "predicted_label": str(predicted_class),
            "confidence": round(confidence, 4),
            "status": status,
            "is_rejected": is_rejected,
            "threshold": float(threshold),
            "probabilities": prob_dict,
        }


# Singleton instance for high-throughput gateway re-use
_GLOBAL_INFERENCE_ENGINE: Union[VoxhandInference, None] = None


def get_inference_engine() -> VoxhandInference:
    global _GLOBAL_INFERENCE_ENGINE
    if _GLOBAL_INFERENCE_ENGINE is None:
        _GLOBAL_INFERENCE_ENGINE = VoxhandInference()
    return _GLOBAL_INFERENCE_ENGINE


def predict_gesture(
    sensor_vector: Union[List[float], Dict[str, Any], np.ndarray],
    threshold: float = CONFIDENCE_THRESHOLD,
) -> Dict[str, Any]:
    """
    Standard interface function as requested in deliverables.
    Returns:
        {
           "text": "THANK YOU",
           "confidence": 0.94,
           "status": "CONFIRMED", ...
        }
    """
    engine = get_inference_engine()
    return engine.predict(sensor_vector, threshold=threshold)
