import json
import platform
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.corrected_release import canonical, match_reviews, read_reviews, load_partition
from evolv_nlp.corrected_training import (RiskLogistic, ClusterFrequency, HierarchicalIntent, NamedMLP,
    clean_research_context, load_corrected_payload, probabilities)
from evolv_nlp.corrected_pipeline import confidence_allowed, checked_feature_load, negated_plan_request
from evolv_nlp.dataset import file_sha256
from evolv_nlp.review_release import validate_isolation


class CorrectedImportTests(unittest.TestCase):
    def test_text_matching_does_not_depend_on_row_order_or_model_prediction(self):
        records = [{"id": "a", "partition": "train", "text": "mover treino de terca", "context": ""},
                   {"id": "b", "partition": "validation", "text": "trocar arroz por batata", "context": ""}]
        reviews = [{"number": 1, "message": records[1]["text"]}, {"number": 2, "message": records[0]["text"]}]
        self.assertEqual(["b", "a"], [rid for _, rid in match_reviews(reviews, records)])

    def test_ambiguous_missing_duplicate_and_reserved_matches_rejected(self):
        base = {"id": "a", "partition": "train", "text": "mensagem completa", "context": ""}
        review = {"number": 1, "message": "mensagem completa"}
        for records, reviews in [([base, {**base, "id": "b"}], [review]),
                                 ([base], [{**review, "message": "texto diferente"}]),
                                 ([base], [review, {**review, "number": 2}]),
                                 ([{**base, "partition": "test"}], [review])]:
            with self.subTest(records=records, reviews=reviews), self.assertRaises(ValueError):
                match_reviews(reviews, records)

    def test_context_disambiguates_identical_messages(self):
        records = [{"id": "a", "partition": "train", "text": "sim pode", "context": "trocar arroz"},
                   {"id": "b", "partition": "train", "text": "sim pode", "context": "mover treino"}]
        reviews = [{"number": 7, "message": "Contexto: mover treino. Mensagem: sim pode"}]
        self.assertEqual("b", match_reviews(reviews, records)[0][1])

    def test_unicode_and_whitespace_not_meaning_are_normalized(self):
        self.assertEqual(canonical("ação\n agora"), canonical("ac\u0327a\u0303o agora"))
        self.assertNotEqual(canonical("nao mover"), canonical("mover"))

    def test_actual_release_covers_every_review_and_preserves_reserved_bytes(self):
        root = AI_ROOT / "data/releases/1.8.0"
        manifest = json.loads((root / "manifest.json").read_text("utf-8"))
        self.assertEqual(2180, manifest["reviewed_records"])
        self.assertEqual(317, manifest["changes"]["intent_changes"])
        self.assertEqual(564, manifest["changes"]["risk_changes"])
        self.assertEqual(773, manifest["changes"]["any_label_change"])
        self.assertEqual(263, manifest["changes"]["uncertain_ai_reference"])
        rows = [r for part in manifest["coverage"] for r in load_partition(AI_ROOT, part)]
        self.assertEqual(12179, len(rows))
        validate_isolation(rows)
        for part, digest in manifest["reserved_byte_identical"].items():
            self.assertEqual(digest, file_sha256(root / f"private/{part}.jsonl"))
            self.assertEqual(digest, file_sha256(AI_ROOT / f"data/releases/1.7.0/private/{part}.jsonl"))
        for name, digest in manifest["files"].items():
            self.assertEqual(digest, file_sha256(root / name))
        for part in ("train", "validation"):
            old = {r["id"]: r for r in __import__('evolv_nlp.review_release', fromlist=['load_partition']).load_partition(AI_ROOT, part)}
            for row in load_partition(AI_ROOT, part):
                for field in ("text", "context", "input", "input_fingerprint", "group_id", "partition"):
                    self.assertEqual(old[row["id"]][field], row[field])
                if "ai_review" in row:
                    self.assertFalse(row["human_gold"])
                    self.assertNotIn("explanation", row["input"])


