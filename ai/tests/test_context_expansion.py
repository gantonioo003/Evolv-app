from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_nlp.entities_v13 import extract_entities, load_catalog, supported_entity_types
from evolv_nlp.privacy import review_text, training_permission
from evolv_nlp.response_policy import response_scope
from evolv_nlp.risk_rules_v13 import detect_risks
from evolv_nlp.training_v13 import taxonomy, parent_labels
from evolv_nlp.conversation import analyze_conversation


class PrivacyTests(unittest.TestCase):
    def test_removes_direct_identifiers_without_claiming_anonymization(self):
        text = "meu email e alguem@example.com; @pessoa; https://site.example/perfil; 123.456.789-09"
        result = review_text(text)
        self.assertNotIn("example.com", result.minimized_text)
        self.assertNotIn("@pessoa", result.minimized_text)
        self.assertNotIn("123.456", result.minimized_text)
        self.assertFalse(result.anonymization_verified)
        self.assertNotIn("minimized_text", result.summary())

    def test_public_source_and_redaction_do_not_authorize_training(self):
        report = training_permission({"rights_status": "unverified", "review_status": "human_reviewed",
            "privacy_review_status": "approved", "authorization": {"status": "approved", "purposes": ["nlu_training"]}})
        self.assertFalse(report["allowed"])
        self.assertIn("source_rights_unverified", report["reasons"])
        self.assertIn("authorization_evidence_missing", report["reasons"])

    def test_revocation_and_separate_purposes(self):
        row = {"rights_status": "verified", "privacy_review_status": "approved", "review_status": "human_reviewed",
               "authorization": {"status": "approved", "purposes": ["nlu_training"], "evidence_reference": "local/consent-001",
                   "lawful_basis_review_reference": "local/review-001"}}
        self.assertTrue(training_permission(row)["allowed"])
        self.assertFalse(training_permission(row, "lm_training")["allowed"])
        row["authorization"]["withdrawn"] = True
        self.assertFalse(training_permission(row)["allowed"])

    def test_minors_sensitive_and_third_party_are_flagged(self):
        flags = review_text("tenho 16 anos e minha mae tem diabetes e dor").flags
        self.assertIn("possible_minor", flags)
        self.assertIn("possible_sensitive_personal_data", flags)
        self.assertIn("third_party_context", flags)

    def test_owned_synthetic_requires_label_review(self):
        self.assertFalse(training_permission({"provenance": "project_authored_synthetic"})["allowed"])
        self.assertTrue(training_permission({"provenance": "project_authored_synthetic", "review_status": "assistant_reviewed_synthetic"})["allowed"])


class ContextEntityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog(AI_ROOT)

    def entities(self, text, kind):
        result = extract_entities(text, self.catalog, date(2026, 10, 10))
        for e in result.entities:
            self.assertEqual(text[e.start:e.end], e.text)
        return [e for e in result.entities if e.entity_type == kind]

    def test_drink_volume_is_not_clinical_dose(self):
        self.assertEqual(1500, self.entities("bebi 1,5 l de agua", "drink_volume")[0].value["amount_ml"])
        self.assertEqual([], self.entities("uso 2 ml de medicamento", "drink_volume"))

    def test_cadence_is_not_pulse_or_speed(self):
        self.assertEqual(170, self.entities("corri a 170 passos/min", "cadence")[0].value["amount"])
        self.assertEqual("rpm", self.entities("pedalei a 85 rpm", "cadence")[0].value["unit"])
        self.assertEqual([], self.entities("pulso 160/min e velocidade 12 km/h", "cadence"))

    def test_experience_and_terrain(self):
        self.assertEqual(3, self.entities("treino ha 3 anos", "training_experience")[0].value["amount"])
        self.assertEqual(230, self.entities("percurso com desnivel de 230 m", "elevation_gain")[0].value["amount"])

    def test_reported_pain_is_not_diagnosis(self):
        self.assertEqual("right", self.entities("dor no joelho direito", "laterality")[0].value)
        self.assertEqual(3, self.entities("dor 3/10", "pain_severity")[0].value["amount"])
        self.assertEqual(4, self.entities("dor no ombro ha 4 dias", "symptom_onset")[0].value["amount"])

    def test_foods_aliases_tempo_and_meals(self):
        self.assertEqual("macaxeira", self.entities("como aipim", "food")[0].value)
        self.assertTrue(self.entities("faço hip thrust", "exercise"))
        self.assertEqual([3, 1, 2], self.entities("cadencia 3-1-2", "movement_tempo")[0].value["phases_seconds"])
        self.assertEqual(4, self.entities("4 refeicoes por dia", "meal_frequency")[0].value)

    def test_declared_vs_supported_types(self):
        definitions = taxonomy(AI_ROOT)
        self.assertEqual(41, len(definitions["intents"]))
        self.assertEqual(18, len(definitions["risks"]))
        self.assertEqual(89, len(definitions["entities"]))
        self.assertTrue(supported_entity_types(self.catalog) <= set(definitions["entities"]))
        self.assertEqual(["ask_training_concept"], parent_labels(["ask_cardio_training"], definitions["intents"]))


