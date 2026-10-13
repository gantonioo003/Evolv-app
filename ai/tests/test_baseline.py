from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

from evolv_nlp.baseline import (  # noqa: E402
    assert_compatible_runtime,
    build_classifier,
    classify,
    load_trusted_model,
)
from evolv_nlp.dataset import load_partition  # noqa: E402
class BaselineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.output_root = AI_ROOT / "artifacts" / "baseline" / "1.0.0"
        cls.manifest = json.loads(
            (cls.output_root / "manifest.json").read_text(encoding="utf-8")
        )
        cls.metrics = json.loads(
            (cls.output_root / "metrics.json").read_text(encoding="utf-8")
        )

    def test_dataset_partitions_have_expected_rows_and_classes(self) -> None:
        intent_train = load_partition(
            AI_ROOT / "data", "train", "intent_classification"
        )
        risk_train = load_partition(
            AI_ROOT / "data", "train", "risk_classification"
        )

        self.assertEqual(180, len(intent_train))
        self.assertEqual(30, len(set(intent_train.labels)))
        self.assertEqual(78, len(risk_train))
        self.assertEqual(13, len(set(risk_train.labels)))
        self.assertTrue(
            all(
                intent_train.labels.count(label) == 6
                for label in set(intent_train.labels)
            )
        )
        self.assertTrue(
            all(
                risk_train.labels.count(label) == 6
                for label in set(risk_train.labels)
            )
        )

    def test_vectorizer_learns_only_from_fit_input(self) -> None:
        model = build_classifier("word_only")
        model.fit(
            ("trocar supino agora", "registrar arroz agora"),
            ("replace_exercise", "record_food_intake"),
        )
        vocabulary = model.named_steps["features"].vocabulary_

        self.assertNotIn("segredodavalidacao", vocabulary)

    def test_training_manifest_excludes_test_and_challenge(self) -> None:
        self.assertEqual("1.2.0", self.manifest["dataset_version"])
        self.assertIn("Not loaded", self.manifest["data_usage"]["test"])
        self.assertIn("Not loaded", self.manifest["data_usage"]["challenge"])
        self.assertTrue(
            all(
                "/test/" not in path and "/challenge/" not in path
                for path in self.manifest["source_files"]
            )
        )
        self.assertEqual(6, len(self.manifest["code_files"]))

    def test_runtime_versions_are_enforced(self) -> None:
        assert_compatible_runtime(self.manifest["dependencies"])
        incompatible = {**self.manifest["dependencies"], "scikit-learn": "0.0.0"}
        with self.assertRaisesRegex(RuntimeError, "Ambiente incompativel"):
            assert_compatible_runtime(incompatible)

    def test_validation_selects_declared_word_and_character_profile(self) -> None:
        tasks = self.metrics["tasks"]
        self.assertEqual(
            "word_char",
            tasks["intent_classification"]["selection"][
                "selected_feature_profile"
            ],
        )
        self.assertEqual(
            "word_char",
            tasks["risk_classification"]["selection"][
                "selected_feature_profile"
            ],
        )
        self.assertGreaterEqual(
            tasks["intent_classification"]["validation"]["macro_f1"],
            0.30,
        )
        self.assertGreaterEqual(
            tasks["risk_classification"]["validation"]["macro_f1"],
            0.50,
        )

    def test_artifacts_load_with_hash_and_predict_known_labels(self) -> None:
        expected_classes = {
            "intent_classification": {
                item["id"]
                for item in json.loads(
                    (AI_ROOT / "data" / "taxonomy" / "intents.v1.json").read_text(
                        encoding="utf-8"
                    )
                )["intents"]
            },
            "risk_classification": {
                item["id"]
                for item in json.loads(
                    (AI_ROOT / "data" / "taxonomy" / "risks.v1.json").read_text(
                        encoding="utf-8"
                    )
                )["risks"]
            },
        }
        for task, artifact in self.manifest["model_artifacts"].items():
            model = load_trusted_model(
                self.output_root / artifact["file"], artifact["sha256"]
            )
            prediction = classify(model, "troca o supino de hoje")
            self.assertEqual(expected_classes[task], set(model.classes_))
            self.assertIn(prediction.label, expected_classes[task])
            self.assertGreaterEqual(prediction.confidence, 0.0)
            self.assertLessEqual(prediction.confidence, 1.0)
            self.assertEqual(3, len(prediction.alternatives))

    def test_modified_joblib_is_rejected_before_loading(self) -> None:
        artifact = self.manifest["model_artifacts"]["intent_classification"]
        original = self.output_root / artifact["file"]

        with self.assertRaisesRegex(ValueError, "Hash do modelo divergente"):
            load_trusted_model(original, "0" * 64)


if __name__ == "__main__":
    unittest.main()
