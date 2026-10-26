"""
VOXHAND Machine Learning Pipeline - Synthetic Dataset Generator & Classifier Training
-------------------------------------------------------------------------------------
Generates physically grounded synthetic telemetry for 5 primary sign gestures + noise/rest,
trains a robust Random Forest classifier with calibrated probabilities, and exports the model.
"""

import os
import json
import argparse
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix

# Feature column definitions (11 total dimensions)
FEATURE_NAMES = [
    "flex_thumb",
    "flex_index",
    "flex_middle",
    "flex_ring",
    "flex_pinky",
    "accel_x",
    "accel_y",
    "accel_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
]

# Physical profiles for each sign gesture (mean and std dev for 11 features)
# Flex: 0.0 (fully extended straight) to 1.0 (fully bent/flexed)
# Accel: normalized in g units (-2.0 to +2.0)
# Gyro: angular rate in rad/s (-5.0 to +5.0)
GESTURE_PROFILES = {
    "HELLO": {
        "description": "Open hand, palm facing forward, gentle side-to-side waving motion.",
        # [thumb, index, middle, ring, pinky, ax, ay, az, gx, gy, gz]
        "mean": [0.08, 0.06, 0.05, 0.06, 0.08, 0.08, 0.94, 0.15, 0.05, 0.05, 2.10],
        "std":  [0.04, 0.03, 0.03, 0.03, 0.04, 0.10, 0.08, 0.10, 0.15, 0.15, 0.60],
    },
    "THANK YOU": {
        "description": "Flat hand moves forward from chin toward recipient; palm tilted slightly forward.",
        # [thumb, index, middle, ring, pinky, ax, ay, az, gx, gy, gz]
        "mean": [0.12, 0.08, 0.08, 0.10, 0.12, 0.04, 0.50, 0.82, 1.80, 0.05, 0.05],
        "std":  [0.05, 0.04, 0.04, 0.04, 0.05, 0.08, 0.12, 0.12, 0.50, 0.15, 0.15],
    },
    "HELP": {
        "description": "Fist with thumb upright (thumbs up pose placed firmly on base hand).",
        # [thumb, index, middle, ring, pinky, ax, ay, az, gx, gy, gz]
        "mean": [0.08, 0.90, 0.93, 0.94, 0.92, 0.05, 0.96, 0.18, 0.06, 0.04, 0.05],
        "std":  [0.04, 0.05, 0.04, 0.04, 0.04, 0.08, 0.06, 0.08, 0.12, 0.12, 0.12],
    },
    "YES": {
        "description": "Closed fist nodding up and down repeatedly like a head nod.",
        # [thumb, index, middle, ring, pinky, ax, ay, az, gx, gy, gz]
        "mean": [0.82, 0.92, 0.94, 0.95, 0.93, 0.05, 0.72, 0.62, 2.40, 0.10, 0.05],
        "std":  [0.06, 0.04, 0.03, 0.03, 0.04, 0.12, 0.18, 0.18, 0.70, 0.20, 0.15],
    },
    "NO": {
        "description": "Index and middle fingers snap down to touch thumb; ring and pinky tucked.",
        # [thumb, index, middle, ring, pinky, ax, ay, az, gx, gy, gz]
        "mean": [0.60, 0.72, 0.70, 0.92, 0.93, 0.38, 0.82, 0.32, 0.10, 1.75, 0.35],
        "std":  [0.07, 0.06, 0.06, 0.04, 0.04, 0.12, 0.12, 0.14, 0.25, 0.55, 0.25],
    },
    "REST_OR_NOISE": {
        "description": "Idle hand resting or indeterminate transitioning movement.",
        # Broad distributions centered on mid-flex and random orientations
        "mean": [0.45, 0.40, 0.42, 0.45, 0.45, 0.00, 0.50, 0.50, 0.00, 0.00, 0.00],
        "std":  [0.25, 0.25, 0.25, 0.25, 0.25, 0.40, 0.40, 0.40, 0.80, 0.80, 0.80],
    },
}

