from __future__ import annotations

import hashlib
import platform
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline


RANDOM_SEED = 42


@dataclass(frozen=True)
class RankedLabel:
    label: str
    confidence: float


@dataclass(frozen=True)
class ClassificationResult:
    label: str
    confidence: float
    alternatives: tuple[RankedLabel, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "alternatives": [asdict(item) for item in self.alternatives],
        }


FEATURE_PROFILES = ("word_only", "word_char")


def word_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        analyzer="word",
        lowercase=True,
        strip_accents="unicode",
        token_pattern=r"(?u)\b\w\w+\b",
        ngram_range=(1, 2),
        min_df=1,
        max_df=1.0,
        norm="l2",
        smooth_idf=True,
        sublinear_tf=True,
    )


def build_classifier(feature_profile: str = "word_char") -> Pipeline:
    if feature_profile not in FEATURE_PROFILES:
        raise ValueError(f"Perfil de atributos desconhecido: {feature_profile}")
    features: TfidfVectorizer | FeatureUnion
    if feature_profile == "word_only":
        features = word_vectorizer()
    else:
        features = FeatureUnion(
            transformer_list=[
                ("word", word_vectorizer()),
                (
                    "char",
                    TfidfVectorizer(
                        analyzer="char_wb",
                        lowercase=True,
                        strip_accents="unicode",
                        ngram_range=(3, 5),
                        min_df=1,
                        max_df=1.0,
                        norm="l2",
                        smooth_idf=True,
                        sublinear_tf=True,
                    ),
                ),
            ]
        )
    return Pipeline(
        steps=[
            ("features", features),
            (
                "classifier",
                LogisticRegression(
                    C=1.0,
                    max_iter=2_000,
                    random_state=RANDOM_SEED,
                    solver="lbfgs",
                    tol=1e-4,
                ),
            ),
        ]
    )


def classify(model: Pipeline, text: str, top_k: int = 3) -> ClassificationResult:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("O texto para classificacao nao pode estar vazio")
    if top_k < 1:
        raise ValueError("top_k precisa ser positivo")

    probabilities = model.predict_proba([text])[0]
    classes = model.classes_
    ranking = np.argsort(probabilities)[::-1][: min(top_k, len(classes))]
    alternatives = tuple(
        RankedLabel(
            label=str(classes[index]),
            confidence=round(float(probabilities[index]), 6),
        )
        for index in ranking
    )
    best = alternatives[0]
    return ClassificationResult(
        label=best.label,
        confidence=best.confidence,
        alternatives=alternatives,
    )


def artifact_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_trusted_model(path: Path, expected_sha256: str) -> Pipeline:
    observed = artifact_sha256(path)
    if observed != expected_sha256:
        raise ValueError(
            f"Hash do modelo divergente em {path.name}; o artefato nao sera carregado"
        )
    model = joblib.load(path)
    if not isinstance(model, Pipeline):
        raise TypeError(f"Artefato inesperado em {path}")
    return model


def assert_compatible_runtime(expected: dict[str, str]) -> None:
    observed = {
        "python": platform.python_version(),
        "joblib": version("joblib"),
        "numpy": version("numpy"),
        "scikit-learn": version("scikit-learn"),
        "scipy": version("scipy"),
    }
    mismatches = {
        name: {"expected": expected.get(name), "observed": value}
        for name, value in observed.items()
        if expected.get(name) != value
    }
    if mismatches:
        raise RuntimeError(f"Ambiente incompativel com o artefato: {mismatches}")
