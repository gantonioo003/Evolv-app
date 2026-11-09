import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.neural_review import register_experiment
from evolv_nlp.pipeline_v14 import ReviewedCoachPipeline
from evolv_nlp.bow_mlp_review import STOPWORDS, NamedIntentMLP


class NeuralProtocolTests(unittest.TestCase):
    def test_stopwords_keep_meaningful_negation_and_commands(self):
        self.assertFalse(set(STOPWORDS) & {"nao", "sem", "quero", "sim", "antes", "depois", "troca"})

    def test_mlp_integer_labels_are_decoded_to_names(self):
        import numpy as np
        class Classifier:
            n_iter_ = 1
            def predict(self, X):
                return np.array([1, 0])
            def predict_proba(self, X):
                return np.array([[0.1, 0.9], [0.8, 0.2]])
        model = NamedIntentMLP(Classifier(), ["question", "action"])
        self.assertEqual(["action", "question"], model.predict(None).tolist())
        self.assertEqual((2, 2), model.predict_proba(None).shape)
    def test_registered_configuration_cannot_be_silently_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            configuration = register_experiment(root)
            self.assertFalse(configuration["test_used_for_selection"])
            self.assertEqual(4, configuration["unfrozen_encoder_layers"])
            self.assertEqual(configuration, register_experiment(root))
            path = root / "artifacts/baseline/1.7.0/registered_experiment.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                register_experiment(root)

    def pipeline_without_models(self):
        pipeline = ReviewedCoachPipeline.__new__(ReviewedCoachPipeline)
        pipeline._load_domain(AI_ROOT)
        return pipeline

    def test_shared_safety_blocks_urgent_requests_without_model_permission(self):
        pipeline = self.pipeline_without_models()
        intent = {"label": "replace_exercise", "confident": True, "margin": 100.0}
        result = pipeline._compose("Sinto dor no peito agora", date(2026, 10, 19), None, intent, [])
        self.assertEqual("urgent_referral", result["route"])
        self.assertFalse(result["planner"]["writes_allowed"])
        self.assertTrue(result["response_constraints"]["no_exam_selection"])

    def test_shared_negation_and_pending_action_guards(self):
        pipeline = self.pipeline_without_models()
        for text, label, route in (("Nao quero mudar o treino", "adapt_training_plan", "clarify"),
                                   ("Pode aplicar", "confirm_planner_action", "clarify_pending_action")):
            result = pipeline._compose(text, date(2026, 10, 19), None,
                                       {"label": label, "confident": True, "margin": 100.0}, [])
            self.assertEqual(route, result["route"])
            self.assertFalse(result["planner"]["writes_allowed"])

    @unittest.skipUnless(importlib.util.find_spec("torch"), "Optional neural environment not installed")
    def test_head_tail_tokenization_keeps_question_end_and_fixed_shape(self):
        from evolv_nlp.neural_review import tokenize_inputs

        class Tokenizer:
            pad_token_id = 0
            def num_special_tokens_to_add(self, pair=False):
                return 2
            def encode(self, text, **kwargs):
                return [1000, *range(1, 501), 1001]
            def build_inputs_with_special_tokens(self, ids):
                return [1000, *ids, 1001]

        ids, masks, truncated = tokenize_inputs(Tokenizer(), ["long question"])
        self.assertEqual((1, 256), tuple(ids.shape))
        self.assertEqual(1, truncated)
        self.assertEqual(1, int(ids[0, 1]))
        self.assertEqual(500, int(ids[0, -2]))
        self.assertEqual(256, int(masks.sum()))


if __name__ == "__main__":
    unittest.main()
