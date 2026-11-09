import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import date
from pathlib import Path

import numpy as np

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.review_release import (choose_partition, input_fingerprint, labels, load_partition,
                                     model_text, read_workbook, validate_isolation)
from evolv_nlp.review_training import (choose_thresholds, confidence_policy, intent_metrics,
                                      risk_matrix, risk_metrics)
from evolv_nlp.entities_v14 import extract_entities, load_catalog, supported_entity_types, RULES
from evolv_nlp.risk_rules_v14 import detect_risks, SUPPORTED_RISKS
from evolv_nlp.pipeline_v14 import decide_route
from evolv_nlp.review_training import load_hashed_payload
from evolv_nlp.dataset import file_sha256
from evolv_nlp.context_data import frozen_fingerprints


class WorkbookTests(unittest.TestCase):
    def test_streaming_headers_are_not_assumed_to_be_row_one(self):
        import openpyxl
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.xlsx"
            book = openpyxl.Workbook()
            sheet = book.active
            sheet.title = "Revisao"
            sheet.append(["Instructions, not data"])
            sheet.append([])
            sheet.append(["id_mensagem", "texto_original", "intenção_principal"])
            sheet.append(["one", "treino curto", "adapt_training_plan"])
            book.save(path)
            book.close()
            self.assertEqual("adapt_training_plan", read_workbook(path)[0]["intenção_principal"])

    def test_lists_and_none(self):
        self.assertEqual(["a", "b"], labels("a; b; a"))
        self.assertEqual([], labels("nenhuma"))
        self.assertEqual(["none"], labels(["none"]))

    def test_source_partitions_are_respected(self):
        self.assertEqual("test", choose_partition("public", {"split": "test"}, {}))
        self.assertEqual("external_human_language", choose_partition("survey", {}, {}))
        self.assertEqual("train", choose_partition("rare_synthetic", {}, {}))
        seed = {"is_synthetic": True, "leakage_group_id": "coach_seed_collection_2026_10_14"}
        self.assertEqual("external_synthetic", choose_partition("coach", {}, seed))
        with self.assertRaises(ValueError):
            choose_partition("public", {"split": "train_candidate"}, {})

    def test_context_is_part_of_input_without_annotation_notes(self):
        self.assertNotEqual(input_fingerprint("sim", "trocar o arroz?"), input_fingerprint("sim", "mover treino?"))
        self.assertEqual("oi", model_text("oi"))

    def test_group_leakage_is_rejected(self):
        rows = [{"id": "a", "input_fingerprint": "a", "group_id": "g", "partition": "train"},
                {"id": "b", "input_fingerprint": "b", "group_id": "g", "partition": "test"}]
        with self.assertRaises(ValueError):
            validate_isolation(rows)

    def test_actual_release_counts_groups_and_checksums(self):
        output = AI_ROOT / "data/releases/1.7.0"
        manifest = json.loads((output / "manifest.json").read_text("utf-8"))
        self.assertEqual(12179, manifest["total_imported"])
        rows = []
        for part in manifest["coverage"]:
            rows.extend(load_partition(AI_ROOT, part))
        validate_isolation(rows)
        self.assertEqual(12179, len(rows))
        for name, digest in manifest["files"].items():
            self.assertEqual(digest, file_sha256(output / name))
        training = [r for r in rows if r["partition"] == "train"]
        self.assertFalse(any(r["source_family"] == "survey" for r in training))
        self.assertEqual(60, len({r["label"] for r in training}))
        self.assertEqual(1480, sum(r["source_family"] == "rare_synthetic" for r in training))
        self.assertFalse(any("INDEFIN" in r["label"] for r in training))
        self.assertFalse(any(r["quarantine_reasons"] for r in training))
        self.assertEqual(manifest["protected_fingerprints"], frozen_fingerprints(AI_ROOT))


