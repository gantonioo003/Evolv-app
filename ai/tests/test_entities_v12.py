from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))

from evolv_nlp.entities import EntityCatalog, entity_signature, extract_entities as extract_legacy, load_entity_catalog  # noqa: E402
from evolv_nlp.entities_v12 import EXTRA_ENTITY_TYPES, extract_entities, supported_entity_types  # noqa: E402


class EntityEnrichmentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_entity_catalog(AI_ROOT / "data/catalogs/entity_catalogs.v1.json")
        cls.reference = date(2026, 10, 7)

    def extract(self, text: str):
        result = extract_entities(text, self.catalog, self.reference)
        for entity in result.entities:
            self.assertEqual(text[entity.start:entity.end], entity.text)
            self.assertTrue(0 <= entity.start < entity.end <= len(text))
        return result

    def of_type(self, text: str, kind: str):
        return [entity for entity in self.extract(text).entities if entity.entity_type == kind]

    def test_opt_in_version_and_legacy_behavior_are_separate(self) -> None:
        text = "peso 80 kg"
        legacy_result = extract_legacy(text, self.catalog, self.reference)
        result = self.extract(text)
        self.assertEqual("1.0.0", legacy_result.extractor_version)
        self.assertEqual("1.1.0", result.extractor_version)
        self.assertEqual(legacy_result.catalog_version, result.catalog_version)
        self.assertEqual(legacy_result.reference_date, result.reference_date)
        self.assertEqual("load", legacy_result.entities[0].entity_type)
        self.assertEqual("body_measurement", result.entities[0].entity_type)
        self.assertEqual(set(legacy_result.to_dict()), set(result.to_dict()))

    def test_development_regression_keeps_historical_signatures(self) -> None:
        # Development examples only; no frozen validation or independent test input.
        path = AI_ROOT / "data/entities/evaluation.v1.jsonl"
        for row in map(json.loads, path.read_text(encoding="utf-8").splitlines()):
            with self.subTest(row=row["id"]):
                result = extract_entities(row["text"], self.catalog, date.fromisoformat(row["reference_date"]))
                self.assertCountEqual([entity_signature(entity) for entity in result.entities], [entity_signature(entity) for entity in row["expected"]])

    def test_decimal_quantities_and_portuguese_thousands(self) -> None:
        cases = (
            ("supino com 2,5 kg", "load", {"amount": 2.5, "unit": "kg"}),
            ("bebi 1.5 litros", "amount", {"amount": 1.5, "unit": "litros"}),
            ("meta 2.400 kcal", "energy_amount", {"amount": 2400, "unit": "kcal"}),
            ("meta 2.400,5 calorias", "energy_amount", {"amount": 2400.5, "unit": "kcal"}),
            ("descanso de 1,5 minutos", "rest_duration", {"amount": 1.5, "unit": "minute", "seconds": 90}),
        )
        for text, kind, value in cases:
            with self.subTest(text=text):
                self.assertEqual([value], [entity.value for entity in self.of_type(text, kind)])

    def test_compact_repetitions_do_not_swallow_load(self) -> None:
        text = "legpress 3x10 120 kg"
        self.assertEqual([10], [entity.value for entity in self.of_type(text, "repetitions")])
        self.assertEqual([{"amount": 120, "unit": "kg"}], [entity.value for entity in self.of_type(text, "load")])
        self.assertEqual([{"minimum": 10, "maximum": 12}], [entity.value for entity in self.of_type("leg press 3\u00d710\u201312 com 120kg", "repetitions")])

    def test_body_weight_load_food_mass_and_unknown_mass_are_distinct(self) -> None:
        text = "peso cerca de 80kg; supino com 30kg cada lado; comprei 1kg de frango"
        self.assertEqual([{"amount": 80, "unit": "kg", "measurement": "body_weight"}], [entity.value for entity in self.of_type(text, "body_measurement")])
        load = self.of_type(text, "load")
        self.assertEqual([{"amount": 30, "unit": "kg"}], [entity.value for entity in load])
        self.assertTrue(load[0].attributes["per_side"])
        self.assertEqual([{"amount": 1, "unit": "kg"}], [entity.value for entity in self.of_type(text, "amount")])
        self.assertEqual([{"amount": 1, "unit": "kg"}], [entity.value for entity in self.of_type("tenho 1kg de frango", "amount")])
        self.assertEqual([{"amount": 30, "unit": "kg"}], [entity.value for entity in self.of_type("tenho 30kg no supino", "load")])
        for text in ("Iniciante, 80 kg", "quero perder 12,3kg", "peso 105-106 kg", "3,6kg de um produto desconhecido"):
            with self.subTest(text=text):
                self.assertEqual([], self.of_type(text, "load"))

    def test_body_weight_change_does_not_become_current_weight(self) -> None:
        entities = self.of_type("perdi 12,3 kg", "body_measurement")
        self.assertEqual([{"amount": 12.3, "unit": "kg", "measurement": "body_weight_change"}], [entity.value for entity in entities])

    def test_unknown_mass_is_a_candidate_not_a_forced_load(self) -> None:
        entity = self.of_type("Iniciante, 80 kg", "ambiguous_weight")[0]
        self.assertEqual({"amount": 80, "unit": "kg"}, entity.value)
        self.assertTrue(entity.attributes["requires_context"])
        self.assertEqual(["load", "body_measurement", "amount"], entity.attributes["candidates"])

    def test_macro_link_is_local_and_handles_prefix(self) -> None:
        text = "creatina 5g e proteina: 150g; 60 g de aveia. 90 g de carboidratos"
        self.assertEqual([5, 60], [entity.value["amount"] for entity in self.of_type(text, "amount")])
        self.assertEqual([150, 90], [entity.value["amount"] for entity in self.of_type(text, "macronutrient_amount")])

    def test_ratios_and_pace_are_not_absolute_quantities(self) -> None:
        entities = self.of_type("proteina 2,5g/kg", "macronutrient_amount")
        self.assertEqual({"amount": 2.5, "unit": "g"}, entities[0].value)
        self.assertEqual("kg", entities[0].attributes["per_unit"])
        self.assertEqual([], self.of_type("5:30 min/km", "duration"))
        self.assertEqual([], self.of_type("exame 5g/dL", "amount"))

    def test_six_extension_types_use_literal_units_and_distinct_spans(self) -> None:
        cases = (
            ("corro 5km", "distance", {"amount": 5, "unit": "km"}),
            ("caminhada a 4,5km/h", "speed", {"amount": 4.5, "unit": "km/h"}),
            ("pace 5:30 min/km", "pace", {"amount": 5.5, "unit": "min/km", "seconds_per_km": 330}),
            ("frequencia 173bpm", "heart_rate", {"amount": 173, "unit": "bpm"}),
            ("testo 200ng/dL", "lab_measurement", {"amount": 200, "unit": "ng/dL"}),
            ("80kg", "ambiguous_weight", {"amount": 80, "unit": "kg"}),
        )
        for text, kind, value in cases:
            with self.subTest(kind=kind):
                self.assertEqual([value], [entity.value for entity in self.of_type(text, kind)])
        self.assertEqual([], self.of_type("5km/h", "distance"))
        self.assertEqual([], self.of_type("teste 107mg/dL", "amount"))
        self.assertEqual([], self.of_type("altura: 1,72m", "distance"))
        self.assertEqual([{"amount": 400, "unit": "m"}], [entity.value for entity in self.of_type("corro 400 metros", "distance")])

    def test_existing_types_receive_subtypes_without_new_ids(self) -> None:
        age = self.of_type("tenho 15 anos", "age_group")[0]
        self.assertEqual({"amount": 15, "unit": "year"}, age.value)
        self.assertEqual("numeric_age", age.attributes["subtype"])
        height = self.of_type("altura: 186cm", "body_measurement")[0]
        self.assertEqual({"measurement": "height", "amount": 186, "unit": "cm"}, height.value)
        fat = self.of_type("BF de 22%", "body_measurement")[0]
        self.assertEqual("body_fat_percent", fat.attributes["subtype"])
        hydration = self.of_type("bebo 5l de agua", "amount")[0]
        self.assertEqual("hydration", hydration.attributes["subtype"])
        measurements = self.of_type("1,72 de altura e 30cm de braco", "body_measurement")
        self.assertEqual(["circumference"], [entity.attributes["subtype"] for entity in measurements])

    def test_clinical_doses_preserve_amount_and_cadence_without_totals(self) -> None:
        text = "oxandrolona 15mg de 6 em 6 horas ou 20mg a cada 8 horas"
        doses = self.of_type(text, "amount")
        self.assertEqual([{"amount": 15, "unit": "mg"}, {"amount": 20, "unit": "mg"}], [entity.value for entity in doses])
        self.assertEqual(["de 6 em 6 horas", "a cada 8 horas"], [entity.attributes["cadence_text"] for entity in doses])
        self.assertTrue(all(entity.attributes["clinical"] for entity in doses))
        self.assertEqual([{"amount": 0.5, "unit": "mg"}], [entity.value for entity in self.of_type("anastrozol 0,5mg", "amount")])
        self.assertTrue(self.of_type("1,5ml de durateston", "amount")[0].attributes["clinical"])

    def test_schedule_is_not_pace_or_duration(self) -> None:
        schedules = self.of_type("treino as 7h e jantar as 19:30", "schedule")
        self.assertEqual([{"time": "07:00"}, {"time": "19:30"}], [entity.value for entity in schedules])
        self.assertEqual([], self.of_type("treino as 7h", "duration"))
        self.assertEqual([], self.of_type("treino as 5:30/km", "schedule"))
        self.assertEqual([], self.of_type("treino de 2h", "schedule"))

    def test_duration_context_does_not_cross_sentences_or_activity(self) -> None:
        for text in ("dormi 6 horas; treino de 1 hora", "dormi 6 horas e treino de 1 hora"):
            with self.subTest(text=text):
                self.assertEqual([6], [entity.value["amount"] for entity in self.of_type(text, "sleep_duration")])
                self.assertEqual([1], [entity.value["amount"] for entity in self.of_type(text, "duration")])

    def test_preferences_stop_at_punctuation_and_new_predicate(self) -> None:
        for text in ("nao gosto de peixe. Prefiro arroz.", "nao gosto de peixe e gosto de arroz"):
            with self.subTest(text=text):
                entities = self.of_type(text, "preference")
                self.assertEqual(["negative", "positive"], [entity.value["polarity"] for entity in entities])
                self.assertEqual("nao gosto de peixe", entities[0].text)
        self.assertEqual([], self.of_type("nao prefiro peixe", "preference"))

    def test_negated_mentions_do_not_look_like_asserted_allergies(self) -> None:
        allergy = self.of_type("nao sou alergico a leite", "allergy")[0]
        restriction = self.of_type("nao sou vegetariano", "dietary_restriction")[0]
        self.assertTrue(allergy.attributes["negated"])
        self.assertTrue(restriction.attributes["negated"])
        self.assertNotIn("negated", self.of_type("sou alergico a leite", "allergy")[0].attributes)
        self.assertNotIn("negated", self.of_type("sou vegetariano", "dietary_restriction")[0].attributes)
        self.assertNotIn("negated", self.of_type("sem lactose", "dietary_restriction")[0].attributes)
        self.assertTrue(self.of_type("nao tenho mais alergia a leite", "allergy")[0].attributes["negated"])

    def test_third_party_and_hypothetical_context_is_explicit(self) -> None:
        allergy = self.of_type("minha irma tem alergia a leite", "allergy")[0]
        self.assertEqual("other", allergy.attributes["subject"])
        self.assertTrue(allergy.attributes["requires_context"])
        self.assertTrue(self.of_type("e se eu tiver alergia a leite?", "allergy")[0].attributes["hypothetical"])

    def test_replacement_needs_local_affirmed_verb(self) -> None:
        for text in ("faco supino por 30 minutos e depois agachamento", "nao troca supino por flexao", "troca supino. Depois faco flexao"):
            with self.subTest(text=text):
                self.assertEqual([], self.of_type(text, "replacement_exercise"))
        self.assertEqual(["flexao de bracos"], [entity.value for entity in self.of_type("troca supino por flexao", "replacement_exercise")])

    def test_unicode_expansions_and_combining_marks_preserve_offsets(self) -> None:
        text = "\U0001f4aa \ufb03\ufb03 troca supino por flexa\u0303o; comi mac\u0327a\u0303"
        result = self.extract(text)
        self.assertEqual(["flexa\u0303o"], [entity.text for entity in result.entities if entity.entity_type == "replacement_exercise"])
        self.assertEqual(["mac\u0327a\u0303"], [entity.text for entity in result.entities if entity.entity_type == "food"])

    def test_aliases_are_catalog_gated_and_have_word_boundaries(self) -> None:
        self.assertEqual(["leg press"], [entity.value for entity in self.of_type("fiz legpress", "exercise")])
        self.assertEqual(["halteres"], [entity.value for entity in self.of_type("um haltere", "equipment")])
        self.assertEqual(["supino reto com halteres"], [entity.value for entity in self.of_type("supino com halter", "exercise")])
        self.assertEqual(["flexoes de braco"], [entity.text for entity in self.of_type("flexoes de braco", "exercise")])
        smaller = EntityCatalog(self.catalog.version, self.catalog.language, tuple(entry for entry in self.catalog.entries if entry.canonical != "leg press"))
        self.assertEqual((), extract_entities("legpress", smaller, self.reference).entities)
        self.assertEqual([], self.of_type("antilegpress", "exercise"))

    def test_informal_frequency_and_invalid_input(self) -> None:
        for text in ("treino 3x na semana", "treino tres vezes na semana"):
            self.assertEqual([3], [entity.value for entity in self.of_type(text, "weekly_frequency")])
        for text in ("", " " * 10, "a" * 10_001):
            with self.subTest(length=len(text)), self.assertRaises(ValueError):
                self.extract(text)

    def test_output_types_remain_in_existing_taxonomy(self) -> None:
        allowed = {entry["id"] for entry in json.loads((AI_ROOT / "data/taxonomy/entities.v1.json").read_text(encoding="utf-8"))["entities"]}
        extension = json.loads((AI_ROOT / "data/taxonomy/expansion.v1.1.json").read_text(encoding="utf-8"))
        extras = {entry["id"] for entry in extension["entities"]}
        self.assertEqual(EXTRA_ENTITY_TYPES, extras)
        self.assertEqual(85, len(allowed | extras))
        self.assertEqual(39, len(supported_entity_types(self.catalog)))
        text = "peso 80 kg; supino com halter 3x10 com 20kg; meta 2400 kcal; nao sou alergico a leite"
        self.assertTrue({entity.entity_type for entity in self.extract(text).entities} <= allowed | extras)


if __name__ == "__main__":
    unittest.main()
