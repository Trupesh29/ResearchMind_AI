"""
ResearchMind AI — SciCite Classification Service
Provides inference, artifacts loading, and classifier abstractions for
citation context intent classification (background, method, result).
"""

from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np

CLASSES = ["background", "method", "result"]


class MajorityClassifier:
    """Predicts the majority class from training data."""

    def __init__(self, majority_class: str = "background", class_counts: Optional[Dict[str, int]] = None):
        self.majority_class_ = majority_class
        self.class_counts_ = class_counts or {}

    def fit(self, texts: List[str], labels: List[str]) -> "MajorityClassifier":
        counts = Counter(labels)
        self.class_counts_ = dict(counts)
        self.majority_class_ = counts.most_common(1)[0][0]
        return self

    def predict(self, texts: List[str]) -> List[str]:
        return [self.majority_class_] * len(texts)

    def predict_proba(self, texts: List[str]) -> np.ndarray:
        total = sum(self.class_counts_.values()) or 1
        probs = [self.class_counts_.get(c, 0) / total for c in CLASSES]
        return np.tile(probs, (len(texts), 1))


class SciCiteClassifierService:
    """Service to load and query trained citation intent models."""

    def __init__(self, models_dir: Optional[Path] = None):
        if models_dir is None:
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            models_dir = project_root / "data" / "models" / "scicite"
        self.models_dir = models_dir
        self._tfidf_pipeline: Optional[Dict[str, Any]] = None
        self._majority_model: Optional[MajorityClassifier] = None

    def load_tfidf_model(self) -> Dict[str, Any]:
        if self._tfidf_pipeline is None:
            path = self.models_dir / "tfidf_baseline.joblib"
            if not path.exists():
                raise FileNotFoundError(f"TF-IDF baseline artifact not found at {path}")
            self._tfidf_pipeline = joblib.load(path)
        return self._tfidf_pipeline

    def predict_citation_intent(self, text: str) -> Dict[str, Any]:
        pipeline = self.load_tfidf_model()
        vec = pipeline["vectorizer"]
        clf = pipeline["classifier"]

        X = vec.transform([text])
        pred_label = clf.predict(X)[0]
        probs = clf.predict_proba(X)[0]

        class_probs = {c: round(float(probs[i]), 4) for i, c in enumerate(clf.classes_)}
        return {
            "predicted_intent": pred_label,
            "confidence": class_probs.get(pred_label, 0.0),
            "probabilities": class_probs,
        }