class EvaluationContractTests(unittest.TestCase):
    def test_untrusted_hash_or_path_never_reaches_pickle_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "model.joblib"
            path.write_bytes(b"not a model")
            with patch("evolv_nlp.review_training.joblib.load") as loader:
                with self.assertRaises(ValueError):
                    load_hashed_payload(root, {"file": "model.joblib", "sha256": "incorrect"})
                with self.assertRaises(ValueError):
                    load_hashed_payload(root, {"file": "../model.joblib", "sha256": "incorrect"})
                loader.assert_not_called()
    def test_risks_are_multi_label_and_none_is_derived(self):
        rows = [{"risks": ["none"]}, {"risks": ["pain", "drug"]}]
        truth = risk_matrix(rows, ["pain", "drug"])
        self.assertEqual([[0, 0], [1, 1]], truth.tolist())
        report = risk_metrics(truth, truth, ["pain", "drug"])
        self.assertEqual(1.0, report["micro_f1"])
        self.assertEqual(1.0, report["exact_match_accuracy"])

    def test_unobserved_classes_are_explicit_not_pretend_measured(self):
        report = intent_metrics(["a", "a"], ["a", "a"], ["a", "b"])
        self.assertEqual(1.0, report["macro_f1_supported"])
        self.assertEqual(0.5, report["macro_f1_all_declared"])
        self.assertEqual(["b"], report["unsupported_classes"])

    def test_thresholds_and_abstention(self):
        truth = np.array([[0, 0], [1, 0], [1, 1], [0, 0]])
        scores = np.array([[0.1, 0.2], [0.8, 0.3], [0.9, 0.8], [0.2, 0.1]])
        thresholds = choose_thresholds(truth, scores)
        self.assertEqual((2,), thresholds.shape)
        policy = confidence_policy(["a"] * 10, ["a"] * 10, np.ones(10))
        self.assertIsNone(policy["margin_threshold"])
        self.assertFalse(policy["is_calibrated_probability"])


class EnrichedEntityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog(AI_ROOT)

    def extract(self, text):
        result = extract_entities(text, self.catalog, date(2026, 10, 18))
        for entity in result.entities:
            self.assertEqual(text[entity.start:entity.end], entity.text)
        return result.entities

    def test_new_rule_types_have_positive_span_cases(self):
        cases = {
            "action_scope": "so hoje", "change_direction": "quero reduzir o volume",
            "context_reference": "esse mesmo", "pending_action": "pode aplicar",
            "previous_action": "desfaz a ultima troca", "negation": "nao quero",
            "certainty": "talvez", "request_priority": "minha prioridade e o sono",
            "plan_scope": "treino de hoje", "meal_context": "dia de descanso",
            "budget": "ate 300 reais", "work_schedule": "trabalho a noite",
            "weekday": "na terca-feira", "storage_duration": "guardar por 3 dias",
            "goal_timeframe": "quero emagrecer em 12 semanas",
            "competition_date": "campeonato em novembro", "time_period": "ultimas quatro semanas",
        }
        self.assertEqual(set(RULES), set(cases))
        for kind, text in cases.items():
            with self.subTest(kind=kind):
                self.assertTrue(any(e.entity_type == kind for e in self.extract(text)))

    def test_new_catalog_types_have_explicit_cases(self):
        cases = {"training_metric": "volume", "intensity": "cardio leve", "nutrient": "proteinas",
                 "medical_condition": "tenho diabetes", "medication": "tomo sertralina",
                 "supplement": "creatina", "cooking_method": "grelhar o frango",
                 "serving_unit": "duas fatias", "location_environment": "treino no hotel",
                 "range_of_motion": "amplitude completa", "training_level": "sou iniciante",
                 "hunger_level": "estou com muita fome", "stress_level": "semana tranquila"}
        for kind, text in cases.items():
            with self.subTest(kind=kind):
                self.assertTrue(any(e.entity_type == kind for e in self.extract(text)))

    def test_negated_conditions_and_other_person_are_not_asserted(self):
        conditions = [e for e in self.extract("nao tenho diabetes") if e.entity_type == "medical_condition"]
        self.assertTrue(conditions[0].attributes["negated"])
        conditions = [e for e in self.extract("minha mae tem diabetes") if e.entity_type == "medical_condition"]
        self.assertEqual("other", conditions[0].attributes["subject"])

    def test_ambiguous_adjectives_are_not_training_parameters(self):
        kinds = {e.entity_type for e in self.extract("dor leve e pressao alta, posso treinar?")}
        self.assertNotIn("intensity", kinds)
        self.assertFalse(any(e.entity_type == "range_of_motion" for e in self.extract("resposta completa")))

    def test_supported_is_not_measured_recall(self):
        taxonomy = json.loads((AI_ROOT / "data/releases/1.7.0/taxonomy.json").read_text("utf-8"))
        active = supported_entity_types(self.catalog)
        self.assertEqual(81, len(active))
        self.assertTrue(active <= {r["id"] for r in taxonomy["entities"]})


