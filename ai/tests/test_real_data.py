from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.real_data import duplicate_groups, load_reviews, near_duplicate_pairs, normalized_key, taxonomy_labels, validate_external
from evolv_nlp.training_v12 import weak_intent


class RealDataTests(unittest.TestCase):
    def setUp(self):
        self.temp_root = AI_ROOT / ".cache/tests"
        self.temp_root.mkdir(parents=True, exist_ok=True)

    def test_extension_has_unique_ids_and_existing_parents(self):
        extension = json.loads((AI_ROOT / "data/taxonomy/expansion.v1.1.json").read_text("utf-8"))
        labels = taxonomy_labels(AI_ROOT)
        self.assertEqual(len(labels["intents"]), 36)
        self.assertEqual(len(labels["risks"]), 16)
        self.assertEqual(len(labels["entities"]), 85)
        for collection in ("intents", "risks", "entities"):
            base = json.loads((AI_ROOT / f"data/taxonomy/{collection}.v1.json").read_text("utf-8"))
            base_ids = {r["id"] for r in base[collection]}
            added = [r["id"] for r in extension[collection]]
            self.assertEqual(len(added), len(set(added)))
            self.assertFalse(base_ids & set(added))
            for row in extension[collection]:
                if "parent" in row:
                    self.assertIn(row["parent"], base_ids)
                for entity in row.get("required_entities", []) + row.get("optional_entities", []):
                    self.assertIn(entity, labels["entities"])

    def test_duplicate_and_near_duplicate_grouping(self):
        first = {"id_mensagem": "a", "texto_original": "Como organizar meu treino de academia com corrida no fim de semana?", "split": "train", "thread_id": "t1", "split_group_id": "g1"}
        second = {**first, "id_mensagem": "b", "texto_original": first["texto_original"] + " obrigado", "split": "test", "thread_id": "t2", "split_group_id": "g2"}
        self.assertIn(("a", "b"), near_duplicate_pairs([first, second]))
        third = {**first, "id_mensagem": "c"}
        self.assertTrue(any(ids == {"a", "c"} for ids in duplicate_groups([first, third]).values()))

    def test_labels_are_not_inferred_from_unknown_or_multitopic_text(self):
        self.assertIsNone(weak_intent("ajuda urgente por favor"))
        self.assertIsNone(weak_intent("dor no joelho com creatina"))
        self.assertEqual(weak_intent("avalia meu treino abc"), "ask_training_program_feedback")
        self.assertEqual(normalized_key("Joelho DÓI!"), "joelho doi")

    def test_review_cannot_open_external_test(self):
        with tempfile.TemporaryDirectory(dir=self.temp_root) as directory:
            path = Path(directory) / "reviews.json"
            path.write_text(json.dumps({"reviews": [{"id": "a", "intent": "ask_recovery", "risks": []}]}), "utf-8")
            with self.assertRaisesRegex(ValueError, "TRAIN"):
                load_reviews(path, [{"id_mensagem": "a", "split": "test"}], taxonomy_labels(AI_ROOT))

    def test_invalid_spans_and_languages_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=self.temp_root) as directory:
            root = Path(directory)
            message = {"id_mensagem": "a", "texto_original": "joelho doi", "idioma": "pt-BR", "split": "train"}
            annotation = {"id_mensagem": "a", "texto_original": "joelho doi"}
            for name, rows in (("mensagens.jsonl", [message]), ("classificacao_revisar.jsonl", [annotation]),
                               ("entidades_revisar.jsonl", [{"id_mensagem": "a", "start": 0, "end": 6, "trecho_original": "errado"}]),
                               ("candidatos_novas_entidades.jsonl", [])):
                (root / name).write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
            with self.assertRaisesRegex(ValueError, "Span"):
                validate_external(root, 1)


if __name__ == "__main__":
    unittest.main()
