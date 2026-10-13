from __future__ import annotations

import json
import hashlib
import sys
import unittest
from datetime import date
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

from evolv_nlp.entities import (  # noqa: E402
    entity_signature,
    extract_entities,
    load_entity_catalog,
    score_entity_predictions,
)


class EntityExtractionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog_path = (
            AI_ROOT / "data" / "catalogs" / "entity_catalogs.v1.json"
        )
        cls.catalog = load_entity_catalog(cls.catalog_path)
        cls.reference = date(2026, 10, 7)

    def signatures(self, text: str) -> set[tuple[str, str]]:
        result = extract_entities(text, self.catalog, self.reference)
        return {entity_signature(entity) for entity in result.entities}

    def assert_entity(self, text: str, entity_type: str, value: object) -> None:
        signature = (entity_type, json.dumps(value, ensure_ascii=False, sort_keys=True))
        self.assertIn(signature, self.signatures(text))

    def test_catalog_is_versioned_and_covers_exercise_food_and_context(self) -> None:
        self.assertEqual("1.0.0", self.catalog.version)
        types = {entry.entity_type for entry in self.catalog.entries}
        self.assertTrue(
            {"exercise", "food", "goal", "body_part", "dietary_restriction"}
            <= types
        )
        self.assertGreaterEqual(
            sum(entry.entity_type == "exercise" for entry in self.catalog.entries),
            50,
        )
        self.assertGreaterEqual(
            sum(entry.entity_type == "food" for entry in self.catalog.entries),
            30,
        )

    def test_exercise_and_food_catalogs_ignore_case_and_accents(self) -> None:
        self.assert_entity("SUPINO INCLINADO e arroz", "exercise", "supino inclinado")
        self.assert_entity("SUPINO INCLINADO e arroz", "food", "arroz branco cozido")
        self.assert_entity("comi maçã", "food", "maca")

    def test_replacement_roles_use_context(self) -> None:
        signatures = self.signatures("troca o supino reto por flexão de braços")
        self.assertIn(("exercise", '"supino reto"'), signatures)
        self.assertIn(("replacement_exercise", '"flexao de bracos"'), signatures)

        food_signatures = self.signatures("coloca batata doce no lugar de arroz")
        self.assertIn(("replacement_food", '"batata-doce cozida"'), food_signatures)
        self.assertIn(("food", '"arroz branco cozido"'), food_signatures)

    def test_sets_repetitions_load_and_duration_are_structured(self) -> None:
        text = "leg press 4x10-12 com 90 kg e descanso de 2 minutos"
        signatures = self.signatures(text)
        self.assertIn(("sets", "4"), signatures)
        self.assertIn(
            ("repetitions", '{"maximum": 12, "minimum": 10}'), signatures
        )
        self.assertIn(("load", '{"amount": 90, "unit": "kg"}'), signatures)
        self.assertIn(
            (
                "rest_duration",
                '{"amount": 2, "seconds": 120, "unit": "minute"}',
            ),
            signatures,
        )

    def test_numbers_written_in_words_and_per_side_are_supported(self) -> None:
        self.assert_entity(
            "quatro séries de oito a doze repetições com vinte quilos de cada lado",
            "sets",
            4,
        )
        self.assert_entity(
            "quatro séries de oito a doze repetições com vinte quilos de cada lado",
            "repetitions",
            {"minimum": 8, "maximum": 12},
        )
        result = extract_entities(
            "vinte quilos de cada lado", self.catalog, self.reference
        )
        load = next(entity for entity in result.entities if entity.entity_type == "load")
        self.assertEqual({"amount": 20, "unit": "kg"}, load.value)
        self.assertTrue(load.attributes["per_side"])

    def test_relative_dates_and_weekdays_receive_source_and_target_roles(self) -> None:
        signatures = self.signatures("move o treino de hoje para amanhã")
        self.assertIn(("source_date", '"2026-10-07"'), signatures)
        self.assertIn(("target_date", '"2026-10-08"'), signatures)

        weekday_signatures = self.signatures("passa de segunda para sexta")
        self.assertIn(("source_date", '"2026-10-12"'), weekday_signatures)
        self.assertIn(("target_date", '"2026-10-16"'), weekday_signatures)

    def test_absolute_dates_are_validated_and_resolved(self) -> None:
        self.assert_entity("treino em 15/10", "target_date", "2026-10-15")
        signatures = self.signatures("treino em 31/02")
        self.assertFalse(any(item[0].endswith("date") for item in signatures))

    def test_two_schedule_dates_are_not_mistaken_for_a_move(self) -> None:
        signatures = self.signatures("treino segunda e cardio sexta")
        self.assertNotIn(("source_date", '"2026-10-12"'), signatures)
        self.assertIn(("target_date", '"2026-10-12"'), signatures)
        self.assertIn(("target_date", '"2026-10-09"'), signatures)

    def test_goals_preferences_limitations_and_restrictions(self) -> None:
        text = (
            "quero hipertrofia, não gosto de peixe, não consigo fazer "
            "agachamento por causa do joelho e sou vegetariano"
        )
        signatures = self.signatures(text)
        self.assertIn(("goal", '"hipertrofia"'), signatures)
        self.assertIn(("dietary_restriction", '"vegetariano"'), signatures)
        self.assertTrue(any(item[0] == "preference" for item in signatures))
        self.assertTrue(any(item[0] == "limitation" for item in signatures))
        self.assertIn(("body_part", '"joelho"'), signatures)

    def test_food_amount_macronutrient_and_sleep_duration(self) -> None:
        signatures = self.signatures(
            "no café comi 60 g de aveia e 3 ovos; bati 150 g de proteína e dormi 6 horas"
        )
        self.assertIn(("meal", '"cafe da manha"'), signatures)
        self.assertIn(("food", '"aveia"'), signatures)
        self.assertIn(("food", '"ovo"'), signatures)
        self.assertIn(("amount", '{"amount": 60, "unit": "g"}'), signatures)
        self.assertIn(
            ("macronutrient_amount", '{"amount": 150, "unit": "g"}'),
            signatures,
        )
        self.assertIn(
            (
                "sleep_duration",
                '{"amount": 6, "seconds": 21600, "unit": "hour"}',
            ),
            signatures,
        )

    def test_all_emitted_types_exist_in_taxonomy(self) -> None:
        taxonomy = json.loads(
            (AI_ROOT / "data" / "taxonomy" / "entities.v1.json").read_text(
                encoding="utf-8"
            )
        )
        allowed = {item["id"] for item in taxonomy["entities"]}
        result = extract_entities(
            "amanhã troca supino por flexão, faz 4x10 com 30 kg; "
            "não gosto de peixe e quero hipertrofia",
            self.catalog,
            self.reference,
        )
        self.assertTrue({item.entity_type for item in result.entities} <= allowed)

    def test_empty_and_excessive_text_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            extract_entities(" ", self.catalog, self.reference)
        with self.assertRaises(ValueError):
            extract_entities("a" * 10_001, self.catalog, self.reference)

    def test_frozen_regression_examples_remain_exact(self) -> None:
        dataset = AI_ROOT / "data" / "entities" / "evaluation.v1.jsonl"
        rows = [
            json.loads(line)
            for line in dataset.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(40, len(rows))
        for row in rows:
            with self.subTest(row=row["id"]):
                result = extract_entities(
                    row["text"],
                    self.catalog,
                    date.fromisoformat(row["reference_date"]),
                )
                score = score_entity_predictions(row["expected"], result.entities)
                self.assertTrue(score["exact"], row["text"])

    def test_entity_artifact_manifest_hashes_are_current(self) -> None:
        manifest_path = (
            AI_ROOT / "artifacts" / "entities" / "1.0.0" / "manifest.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertFalse(manifest["safety"]["planner_writes"])
        self.assertTrue(manifest["safety"]["requires_downstream_validation"])
        for item in manifest["files"].values():
            path = AI_ROOT / item["path"]
            observed = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(item["sha256"], observed, item["path"])


if __name__ == "__main__":
    unittest.main()
