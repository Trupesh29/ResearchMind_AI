"""
ResearchMind AI — SciCite Baselines Training & Evaluation
Fits:
1. Majority-Class Baseline (predicts most frequent training class)
2. TF-IDF + Logistic Regression Baseline

Strict Isolation:
- Models and vocabularies are fit strictly on data/models/scicite/dataset/scicite/train.jsonl.
- Evaluation is executed strictly on dev.jsonl.
- The test split (test.jsonl) is NOT touched.
- Saves model artifacts to data/models/scicite/ and metrics to docs/scicite_baselines_report.json.
"""

import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.scicite_service import CLASSES, MajorityClassifier

DATASET_DIR = PROJECT_ROOT / "data" / "models" / "scicite" / "dataset" / "scicite"
MODELS_DIR = PROJECT_ROOT / "data" / "models" / "scicite"
REPORT_PATH = PROJECT_ROOT / "docs" / "scicite_baselines_report.json"


def load_split(split_name: str):
    path = DATASET_DIR / f"{split_name}.jsonl"
    texts = []
    labels = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            texts.append(obj["string"].strip())
            labels.append(obj["label"].strip())
    return texts, labels


def evaluate_predictions(y_true, y_pred, duration_s: float):
    acc = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, labels=CLASSES, average="macro")
    micro_f1 = f1_score(y_true, y_pred, labels=CLASSES, average="micro")
    weighted_f1 = f1_score(y_true, y_pred, labels=CLASSES, average="weighted")

    p, r, f1, sup = precision_recall_fscore_support(y_true, y_pred, labels=CLASSES)
    cm = confusion_matrix(y_true, y_pred, labels=CLASSES)

    per_class = {}
    for idx, c in enumerate(CLASSES):
        per_class[c] = {
            "precision": round(float(p[idx]), 4),
            "recall": round(float(r[idx]), 4),
            "f1_score": round(float(f1[idx]), 4),
            "support": int(sup[idx]),
        }

    return {
        "accuracy": round(float(acc), 4),
        "macro_f1": round(float(macro_f1), 4),
        "micro_f1": round(float(micro_f1), 4),
        "weighted_f1": round(float(weighted_f1), 4),
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
        "classes": CLASSES,
        "eval_duration_seconds": round(duration_s, 4),
    }


def main() -> int:
    print("=" * 70)
    print(" ResearchMind AI — SciCite Baselines Training (Majority & TF-IDF)")
    print("=" * 70)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    print("\n[1/4] Loading training and validation data...")
    train_texts, train_labels = load_split("train")
    dev_texts, dev_labels = load_split("dev")
    print(f"  - Training samples: {len(train_texts)} (Distribution: {dict(Counter(train_labels))})")
    print(f"  - Dev samples:      {len(dev_texts)} (Distribution: {dict(Counter(dev_labels))})")
    print("  - Test split (test.jsonl): ISOLATED and UNTOUCHED.")

    # 1. Majority-Class Baseline
    print("\n[2/4] Fitting Majority-Class Baseline...")
    t0 = time.perf_counter()
    majority_clf = MajorityClassifier().fit(train_texts, train_labels)
    majority_preds = majority_clf.predict(dev_texts)
    majority_metrics = evaluate_predictions(dev_labels, majority_preds, time.perf_counter() - t0)

    majority_artifact_path = MODELS_DIR / "majority_baseline.joblib"
    joblib.dump(majority_clf, majority_artifact_path)
    print(f"  - Majority Class: '{majority_clf.majority_class_}'")
    print(f"  - Dev Accuracy:   {majority_metrics['accuracy']:.4f}")
    print(f"  - Dev Macro-F1:   {majority_metrics['macro_f1']:.4f}")
    print(f"  - Saved artifact: {majority_artifact_path}")

    # 2. TF-IDF + Logistic Regression Baseline
    print("\n[3/4] Fitting TF-IDF + Logistic Regression Baseline...")
    t1 = time.perf_counter()
    vectorizer = TfidfVectorizer(
        max_features=15000,
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=2,
    )
    X_train = vectorizer.fit_transform(train_texts)
    X_dev = vectorizer.transform(dev_texts)

    lr_clf = LogisticRegression(
        C=1.0,
        max_iter=1000,
        random_state=42,
        class_weight="balanced",
        solver="lbfgs",
    )
    lr_clf.fit(X_train, train_labels)
    lr_preds = lr_clf.predict(X_dev)
    lr_metrics = evaluate_predictions(dev_labels, lr_preds, time.perf_counter() - t1)

    tfidf_pipeline = {
        "vectorizer": vectorizer,
        "classifier": lr_clf,
        "classes": CLASSES,
        "trained_on_samples": len(train_texts),
        "vocab_size": len(vectorizer.vocabulary_),
    }
    tfidf_artifact_path = MODELS_DIR / "tfidf_baseline.joblib"
    joblib.dump(tfidf_pipeline, tfidf_artifact_path)

    print(f"  - Vocabulary Size: {len(vectorizer.vocabulary_)}")
    print(f"  - Dev Accuracy:    {lr_metrics['accuracy']:.4f}")
    print(f"  - Dev Macro-F1:    {lr_metrics['macro_f1']:.4f}")
    print(f"  - Saved artifact:  {tfidf_artifact_path}")
    print("\n  Per-class metrics:")
    for c, stats in lr_metrics["per_class"].items():
        print(f"    {c:12s}: P={stats['precision']:.4f}, R={stats['recall']:.4f}, F1={stats['f1_score']:.4f}")

    # 3. Save Summary Report
    print("\n[4/4] Writing Baselines Report...")
    report = {
        "workstream": "scicite_baselines",
        "dataset": "allenai/scicite",
        "splits_used": {"train_count": len(train_texts), "dev_count": len(dev_texts), "test_touched": False},
        "majority_baseline": {
            "model_type": "MajorityClassifier",
            "majority_class": majority_clf.majority_class_,
            "metrics": majority_metrics,
            "artifact_file": str(majority_artifact_path.relative_to(PROJECT_ROOT)),
        },
        "tfidf_baseline": {
            "model_type": "TfidfVectorizer + LogisticRegression",
            "hyperparameters": {
                "max_features": 15000,
                "ngram_range": [1, 2],
                "sublinear_tf": True,
                "C": 1.0,
                "class_weight": "balanced",
                "random_state": 42,
            },
            "vocab_size": len(vectorizer.vocabulary_),
            "metrics": lr_metrics,
            "artifact_file": str(tfidf_artifact_path.relative_to(PROJECT_ROOT)),
        },
        "comparison": {
            "accuracy_delta": round(lr_metrics["accuracy"] - majority_metrics["accuracy"], 4),
            "macro_f1_delta": round(lr_metrics["macro_f1"] - majority_metrics["macro_f1"], 4),
            "baseline_surpassed": lr_metrics["macro_f1"] > majority_metrics["macro_f1"],
        },
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"  - Saved complete baselines report to {REPORT_PATH}")
    print("\n" + "=" * 70)
    print(" BASELINE TRAINING & EVALUATION COMPLETED SUCCESSFULLY")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
