from __future__ import annotations

from typing import Callable

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import SVC


RANDOM_SEED = 42
MODEL_PROFILES = (
    "word_char_c1",
    "word_char_c2",
    "word_char_c4",
    "wide_word_char_c2",
    "char_only_c4",
    "svc_linear_c05",
    "svc_linear_c1",
    "svc_linear_c2",
)


def word_vectorizer(wide: bool = False) -> TfidfVectorizer:
    return TfidfVectorizer(
        analyzer="word",
        lowercase=True,
        strip_accents="unicode",
        token_pattern=r"(?u)\b\w\w+\b",
        ngram_range=(1, 3) if wide else (1, 2),
        min_df=1,
        max_df=1.0,
        norm="l2",
        smooth_idf=True,
        sublinear_tf=True,
    )


def char_vectorizer(wide: bool = False) -> TfidfVectorizer:
    return TfidfVectorizer(
        analyzer="char_wb",
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(2, 6) if wide else (3, 5),
        min_df=1,
        max_df=1.0,
        norm="l2",
        smooth_idf=True,
        sublinear_tf=True,
    )


def profile_spec(profile: str) -> tuple[object, float]:
    if profile == "word_char_c1":
        return FeatureUnion([("word", word_vectorizer()), ("char", char_vectorizer())]), 1.0
    if profile == "word_char_c2":
        return FeatureUnion([("word", word_vectorizer()), ("char", char_vectorizer())]), 2.0
    if profile == "word_char_c4":
        return FeatureUnion([("word", word_vectorizer()), ("char", char_vectorizer())]), 4.0
    if profile == "wide_word_char_c2":
        return FeatureUnion(
            [("word", word_vectorizer(wide=True)), ("char", char_vectorizer(wide=True))]
        ), 2.0
    if profile == "char_only_c4":
        return char_vectorizer(wide=True), 4.0
    raise ValueError(f"Perfil desconhecido: {profile}")


def build_classifier(profile: str) -> Pipeline:
    if profile.startswith("svc_linear_c"):
        c_value = {"svc_linear_c05": 0.5, "svc_linear_c1": 1.0, "svc_linear_c2": 2.0}[profile]
        features = FeatureUnion(
            [("word", word_vectorizer(wide=True)), ("char", char_vectorizer(wide=True))]
        )
        classifier = SVC(
            C=c_value,
            kernel="linear",
            class_weight="balanced",
            probability=True,
            random_state=RANDOM_SEED,
        )
        return Pipeline([("features", features), ("classifier", classifier)])
    features, regularization = profile_spec(profile)
    return Pipeline(
        [
            ("features", features),
            (
                "classifier",
                LogisticRegression(
                    C=regularization,
                    max_iter=4_000,
                    random_state=RANDOM_SEED,
                    solver="lbfgs",
                    class_weight="balanced",
                    tol=1e-5,
                ),
            ),
        ]
    )


def feature_names(model: Pipeline) -> list[str]:
    return [str(name) for name in model.named_steps["features"].get_feature_names_out()]