class CorrectedModelTests(unittest.TestCase):
    def test_negation_guard_covers_subjunctive_and_does_not_block_unrelated_negation(self):
        for text in ("Nao mude meu treino", "nao quero que voce altere o treino", "nao crie dieta", "nunca registre isso"):
            self.assertTrue(negated_plan_request(text), text)
        for text in ("Quero mudar meu treino", "Nao tenho halteres, pode trocar o exercicio?", "Nao acho ruim mudar o treino"):
            self.assertFalse(negated_plan_request(text), text)

    def test_mlp_encodes_string_labels_for_numeric_early_stopping(self):
        labels = np.asarray(["one", "two", "three", "four"] * 64)
        X = np.eye(4)[np.arange(len(labels)) % 4]
        model = NamedMLP().fit(X, labels, sample_weight=np.ones(len(X)))
        scores = model.predict_proba(X)
        self.assertEqual((256, 4), scores.shape)
        self.assertEqual(sorted(set(labels)), list(model.classes_))
        self.assertTrue(np.isfinite(scores).all())

    def test_binary_risk_models_accept_sample_weights_and_multi_label_output(self):
        X = np.asarray([[0, 0], [0, 1], [1, 0], [1, 1]] * 4, dtype=float)
        y = X.astype(int)
        model = RiskLogistic().fit(X, y, sample_weight=np.ones(len(X)))
        scores = model.predict_proba(X)
        self.assertEqual(y.shape, scores.shape)
        self.assertTrue(np.isfinite(scores).all())
        self.assertTrue(((scores > 0) & (scores < 1)).all())

    def test_cluster_frequencies_are_learned_from_train_labels(self):
        class Clusters:
            n_clusters = 2
            def predict(self, X):
                return (X[:, 0] > 0).astype(int)
        X = np.asarray([[-2], [-1], [1], [2]], dtype=float)
        model = ClusterFrequency(Clusters(), ["a", "b"], "intent").fit(X, np.asarray(["a", "a", "b", "b"]))
        self.assertEqual([[1, 0], [1, 0], [0, 1], [0, 1]], model.predict_proba(X).tolist())

    def test_hierarchy_preserves_all_labels_and_normalizes_scores(self):
        labels = np.asarray(["ask_recovery", "ask_sleep_habits", "greeting", "clarification"] * 4)
        X = np.eye(4)[np.arange(16) % 4]
        model = HierarchicalIntent().fit(X, labels, sample_weight=np.ones(len(X)))
        scores = model.predict_proba(X)
        self.assertEqual(sorted(set(labels)), list(model.classes_))
        np.testing.assert_allclose(scores.sum(1), 1)

    def test_collection_boilerplate_removed_but_real_conversation_preserved(self):
        artificial = "Contexto anterior: A publicação pode depender de imagem/vídeo. A mídia não foi coletada ou analisada.\nMensagem atual: meu joelho doi"
        self.assertEqual("meu joelho doi", clean_research_context(artificial))
        synthetic = "Contexto anterior: [estado_sintetico] Nao ha proposta pendente.\nMensagem atual: sim"
        self.assertEqual("sim", clean_research_context(synthetic))
        real = "Contexto anterior: Coach: voce prefere arroz ou batata?\nMensagem atual: batata"
        self.assertEqual(real, clean_research_context(real))

    def test_corrupt_hash_or_path_cannot_reach_deserialization(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "model").write_bytes(b"invalid")
            for loader in (load_corrected_payload, checked_feature_load):
                with patch("joblib.load") as deserialize:
                    with self.assertRaises(ValueError):
                        loader(root, {"file": "model", "sha256": "wrong"})
                    with self.assertRaises(ValueError):
                        loader(root, {"file": "../model", "sha256": "wrong"})
                    deserialize.assert_not_called()

    def test_confidence_requires_validation_evidence_for_the_label(self):
        policy = {"margin_threshold": 0.3, "validation_label_support": {"known": 5, "rare": 1},
                  "minimum_label_validation_support": 5}
        self.assertTrue(confidence_allowed(policy, "known", 0.4))
        self.assertFalse(confidence_allowed(policy, "known", 0.2))
        self.assertFalse(confidence_allowed(policy, "rare", 1.0))
        self.assertFalse(confidence_allowed(policy, "unknown", 1.0))
        self.assertFalse(confidence_allowed({**policy, "margin_threshold": None}, "known", 1.0))


def finalized_compatible_runtime():
    root = AI_ROOT / "artifacts/baseline/1.8.0"
    if not (root / "manifest.json").exists():
        return False
    candidate = json.loads((root / "candidate_selection.json").read_text("utf-8"))
    return platform.python_version() == candidate["runtime"]["python"]


@unittest.skipUnless(finalized_compatible_runtime(), "New trained model requires its recorded runtime")
class CorrectedIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from evolv_nlp.corrected_pipeline import CorrectedCoachPipeline
        cls.pipeline = CorrectedCoachPipeline(AI_ROOT)

    def test_urgent_rule_wins_and_planner_cannot_write(self):
        result = self.pipeline.analyze("Sinto dor no peito agora, posso treinar?")
        self.assertEqual("urgent_referral", result["route"])
        self.assertFalse(result["planner"]["writes_allowed"])
        self.assertTrue(result["response_constraints"]["no_diagnosis"])
        self.assertEqual("1.8.0", result["dataset_version"])

    def test_negation_cannot_become_a_plan_change(self):
        result = self.pipeline.analyze("Nao quero que voce mude meu treino")
        self.assertNotEqual("draft_for_confirmation", result["route"])
        self.assertFalse(result["planner"]["writes_allowed"])

    def test_identifiers_are_minimized_before_model_features(self):
        received = []
        original = self.pipeline.predictor.scores
        def capture(texts):
            received.extend(texts)
            return original(texts)
        with patch.object(self.pipeline.predictor, "scores", side_effect=capture):
            result = self.pipeline.analyze("meu email e pessoa@example.com e quero treinar")
        self.assertNotIn("pessoa@example.com", received[0])
        self.assertFalse(result["privacy"]["automatic_training"])


if __name__ == "__main__":
    unittest.main()
