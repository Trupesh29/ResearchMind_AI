"""
ResearchMind AI — SciCite DistilBERT Initial Training Trial & Checkpointing
Performs bounded fine-tuning trial on SciCite dataset:
- Sequence length = 128 tokens, records truncation rate
- Pinned seed (42) for reproducibility
- Saves intermediate training checkpoint
- Supports interruption simulation and resume from checkpoint
- Evaluates on dev.jsonl split (test.jsonl strictly untouched)
- Records device configuration, duration, RSS memory, and validation curves
- Saves report to docs/scicite_distilbert_trial_report.json
"""

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

import ctypes
from ctypes import wintypes
import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = PROJECT_ROOT / "data" / "models" / "scicite" / "dataset" / "scicite"
MODELS_DIR = PROJECT_ROOT / "data" / "models" / "scicite"
CHECKPOINT_PATH = MODELS_DIR / "distilbert_checkpoint.pt"
FINAL_MODEL_PATH = MODELS_DIR / "distilbert_scicite_trial.pt"
REPORT_PATH = PROJECT_ROOT / "docs" / "scicite_distilbert_trial_report.json"

CLASSES = ["background", "method", "result"]
LABEL_TO_ID = {c: i for i, c in enumerate(CLASSES)}
ID_TO_LABEL = {i: c for i, c in enumerate(CLASSES)}


def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def get_process_memory_mb() -> float:
    try:
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return round(counters.WorkingSetSize / (1024 * 1024), 2)
    except Exception:
        pass
    return 0.0


class SciCiteDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length: int = 128):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = self.texts[idx]
        label = self.labels[idx]
        label_id = LABEL_TO_ID[label]
        encoding = self.tokenizer(
            text,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )
        item = {key: val.squeeze(0) for key, val in encoding.items()}
        item["labels"] = torch.tensor(label_id, dtype=torch.long)
        return item


def load_split(split_name: str, max_samples: int = None):
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
            if max_samples and len(texts) >= max_samples:
                break
    return texts, labels