class ReviewedSafetyTests(unittest.TestCase):
    def test_risk_coverage(self):
        self.assertEqual(21, len(set(SUPPORTED_RISKS)))

    def test_medication_context_is_not_dose(self):
        result = detect_risks("Uso sertralina e quero treinar")
        self.assertIn("medication_or_substance_context", result.risks)
        self.assertNotIn("medication_or_hormone", result.risks)
        self.assertNotIn("medication_or_substance_context", detect_risks("Nao uso sertralina").risks)

    def test_illness_is_active_personal_and_related_to_activity(self):
        self.assertIn("acute_illness_signal", detect_risks("Estou gripado e quero treinar").risks)
        self.assertNotIn("acute_illness_signal", detect_risks("Tive gripe ano passado e quero treinar").risks)
        self.assertNotIn("acute_illness_signal", detect_risks("O que e gripe?").risks)

    def test_systemic_not_generic_educational_or_negated(self):
        self.assertIn("systemic_symptom_signal", detect_risks("Estou com tontura agora").risks)
        for text in ("Nao tenho tontura", "O que e tontura?", "Se eu tiver tontura devo parar?"):
            self.assertNotIn("systemic_symptom_signal", detect_risks(text).risks)

    def test_urgent_and_pain_boundaries(self):
        result = detect_risks("Sinto dor no peito agora")
        self.assertIn("emergency_symptom", result.risks)
        self.assertNotIn("pain_or_possible_injury", result.risks)
        self.assertIn("pain_or_possible_injury", detect_risks("Sinto dor no joelho agora").risks)

    def test_planner_is_never_authorized_by_short_text(self):
        self.assertEqual("clarify_pending_action", decide_route("confirm_planner_action", True, []))
        self.assertEqual("review_pending_action", decide_route("confirm_planner_action", True, [], {"id": "trusted"}))
        self.assertEqual("clarify", decide_route("replace_exercise", False, []))
        self.assertEqual("safety_information_only", decide_route("replace_exercise", True, ["pain_or_possible_injury"]))
        self.assertEqual("clarify", decide_route("adjust_training_volume", True, [], negated_change=True))


@unittest.skipUnless((AI_ROOT / "artifacts/baseline/1.6.0/manifest.json").exists(), "Models not finalized yet")
class TrainedReleaseTests(unittest.TestCase):
    def test_both_winners_frozen_and_every_message_processed(self):
        path = AI_ROOT / "artifacts/baseline/1.6.0"
        manifest = json.loads((path / "manifest.json").read_text("utf-8"))
        self.assertEqual(40, manifest["trial_count"])
        self.assertEqual(12179, manifest["all_imported_records_processed"])
        self.assertFalse(manifest["automatically_promoted_to_app"])
        self.assertEqual({"intent", "risk"}, set(manifest["models"]))
        frozen = json.loads((path / "selection_frozen.json").read_text("utf-8"))
        self.assertFalse(frozen["test_opened"])
        self.assertEqual(frozen["models"], manifest["models"])
        for task, metadata in manifest["models"].items():
            payload = load_hashed_payload(path, metadata)
            self.assertEqual(60 if task == "intent" else 20, len(payload["classes"]))
        for name, digest in manifest["source_files"].items():
            self.assertEqual(digest, file_sha256(AI_ROOT / name))

    def test_live_pipeline_has_topics_and_never_writes(self):
        from evolv_nlp.pipeline_v14 import ReviewedCoachPipeline
        result = ReviewedCoachPipeline(AI_ROOT).analyze("Nao quero mudar o treino de hoje")
        self.assertFalse(result["planner"]["writes_allowed"])
        self.assertTrue(result["planner"]["requires_confirmation"])
        self.assertIn("topics", result)
        self.assertFalse(result["privacy"]["automatic_training"])
        self.assertTrue(result["response_constraints"]["no_diagnosis"])
        json.dumps(result)


if __name__ == "__main__":
    unittest.main()