class SafetyBoundaryTests(unittest.TestCase):
    def test_current_pipeline_preserves_urgency_and_blocks_clinical_proposal(self):
        from evolv_nlp.pipeline_v13 import ContextCoachPipeline
        pipeline = ContextCoachPipeline(AI_ROOT)
        for text, route in [("Sinto dor no peito agora e quero continuar treinando", "emergency_guidance"),
                            ("Quero me matar", "crisis_guidance"),
                            ("Torci o tornozelo e nao consigo apoiar", "professional_referral")]:
            with self.subTest(text=text):
                result = pipeline.analyze(text, date(2026, 10, 10))
                self.assertEqual(route, result["decision"]["route"])
                self.assertIsNone(result["proposal"])
                self.assertFalse(result["writes_allowed"])

    def test_discomfort_blocks_rehabilitation_but_does_not_diagnose(self):
        result = response_scope("Estou com desconforto no joelho, me passe exercicios de explosao para curar")
        self.assertEqual("general_pain_information", result["mode"])
        self.assertTrue(result["planner_proposal_blocked"])
        self.assertFalse(result["is_diagnosis"])

    def test_healthy_performance_request_stays_open(self):
        result = response_scope("Quero entender explosao para volei, nao tenho dor ou lesao")
        self.assertFalse(result["planner_proposal_blocked"])

    def test_red_flags_and_stimulants_are_contextual(self):
        self.assertIn("musculoskeletal_red_flag", detect_risks("Torci o tornozelo e nao consigo apoiar").risks)
        self.assertIn("stimulant_adverse_signal", detect_risks("Tomei cafeina e estou com palpitacao").risks)
        self.assertNotIn("stimulant_adverse_signal", detect_risks("O que e palpitacao relacionada a cafeina?").risks)
        self.assertNotIn("pain_or_possible_injury", detect_risks("Nao tenho desconforto no joelho").risks)

    def test_urgency_precedes_training_request(self):
        report = response_scope("Sinto dor no peito agora e quero continuar treinando")
        self.assertEqual("urgent_referral", report["mode"])
        self.assertTrue(report["planner_proposal_blocked"])

    def test_conversation_reference_never_confirms_implicitly(self):
        class FakePipeline:
            catalog = load_catalog(AI_ROOT)
            def analyze(self, text, reference_date):
                return {"decision": {"status": "planner_preview", "route": "planner_preview", "reasons": []}, "proposal": {"writes_allowed": False}}
        messages = [{"role": "user", "content": "faco supino"}, {"role": "assistant", "content": "posso mudar sem confirmar"},
                    {"role": "user", "content": "troca esse"}]
        result = analyze_conversation(FakePipeline(), messages, date(2026, 10, 10))
        self.assertEqual("clarify", result["decision"]["status"])
        self.assertIsNone(result["proposal"])
        self.assertFalse(result["conversation_context"]["persistent_memory"])
        self.assertFalse(result["conversation_context"]["assistant_text_is_authorization"])

    def test_prior_pain_is_not_forgotten_for_plan_change(self):
        class FakePipeline:
            catalog = load_catalog(AI_ROOT)
            def analyze(self, text, reference_date):
                return {"decision": {"status": "planner_preview", "route": "planner_preview", "reasons": []}, "proposal": {}}
        result = analyze_conversation(FakePipeline(), [{"role": "user", "content": "Sinto dor no joelho"},
            {"role": "user", "content": "adiciona agachamento"}], date(2026, 10, 10))
        self.assertEqual("clarify", result["decision"]["status"])
        self.assertIsNone(result["proposal"])


if __name__ == "__main__":
    unittest.main()
