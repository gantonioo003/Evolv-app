from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "scripts"))
sys.path.insert(0, str(AI_ROOT / "src"))
from import_human_questions import import_questions
from evolv_nlp.dataset import read_jsonl


class InterviewImportTests(unittest.TestCase):
    def setUp(self):
        temp_root = AI_ROOT / ".cache/tests"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=temp_root)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def prepare(self, rows):
        path = self.root / "questions.csv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["participant_code", "question", "consent_training", "consent_evaluation", "source_type"])
            writer.writeheader()
            writer.writerows(rows)
        return path

    def row(self, **changes):
        return {"participant_code": "P001", "question": "Como melhorar meu treino?", "consent_training": "nao",
                "consent_evaluation": "sim", "source_type": "consented_interview", **changes}

    def test_duplicates_stay_reserved_and_training_consent_is_separate(self):
        source = self.prepare([self.row(), self.row(question="COMO melhorar meu treino!")])
        output = self.root / "out.jsonl"
        self.assertEqual(1, import_questions(source, output)["rows"])
        row = read_jsonl(output)[0]
        self.assertFalse(row["consent_training"])
        self.assertFalse(row["training_allowed"])
        self.assertEqual("reserved_human_holdout", row["split"])
        with self.assertRaises(ValueError):
            import_questions(source, output)

    def test_names_missing_consent_and_identifiers_are_rejected(self):
        for changes in ({"participant_code": "Gabriel"}, {"consent_evaluation": "nao"},
                        {"question": "Me responde em teste@example.com"}):
            source = self.prepare([self.row(**changes)])
            with self.assertRaises(ValueError):
                import_questions(source, self.root / "rejected.jsonl")
            self.assertFalse((self.root / "rejected.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
