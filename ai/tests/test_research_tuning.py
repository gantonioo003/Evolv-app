import sys
import unittest
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.linear_model import LogisticRegression

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.research_data import blocked_groups, private_eligibility, reply_text
from evolv_nlp.research_models import TwoStageClassifier
from evolv_nlp.tuning_v14 import FEATURES, PROFILES, estimator, features, select_trial, validate_partition_isolation
from evolv_nlp.tuning_semantic import augment_actions
from evolv_nlp.training_v13 import taxonomy


class ResearchTuningTests(unittest.TestCase):
    def test_thread_quarantine_propagates(self):
        rows = [{"id": "a", "thread_id": "t", "source_split": "train", "quarantine_reasons": ["overlap"]},
                {"id": "b", "thread_id": "t", "source_split": "train"},
                {"id": "c", "thread_id": "u", "source_split": "validation"}]
        self.assertEqual({"t"}, blocked_groups(rows))

    def test_cross_split_thread_is_blocked(self):
        self.assertEqual({"t"}, blocked_groups([
            {"id": "a", "thread_id": "t", "source_split": "train"},
            {"id": "b", "thread_id": "t", "source_split": "test"}]))

    def test_private_research_excludes_personal_signals_and_media(self):
        row = {"text": "uma pergunta generica sobre academia", "source": "reddit/r/maromba", "privacy_flags": []}
        self.assertEqual([], private_eligibility(row))
        self.assertIn("possible_minor", private_eligibility({**row, "privacy_flags": ["possible_minor"]}))
        self.assertIn("external_media_context", private_eligibility({**row, "media_context": True}))

    def test_answers_are_text_only_not_implicit_gold(self):
        self.assertEqual("opiniao", reply_text({"body": "opiniao", "author": "irrelevant"}))
        self.assertEqual("", reply_text({"author": "not text"}))

    def test_partition_guard(self):
        a = [{"id": "a", "text": "duvida sobre treino", "family": "t"}]
        with self.assertRaises(ValueError):
            validate_partition_isolation(a, [{"id": "b", "text": "outra duvida", "family": "t"}])
        with self.assertRaises(ValueError):
            validate_partition_isolation(a, [{"id": "b", "text": "DUVIDA sobre treino", "family": "u"}])

    def test_selection_ignores_test_results(self):
        trials = [{"order": 0, "selection_score": .6, "test_score": 1},
                  {"order": 1, "selection_score": .7, "test_score": 0}]
        self.assertEqual(1, select_trial(trials)["order"])

    def test_all_declared_estimators_accept_weighted_fit(self):
        X = csr_matrix([[1, 0], [2, 0], [0, 1], [0, 2]])
        for name in PROFILES:
            model = estimator(name).fit(X, ["a", "a", "b", "b"], sample_weight=np.ones(4))
            self.assertEqual(4, len(model.predict(X)))

    def test_features_fit_text(self):
        for name in FEATURES:
            self.assertEqual(2, features(name).fit_transform(["treino de forca", "refeicao com arroz"]).shape[0])

    def test_hierarchy_preserves_subtypes(self):
        X = csr_matrix([[2, 0, 0], [3, 0, 0], [0, 2, 0], [0, 3, 0], [0, 0, 2], [0, 0, 3]])
        y = ["a", "a", "a_sub", "a_sub", "b", "b"]
        model = TwoStageClassifier(LogisticRegression(C=10), {"a": "a", "a_sub": "a", "b": "b"})
        model.fit(X, y, sample_weight=np.ones(6))
        self.assertEqual(y, model.predict(X).tolist())

    def test_planner_action_augmentation_is_training_only(self):
        rows, manifest = augment_actions(AI_ROOT, [], taxonomy(AI_ROOT)["intents"])
        self.assertEqual(160, manifest["rows_added"])
        self.assertTrue(manifest["train_only"])
        self.assertTrue(all(r["provenance"] == "project_authored_synthetic" for r in rows))
        self.assertEqual(8, sum(r["label"] == "move_workout_day" for r in rows))


if __name__ == "__main__":
    unittest.main()
