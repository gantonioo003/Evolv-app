from datetime import date
from pathlib import Path
import sys
import unittest
import numpy as np
AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_rag.search import Search

class FakeEncoder:
    def encode(self, texts):
        a = np.zeros((len(texts), 384), dtype=np.float32)
        a[:, 0] = 1
        return a

class SearchTests(unittest.TestCase):
    def setUp(self):
        self.s = Search.__new__(Search)
        self.s.encoder = FakeEncoder()
        self.s.vectors = np.zeros((3, 384), dtype=np.float32)
        self.s.vectors[:, 0] = [1, .7, .2]
        self.s.rows = [{"id": str(i), "effective_review_due_at": "2027-01-01",
                       "reviewed_at": "2026-10-01", "domain": "training",
                       "topic_ids": ["strength_training"], "citations": [
                           {"status": "approved", "last_verified_at": "2026-10-01",
                            "review_due_at": "2027-01-01"}]} for i in range(3)]
    def test_rank_threshold_and_expiry_before_top_k(self):
        self.s.rows[0]["effective_review_due_at"] = "2026-11-02"
        result = self.s.query("treino", as_of=date(2026,11,2))
        self.assertEqual(["1"], [x["id"] for x in result["matches"]])
    def test_source_expiry_also_blocks(self):
        self.s.rows[0]["citations"][0]["review_due_at"] = "2026-11-02"
        result = self.s.query("treino", k=1, as_of=date(2026,11,2))
        self.assertEqual("1", result["matches"][0]["id"])
    def test_no_evidence_and_filters(self):
        self.assertEqual("no_evidence", self.s.query("treino", domain="nutrition")["status"])
        self.assertEqual("no_evidence", self.s.query("treino", topics=["unknown"])["status"])
    def test_invalid_queries_and_budgets(self):
        for query in ["", " ", None, "a"*20001]:
            with self.assertRaises(ValueError):
                self.s.query(query)
        with self.assertRaises(ValueError):
            self.s.query("treino", k=4)

if __name__ == "__main__":
    unittest.main()
