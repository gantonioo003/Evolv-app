import importlib.util
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

AI_ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("predict_research", AI_ROOT / "scripts/predict_research.py")
prediction = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prediction)


class ResearchPredictionTests(unittest.TestCase):
    def test_rejects_unsupported_versions_and_invalid_text(self):
        with self.assertRaises(ValueError):
            prediction.predict("troca o supino", "../unexpected")
        for text in ("", "   ", None, "x" * 8001):
            with self.assertRaises(ValueError):
                prediction.predict(text, "1.4.0")

    def test_rejects_bad_hash_before_deserializing(self):
        if not (AI_ROOT / "artifacts/baseline/1.4.0/manifest.json").exists():
            self.skipTest("Research artifacts not generated")
        with patch.object(prediction, "file_sha256", return_value="invalid"), \
                patch.object(prediction.joblib, "load") as load:
            with self.assertRaises(ValueError):
                prediction.predict("troca o supino", "1.4.0")
            load.assert_not_called()

    def check_private_output(self, artifact_version):
        root = AI_ROOT / f"artifacts/baseline/{artifact_version}"
        if not (root / "manifest.json").exists():
            self.skipTest("Research artifacts not generated")
        if artifact_version == "1.5.0" and importlib.util.find_spec("onnxruntime") is None:
            self.skipTest("Optional research dependencies not installed")
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            result = prediction.predict("passa o treino de hoje para amanha", artifact_version)
        self.assertEqual("", stdout.getvalue())
        self.assertTrue(result["private_research_only"])
        self.assertFalse(result["planner_action_applied"])
        self.assertFalse(result["probabilities_calibrated"])
        self.assertEqual(artifact_version, result["version"])
        self.assertEqual(result, json.loads(json.dumps(result)))
        self.assertIsInstance(result["intent_classification"], str)
        self.assertIsInstance(result["risk_classification"], str)

    def test_classical_prediction_contract(self):
        self.check_private_output("1.4.0")

    def test_semantic_prediction_contract(self):
        self.check_private_output("1.5.0")


if __name__ == "__main__":
    unittest.main()
