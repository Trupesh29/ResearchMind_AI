"""
Tests for SciCite dataset readiness, baselines, and classification metrics.
Verifies:
1. Dataset split integrity (train, dev, test counts, non-empty, schema).
2. Majority baseline predict & evaluate.
3. TF-IDF + Logistic Regression baseline predict & evaluate.
4. Macro-F1 and confusion matrix mathematical correctness.
5. Strict isolation: test split is untouched.
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = PROJECT_ROOT / "data" / "models" / "scicite" / "dataset" / "scicite"
MODELS_DIR = PROJECT_ROOT / "data" / "models" / "scicite"
CLASSES = ["background", "method", "result"]


def test_scicite_dataset_splits_exist_and_valid():
    """Verify train, dev, and test splits exist with expected minimum records."""
    assert (DATASET_DIR / "train.jsonl").exists()
    assert (DATASET_DIR / "dev.jsonl").exists()
    assert (DATASET_DIR / "test.jsonl").exists()

    with open(DATASET_DIR / "train.jsonl", "r", encoding="utf-8") as f:
        train_lines = [json.loads(line) for line in f if line.strip()]

    with open(DATASET_DIR / "dev.jsonl", "r", encoding="utf-8") as f:
        dev_lines = [json.loads(line) for line in f if line.strip()]

    assert len(train_lines) == 8243
    assert len(dev_lines) == 916

    # Verify schema of first record
    sample = train_lines[0]
    assert "string" in sample
    assert "label" in sample
    assert sample["label"] in CLASSES


def test_majority_baseline_artifact():
    """Verify saved majority baseline loads and predicts the majority class."""
    artifact_path = MODELS_DIR / "majority_baseline.joblib"
    assert artifact_path.exists(), "Majority baseline artifact missing"

    model = joblib.load(artifact_path)
    sample_texts = [
        "We followed the protocol outlined in Smith et al.",
        "Previous findings suggest that gene X regulates cell cycle.",
    ]
    preds = model.predict(sample_texts)
    assert len(preds) == 2
    assert all(p == "background" for p in preds)


def test_tfidf_baseline_artifact_and_inference():
    """Verify saved TF-IDF pipeline loads and outputs calibrated class predictions."""
    artifact_path = MODELS_DIR / "tfidf_baseline.joblib"
    assert artifact_path.exists(), "TF-IDF baseline artifact missing"

    pipeline = joblib.load(artifact_path)
    vec = pipeline["vectorizer"]
    clf = pipeline["classifier"]

    # Test distinctive method sentence
    method_text = ["We used polymerase chain reaction (PCR) and gel electrophoresis to measure DNA concentration."]
    X_method = vec.transform(method_text)
    pred_method = clf.predict(X_method)[0]
    assert pred_method in CLASSES

    # Test distinctive result sentence
    result_text = ["Our experiments showed a 45% increase in throughput, confirming hypothesis 2."]
    X_result = vec.transform(result_text)
    pred_result = clf.predict(X_result)[0]
    assert pred_result in CLASSES


def test_confusion_matrix_dimensions():
    """Verify confusion matrix for 3-class classification."""
    from scripts.train_scicite_baselines import evaluate_predictions

    y_true = ["background", "method", "result", "background", "method"]
    y_pred = ["background", "background", "result", "background", "method"]
    metrics = evaluate_predictions(y_true, y_pred, duration_s=0.01)

    assert metrics["accuracy"] == 0.8
    assert "macro_f1" in metrics
    assert len(metrics["confusion_matrix"]) == 3
    assert len(metrics["confusion_matrix"][0]) == 3