def evaluate(model, dataloader, device):
    model.eval()
    total_loss = 0.0
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
            total_loss += outputs.loss.item() * len(labels)

            preds = torch.argmax(outputs.logits, dim=-1)
            all_preds.extend(preds.cpu().tolist())
            all_labels.extend(labels.cpu().tolist())

    avg_loss = total_loss / len(dataloader.dataset)
    y_true = [ID_TO_LABEL[i] for i in all_labels]
    y_pred = [ID_TO_LABEL[i] for i in all_preds]

    acc = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, labels=CLASSES, average="macro")
    p, r, f1, sup = precision_recall_fscore_support(y_true, y_pred, labels=CLASSES, zero_division=0)
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
        "val_loss": round(float(avg_loss), 4),
        "accuracy": round(float(acc), 4),
        "macro_f1": round(float(macro_f1), 4),
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="SciCite DistilBERT Training Trial")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument("--lr", type=float, default=2e-5, help="Learning rate")
    parser.add_argument("--epochs", type=int, default=1, help="Number of training epochs")
    parser.add_argument("--max-train-samples", type=int, default=800, help="Train sample limit for bounded trial")
    parser.add_argument("--simulate-interrupt", action="store_true", help="Simulate worker interrupt after step")
    parser.add_argument("--resume", action="store_true", help="Resume from saved checkpoint")
    args = parser.parse_args()

    set_seed(args.seed)
    start_time = time.perf_counter()
    initial_rss_mb = get_process_memory_mb()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("=" * 70)
    print(" ResearchMind AI — SciCite DistilBERT Initial Training Trial")
    print("=" * 70)
    print(f"Device: {device}")
    print(f"Initial Memory RSS: {initial_rss_mb} MB")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load Data
    print("\n[1/5] Loading SciCite splits...")
    train_texts, train_labels = load_split("train", max_samples=args.max_train_samples)
    dev_texts, dev_labels = load_split("dev")
    print(f"  - Train samples: {len(train_texts)}")
    print(f"  - Dev samples:   {len(dev_texts)}")
    print("  - Test split (test.jsonl): ISOLATED and UNTOUCHED.")

    # 2. Tokenizer & Truncation Check
    tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
    raw_token_counts = [len(tokenizer.encode(t, truncation=False)) for t in train_texts]
    truncated_count = sum(1 for c in raw_token_counts if c > 128)
    truncation_rate = round(truncated_count / len(train_texts), 4)
    print(f"  - Max sequence length: 128")
    print(f"  - Truncated samples: {truncated_count}/{len(train_texts)} ({truncation_rate * 100:.2f}%)")

    train_dataset = SciCiteDataset(train_texts, train_labels, tokenizer, max_length=128)
    dev_dataset = SciCiteDataset(dev_texts, dev_labels, tokenizer, max_length=128)

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    dev_loader = DataLoader(dev_dataset, batch_size=args.batch_size, shuffle=False)

    # 3. Model & Optimizer Initialization
    model = AutoModelForSequenceClassification.from_pretrained(
        "distilbert-base-uncased",
        num_labels=len(CLASSES),
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)

    start_epoch = 0
    start_step = 0
    resumed_from_step = None

    if args.resume and CHECKPOINT_PATH.exists():
        print(f"\n[Resuming from Checkpoint: {CHECKPOINT_PATH}]")
        checkpoint = torch.load(CHECKPOINT_PATH, map_location=device)
        model.load_state_dict(checkpoint["model_state_dict"])
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        start_step = checkpoint.get("step", 0)
        resumed_from_step = start_step
        print(f"  - Successfully restored state at step {start_step}")

    # 4. Training Loop with Checkpointing
    print(f"\n[2/5] Training for {args.epochs} epoch(s)...")
    model.train()
    step = 0
    training_curves = []

    for epoch in range(start_epoch, args.epochs):
        epoch_loss = 0.0
        for batch_idx, batch in enumerate(train_loader):
            step += 1
            if step <= start_step:
                continue

            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            optimizer.zero_grad()
            outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
            loss = outputs.loss
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()

            if step % 10 == 0 or step == len(train_loader):
                rss_now = get_process_memory_mb()
                training_curves.append({
                    "step": step,
                    "loss": round(loss.item(), 4),
                    "memory_rss_mb": rss_now,
                })
                print(f"  Epoch {epoch+1} | Step {step}/{len(train_loader)} | Loss: {loss.item():.4f} | RSS: {rss_now} MB")

            # Save checkpoint midway
            if step == 15 and not args.resume:
                print(f"\n  [Checkpointing at step {step}] => {CHECKPOINT_PATH}")
                torch.save({
                    "step": step,
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "loss": loss.item(),
                }, CHECKPOINT_PATH)

                if args.simulate_interrupt:
                    print("  [SIMULATED INTERRUPTION] Stopping training as requested to verify recovery.")
                    return 0

    peak_rss_mb = get_process_memory_mb()

    # 5. Validation Evaluation
    print("\n[3/5] Evaluating on Dev split...")
    val_results = evaluate(model, dev_loader, device)
    print(f"  - Validation Loss: {val_results['val_loss']}")
    print(f"  - Dev Accuracy:    {val_results['accuracy']:.4f}")
    print(f"  - Dev Macro-F1:    {val_results['macro_f1']:.4f}")
    for c, stats in val_results["per_class"].items():
        print(f"    {c:12s}: P={stats['precision']:.4f}, R={stats['recall']:.4f}, F1={stats['f1_score']:.4f}")

    # 6. Save Model Artifact
    print(f"\n[4/5] Saving fine-tuned trial artifact to {FINAL_MODEL_PATH}...")
    torch.save({
        "model_state_dict": model.state_dict(),
        "classes": CLASSES,
        "label_to_id": LABEL_TO_ID,
        "config": {
            "model_type": "distilbert-base-uncased",
            "seed": args.seed,
            "max_length": 128,
            "lr": args.lr,
            "batch_size": args.batch_size,
        },
    }, FINAL_MODEL_PATH)

    total_duration_s = round(time.perf_counter() - start_time, 2)

    # 7. Write Report
    print(f"\n[5/5] Writing Trial Report to {REPORT_PATH}...")
    report = {
        "workstream": "scicite_distilbert_initial_trial",
        "device": str(device),
        "seed": args.seed,
        "hyperparameters": {
            "model": "distilbert-base-uncased",
            "max_sequence_length": 128,
            "batch_size": args.batch_size,
            "learning_rate": args.lr,
            "epochs": args.epochs,
            "train_samples": len(train_texts),
        },
        "truncation": {
            "max_len": 128,
            "truncated_count": truncated_count,
            "truncation_rate": truncation_rate,
        },
        "memory": {
            "initial_rss_mb": initial_rss_mb,
            "peak_rss_mb": peak_rss_mb,
            "net_growth_mb": round(peak_rss_mb - initial_rss_mb, 2),
        },
        "execution": {
            "duration_seconds": total_duration_s,
            "resumed_from_step": resumed_from_step,
            "checkpoint_file": str(CHECKPOINT_PATH.relative_to(PROJECT_ROOT)),
            "model_file": str(FINAL_MODEL_PATH.relative_to(PROJECT_ROOT)),
        },
        "training_curves": training_curves,
        "validation_metrics": val_results,
        "test_split_status": "strictly_untouched_reserved_for_week4",
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"  - Report written to {REPORT_PATH}")
    print("\n" + "=" * 70)
    print(" DISTILBERT TRAINING TRIAL COMPLETED SUCCESSFULLY")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
