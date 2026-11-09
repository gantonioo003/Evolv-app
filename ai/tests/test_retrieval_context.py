from copy import deepcopy
from datetime import date
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
AI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI / "src"))
from evolv_rag.preparation import write, digest
from evolv_rag.retrieval import HybridSearch
from evolv_rag.retrieval_hydration import HydrationSearch
from evolv_rag.retrieval_runtime import load_search
from evolv_rag.coach import Coach
from evolv_api.app import Settings


class Encoder:
    manifest = {"test_encoder": True}
    def __init__(self): self.calls = []
    def encode(self, texts):
        self.calls.extend(texts)
        result = np.zeros((len(texts), 384), dtype=np.float32)
        for i, text in enumerate(texts):
            for axis, word in enumerate(["noite", "series", "creatina"]):
                if word in text: result[i, axis] = 1
            if not result[i].any(): result[i, 3] = 1
            result[i] /= np.linalg.norm(result[i])
        return result


class NLP:
    def analyze(self, text, **kwargs):
        return {"route": "answer", "risk": {"labels": []},
                "intent": {"label": "ask_training_concept", "confident": True},
                "entities": {"text": text, "entities": []}}


class ContextRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.encoder = Encoder()
        rows = []
        for i, title in enumerate(["noite alimentação", "series descanso", "creatina desempenho"]):
            rows.append({"id": f"kb:{i}", "document_id": str(i), "embedding_text": title,
                "reviewed_at": "2026-01-01", "effective_review_due_at": "2027-01-01",
                "domain": "nutrition" if i != 1 else "training", "topic_ids": [str(i)],
                "citations": [{"status": "approved", "last_verified_at": "2026-01-01", "review_due_at": "2027-01-01"}],
                "generation_context": {"text": title, "not_for": "diagnóstico", "evidence_ids": [str(i)]}})
        write(self.root / "chunks.json", rows)
        vectors = np.zeros((3, 384), dtype=np.float32)
        vectors[range(3), range(3)] = 1
        np.save(self.root / "vectors.npy", vectors, allow_pickle=False)
        write(self.root / "manifest.json", {"encoder": self.encoder.manifest,
            "outputs": {name: digest(self.root / name) for name in ["chunks.json", "vectors.npy"]}})
        self.s = HybridSearch(self.root, self.encoder, {"lexical_weight": .45, "context_weight": .8, "min_score": .3})
    def tearDown(self): self.tmp.cleanup()

    def test_assistant_claims_never_become_context_or_persist(self):
        history = [{"role": "assistant", "content": "creatina private@example.com"}]
        result = self.s.query_conversation("E se for de noite?", history, as_of=date(2026, 11, 3))
        self.assertFalse(result["context"]["used"])
        self.assertFalse(any("private@example.com" in t for t in self.encoder.calls))
        self.assertNotIn("private@example.com", json.dumps(result))
        self.assertFalse(hasattr(self.s, "history"))

    def test_long_followup_uses_only_last_user_turn(self):
        prior = [{"role": "user", "content": "creatina"}, {"role": "user", "content": "noite"},
                 {"role": "assistant", "content": "creatina"}]
        text = "E se eu realmente precisar organizar tudo isso para noite nessa situação?"
        result = self.s.query_conversation(text, prior, as_of=date(2026, 11, 3))
        self.assertTrue(result["context"]["used"])
        self.assertEqual(1, result["context"]["user_turns_used"])
        self.assertFalse(any("creatina" in t for t in self.encoder.calls))

    def test_explicit_topic_switch_does_not_inherit_history(self):
        result = self.s.query_conversation("Mudando de assunto: creatina?", [{"role": "user", "content": "noite"}], as_of=date(2026, 11, 3))
        self.assertFalse(result["context"]["used"])
        self.assertEqual("2", result["matches"][0]["document_id"])
        self.assertEqual("explicit_subject_switch", result["context"]["reason"])

    def test_vague_followup_with_or_without_history_has_no_evidence(self):
        for history in [[], [{"role": "user", "content": "creatina"}]]:
            result = self.s.query_conversation("E isso?", history, as_of=date(2026, 11, 3))
            self.assertEqual("no_evidence", result["status"])

    def test_expiry_and_filters_apply_before_hybrid_ranking(self):
        self.s.rows[0]["citations"][0]["review_due_at"] = "2026-11-03"
        result = self.s.query("noite", as_of=date(2026, 11, 3))
        self.assertFalse(any(r["document_id"] == "0" for r in result["matches"]))
        self.assertEqual("no_evidence", self.s.query("series", topics=["missing"], as_of=date(2026, 11, 3))["status"])

    def test_shared_search_does_not_share_coach_history(self):
        first, second = Coach(NLP(), self.s), Coach(NLP(), self.s)
        first.respond("noite?", reference_date=date(2026, 11, 3))
        first_result = first.respond("E se for de noite?", reference_date=date(2026, 11, 3))
        second_result = second.respond("series?", reference_date=date(2026, 11, 3))
        self.assertTrue(first_result["retrieval"]["context"]["used"])
        self.assertFalse(second_result["retrieval"]["context"]["used"])
        self.assertEqual(2, len(second.history))

    def test_hydration_alias_expands_only_water_intake_during_activity(self):
        search = HydrationSearch.__new__(HydrationSearch)
        with patch.object(HybridSearch, "lexical") as lexical:
            for text in (
                "Todo mundo deve beber a mesma quantidade de água no treino?",
                "Preciso beber líquido enquanto pedalo?",
                "Quanto de água eu devo tomar na academia?",
            ):
                search.lexical(text)
                lexical.assert_called_with(text + "\nhidratação líquido suor")
            for text in (
                "Quanta água coloco para cozinhar arroz antes de treinar?",
                "Posso tomar whey com água antes do treino?",
                "Qual a capital do Canadá?",
            ):
                search.lexical(text)
                lexical.assert_called_with(text)

    def test_invalid_inputs_and_runtime_versions_fail(self):
        for text in [None, "", " ", "x" * 20001]:
            with self.assertRaises(ValueError): self.s.query(text)
        with self.assertRaises(ValueError): self.s.query_conversation("noite", [{}] * 17)
        with self.assertRaises(ValueError): self.s.query("noite", k=4)
        with self.assertRaises(ValueError): load_search(AI, "latest")
        with self.assertRaises(ValueError): Settings("x" * 32, retrieval_version="latest")
        self.assertEqual("1.1.2", Settings("x" * 32).retrieval_version)

    def test_runtime_refuses_modified_index_manifest(self):
        config = {"version": "1.1.1", "index": "artifacts/rag/1.1.1", "index_manifest_sha256": "0" * 64}
        (self.root / "configs").mkdir()
        write(self.root / "configs/retrieval.runtime.v1.json", config)
        (self.root / "artifacts/rag/1.1.1").mkdir(parents=True)
        write(self.root / "artifacts/rag/1.1.1/manifest.json", {})
        with patch("evolv_rag.retrieval_runtime.Encoder", return_value=self.encoder):
            with self.assertRaises(ValueError): load_search(self.root)

if __name__ == "__main__": unittest.main()
