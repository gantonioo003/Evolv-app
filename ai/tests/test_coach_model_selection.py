"""Service selection is explicit; no silent promotion or fallback on invalid versions."""
from pathlib import Path
from types import SimpleNamespace
import os
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from evolv_api.app import Settings, Manager
from evolv_rag.coach import load_nlp, MemoryOnlyEncoder

KEY = "temporary-test-key-with-at-least-32-characters"

class SelectionTests(unittest.TestCase):
    def test_default_stays_legacy_and_unknown_is_rejected(self):
        self.assertEqual("1.8.0", Settings(KEY).nlp_version)
        with self.assertRaises(ValueError):
            Settings(KEY, nlp_version="latest")
        with self.assertRaises(ValueError):
            load_nlp(ROOT, "latest")

    def test_env_and_manager_forward_explicit_selection(self):
        with patch.dict(os.environ, {"EVOLV_AI_SERVICE_KEY": KEY,
                "EVOLV_AI_NLP_VERSION": "1.9.0", "EVOLV_AI_MODE": "analyze",
                "EVOLV_AI_RETRIEVAL_VERSION": "1.1.1"}):
            settings = Settings.from_env()
        with patch("evolv_rag.coach.load_coach") as loader:
            manager = Manager(settings)
            manager.start()
            loader.assert_called_once_with(ROOT, generate=False,
                adapted=False, nlp_version="1.9.0", retrieval_version="1.1.1")

    def test_selected_runtime_and_private_encoder(self):
        sentinel = object()
        with patch("evolv_nlp.recognition_pipeline.RecognitionPipeline", return_value=sentinel) as new:
            self.assertIs(sentinel, load_nlp(ROOT, "1.9.0"))
            new.assert_called_once_with(ROOT)
        old = SimpleNamespace(predictor=SimpleNamespace(encoder=object()))
        with patch("evolv_nlp.corrected_pipeline.CorrectedCoachPipeline", return_value=old):
            self.assertIs(old, load_nlp(ROOT))
            self.assertIsInstance(old.predictor.encoder, MemoryOnlyEncoder)

if __name__ == "__main__":
    unittest.main()