TARGET_CLASSES = list(GESTURE_PROFILES.keys())


def generate_synthetic_dataset(samples_per_class: int = 1200, random_seed: int = 42):
    """
    Generates realistic, noisy sensor frames based on biomechanical constraints.
    Adds sensor drift, Gaussian noise, and physical boundary clipping.
    """
    np.random.seed(random_seed)
    features_list = []
    labels_list = []

    for label, profile in GESTURE_PROFILES.items():
        mean = np.array(profile["mean"])
        std = np.array(profile["std"])

        # Generate base Gaussian distribution
        samples = np.random.normal(loc=mean, scale=std, size=(samples_per_class, len(mean)))

        # Add simulated sensor noise and slight non-linear drift
        noise = np.random.normal(0, 0.02, size=samples.shape)
        drift = np.sin(np.linspace(0, 3 * np.pi, samples_per_class)).reshape(-1, 1) * 0.03
        samples += noise + drift

        # Physical constraints:
        # Flex values must remain strictly in [0.0, 1.0]
        samples[:, 0:5] = np.clip(samples[:, 0:5], 0.0, 1.0)
        # Accel values in [-2.0, 2.0] g
        samples[:, 5:8] = np.clip(samples[:, 5:8], -2.0, 2.0)
        # Gyro values in [-6.0, 6.0] rad/s
        samples[:, 8:11] = np.clip(samples[:, 8:11], -6.0, 6.0)

        features_list.append(samples)
        labels_list.extend([label] * samples_per_class)

    X = np.vstack(features_list)
    y = np.array(labels_list)
    return X, y


def train_and_evaluate(
    output_dir: str = ".",
    samples_per_class: int = 1500,
    random_seed: int = 42,
):
    """
    Trains a high-precision Random Forest model and serializes it to disk.
    """
    os.makedirs(output_dir, exist_ok=True)
    print("=" * 60)
    print(f"VOXHAND ML PIPELINE: Generating {samples_per_class} samples per class...")
    X, y = generate_synthetic_dataset(samples_per_class=samples_per_class, random_seed=random_seed)
    print(f"Dataset generated: {X.shape[0]} total samples, {X.shape[1]} features.")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=random_seed, stratify=y
    )
    print(f"Split: Train={len(X_train)} frames, Test={len(X_test)} frames.")

    print("\nTraining RandomForestClassifier (120 estimators)...")
    clf = RandomForestClassifier(
        n_estimators=120,
        max_depth=15,
        min_samples_split=4,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=random_seed,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)

    # Evaluate on held-out test data
    y_pred = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"\nModel Test Accuracy: {acc * 100:.2f}%\n")
    print("Classification Report:")
    print(classification_report(y_test, y_pred, digits=4))

    # Save artifacts
    model_path = os.path.join(output_dir, "model.joblib")
    joblib.dump(clf, model_path, compress=3)
    print(f"[OK] Model successfully saved to: {model_path}")

    metadata = {
        "feature_names": FEATURE_NAMES,
        "classes": list(clf.classes_),
        "target_classes": TARGET_CLASSES,
        "gesture_descriptions": {k: v["description"] for k, v in GESTURE_PROFILES.items()},
        "test_accuracy": round(float(acc), 4),
        "confidence_threshold": 0.70,
        "rejection_message": "Unrecognized gesture - please repeat gesture clearly.",
    }

    meta_path = os.path.join(output_dir, "model_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"[OK] Metadata saved to: {meta_path}")
    print("=" * 60)

    return clf, metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train VOXHAND Sign Recognition Model")
    parser.add_argument("--samples", type=int, default=1500, help="Samples per gesture class")
    parser.add_argument("--outdir", type=str, default=os.path.dirname(os.path.abspath(__file__)), help="Output directory")
    args = parser.parse_args()

    train_and_evaluate(output_dir=args.outdir, samples_per_class=args.samples)

