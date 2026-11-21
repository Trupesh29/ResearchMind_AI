"""
ResearchMind AI — SciCite Evaluation CLI
Loads saved SciCite model artifacts (majority baseline, TF-IDF baseline, or DistilBERT model)
and evaluates them against validation (dev) or held-out (test) data.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import joblib
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.scicite_service import CLASSES, MajorityClassifier

DATASET_DIR = PROJECT_ROOT / "data" / "models" / "scicite" / "dataset" / "scicite"
MODELS_DIR = PROJECT_ROOT / "data" / "models" / "scicite"


def load_split(split_name: str):
    path = DATASET_DIR / f"{split_name}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"Split file not found: {path}")
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate SciCite citation classifier models")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--baseline",
        choices=["majority", "tfidf"],
        help="Evaluate a baseline model (majority or tfidf)",
    )
    group.add_argument(
        "--model",
        type=str,
        help="Path or name of trained model (e.g. distilbert)",
    )
    parser.add_argument(
        "--split",
        choices=["dev", "test"],
        default="dev",
        help="Dataset split to evaluate on (default: dev; test reserved for Week 4)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional path to save JSON metrics report",
    )
    args = parser.parse_args()

    print("=" * 70)
    print(f" ResearchMind AI — SciCite Model Evaluation (Split: {args.split})")
    print("=" * 70)

    texts, labels = load_split(args.split)
    print(f"Loaded {len(texts)} samples from {args.split}.jsonl")
    print(f"Class distribution: {dict(Counter(labels))}")

    preds = []
    model_name = ""

    if args.baseline == "majority":
        artifact_path = MODELS_DIR / "majority_baseline.joblib"
        if not artifact_path.exists():
            print(f"[ERROR] Artifact not found at {artifact_path}. Run scripts/train_scicite_baselines.py first.")
            return 1
        clf = joblib.load(artifact_path)
        preds = clf.predict(texts)
        model_name = "Majority-Class Baseline"

    elif args.baseline == "tfidf":
        artifact_path = MODELS_DIR / "tfidf_baseline.joblib"
        if not artifact_path.exists():
            print(f"[ERROR] Artifact not found at {artifact_path}. Run scripts/train_scicite_baselines.py first.")
            return 1
        pipeline = joblib.load(artifact_path)
        vec = pipeline["vectorizer"]
        clf = pipeline["classifier"]
        X = vec.transform(texts)
        preds = clf.predict(X)
        model_name = "TF-IDF + LogisticRegression Baseline"

    elif args.model:
        # Load DistilBERT model
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        model_path = Path(args.model)
        if not model_path.is_absolute() and not model_path.exists():
            model_path = MODELS_DIR / args.model

        if not model_path.exists():
            print(f"[ERROR] Model path not found: {model_path}")
            return 1

        print(f"Loading PyTorch DistilBERT model from {model_path}...")
        checkpoint = torch.load(model_path, map_location="cpu")
        tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
        model = AutoModelForSequenceClassification.from_pretrained(
            "distilbert-base-uncased",
            num_labels=len(CLASSES),
        )
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()

        label_to_id = {c: i for i, c in enumerate(CLASSES)}
        id_to_label = {i: c for i, c in enumerate(CLASSES)}

        batch_size = 32
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            encoded = tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=128,
                return_tensors="pt",
            )
            with torch.no_grad():
                logits = model(**encoded).logits
                batch_preds = torch.argmax(logits, dim=-1).tolist()
                preds.extend([id_to_label[p] for p in batch_preds])
        model_name = f"DistilBERT ({model_path.name})"

    # Calculate metrics
    acc = accuracy_score(labels, preds)
    macro_f1 = f1_score(labels, preds, labels=CLASSES, average="macro")
    micro_f1 = f1_score(labels, preds, labels=CLASSES, average="micro")
    weighted_f1 = f1_score(labels, preds, labels=CLASSES, average="weighted")

    p, r, f1, sup = precision_recall_fscore_support(labels, preds, labels=CLASSES)
    cm = confusion_matrix(labels, preds, labels=CLASSES)

    print(f"\nModel: {model_name}")
    print(f"Overall Accuracy:  {acc:.4f}")
    print(f"Macro-Averaged F1: {macro_f1:.4f}")
    print(f"Micro-Averaged F1: {micro_f1:.4f}")
    print(f"Weighted F1:       {weighted_f1:.4f}")

    print("\nPer-Class Breakdown:")
    print(f"{'Class':15s} | {'Precision':10s} | {'Recall':10s} | {'F1-Score':10s} | {'Support':10s}")
    print("-" * 65)
    for idx, c in enumerate(CLASSES):
        print(f"{c:15s} | {p[idx]:10.4f} | {r[idx]:10.4f} | {f1[idx]:10.4f} | {sup[idx]:10d}")

    print("\nConfusion Matrix (Rows=True, Cols=Predicted):")
    print(f"{'':15s} | " + " | ".join(f"{c:>10s}" for c in CLASSES))
    print("-" * 55)
    for idx, row in enumerate(cm):
        print(f"{CLASSES[idx]:15s} | " + " | ".join(f"{val:>10d}" for val in row))

    if args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = PROJECT_ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_data = {
            "model_name": model_name,
            "split": args.split,
            "sample_count": len(texts),
            "accuracy": round(float(acc), 4),
            "macro_f1": round(float(macro_f1), 4),
            "micro_f1": round(float(micro_f1), 4),
            "weighted_f1": round(float(weighted_f1), 4),
            "per_class": {
                c: {
                    "precision": round(float(p[idx]), 4),
                    "recall": round(float(r[idx]), 4),
                    "f1_score": round(float(f1[idx]), 4),
                    "support": int(sup[idx]),
                }
                for idx, c in enumerate(CLASSES)
            },
            "confusion_matrix": cm.tolist(),
            "classes": CLASSES,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out_data, f, indent=2)
        print(f"\nSaved metrics to {out_path}")

    print("\n" + "=" * 70)
    print(" EVALUATION COMPLETED SUCCESSFULLY")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
