"""Synthetic development regressions; no frozen or external evaluation data."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evolv_nlp.risk_rules_v12 import (  # noqa: E402
    SUPPORTED_RISKS,
    detect_risks,
    normalize_with_offsets,
)


class RiskRulesV12Tests(unittest.TestCase):
    def assertRisks(self, text: str, expected: set[str]) -> None:
        result = detect_risks(text)
        self.assertEqual(set(result.risks), expected, result.to_dict())
        self.assertEqual(result.safety_assessment, "unknown")
        self.assertNotIn("none", result.risks)
        self.assertFalse(result.is_diagnosis)
        self.assertTrue(result.requires_review)
        for item in result.evidence:
            self.assertEqual(item.text, text[item.start:item.end])
            self.assertLess(item.start, item.end)

    def test_unmatched_never_means_safe(self) -> None:
        for text in ("", " ", "Bom dia", "posso misturar arroz e feijao?", "cansado depois do treino", "chest pain"):
            with self.subTest(text=text):
                self.assertRisks(text, set())
                self.assertEqual(detect_risks(text).status, "unmatched")

    def test_urgent_context(self) -> None:
        for text in ("Estou com dor no peito", "Desmaiei durante o treino", "Dor no peito durante supino?", "Nao consigo respirar", "Estou com falta de ar intensa", "Vomitei sangue agora"):
            with self.subTest(text=text):
                self.assertIn("emergency_symptom", detect_risks(text).risks)

    def test_negation_of_urgent_symptoms(self) -> None:
        for text in ("nao tenho dor no peito", "nao desmaiei", "nunca tive desmaio", "sem dor no peito nem desmaio", "Nao estou com falta de ar intensa", "Dor no peito nao tenho", "Desmaio nunca tive"):
            with self.subTest(text=text):
                self.assertRisks(text, set())
                self.assertTrue(all(item.status == "suppressed" for item in detect_risks(text).evidence))

    def test_local_negation_stops_at_contrast_and_sentence(self) -> None:
        for text in ("Nao tenho dor no peito, mas desmaiei", "Nao tenho dor no peito. Desmaiei agora", "Nao tenho dor no peito; desmaiei durante o treino", "Nao tenho dor no peito\nDesmaiei agora", "Nao so tenho dor no peito, estou com falta de ar intensa", "Nao tenho dor e desmaiei", "Nao tenho dor, estou sufocando"):
            with self.subTest(text=text):
                self.assertIn("emergency_symptom", detect_risks(text).risks)

    def test_educational_hypothetical_and_quoted_urgent_signals(self) -> None:
        for text in ("O que e dor no peito?", "Quais sao os sintomas de desmaio?", "Como evitar desmaio?", "Tenho medo de desmaiar e ter dor no peito", 'O artigo diz "dor no peito"', 'O livro diz "estou com dor no peito agora"', "Dor no peito?", "Se eu tiver dor no peito, o que fazer?", "Nao lembro se desmaiei"):
            with self.subTest(text=text):
                result = detect_risks(text)
                self.assertNotIn("emergency_symptom", result.risks)
                self.assertTrue(result.ambiguity_flag)
        self.assertIn("emergency_symptom", detect_risks("O que e dor no peito? Agora estou com dor no peito").risks)

    def test_fatigue_is_not_emergency(self) -> None:
        for text in ("Estou cansado", "Cansaco depois da corrida", "Tenho falta de ar ao correr", "Fadiga e calorias baixas", "Estou cansado no calor"):
            with self.subTest(text=text):
                self.assertNotIn("emergency_symptom", detect_risks(text).risks)

    def test_supplement_titles_and_pre_workout_food(self) -> None:
        for text in ("CREATINA presta?", "Whey vale a pena?", "Duvida sobre suplementacao", "Posso tomar pre-treino?", "Termogenico funciona?", "Creatinha vencida?"):
            with self.subTest(text=text):
                self.assertIn("supplement_uncertainty", detect_risks(text).risks)
        self.assertRisks("Esta receita e um bom pre-treino liquido?", set())
        self.assertRisks("O que comer na refeicao pre treino?", set())

    def test_medication_names_and_contextual_forum_aliases(self) -> None:
        for text in ("Como usar Durateston?", "Oxandrolona 15mg?", "Posso tomar tamoxifeno?", "Ciclo oxa e dura", "Ciclar stano com trembo", "Deca como base no ciclo", "Duvida TPC", "O que e pos-ciclo?", "Duvida ciclo E.C", "Semaglutida ou testosterona para cutting?"):
            with self.subTest(text=text):
                self.assertIn("medication_or_hormone", detect_risks(text).risks)
                self.assertNotIn("supplement_uncertainty", detect_risks(text).risks)
        for text in ("Meu treino dura uma hora", "Dieta dura funciona?", "Testosterona baixa?", "Nao uso oxandrolona", "Meu treino dura uma hora e tomo whey", "Posso tomar GH Max?"):
            with self.subTest(text=text):
                self.assertNotIn("medication_or_hormone", detect_risks(text).risks)

    def test_substances_require_joint_use_or_combination_question(self) -> None:
        for text in ("Posso misturar cafeina e sertralina?", "Cerveja e creatina?", "Tomo ibuprofeno junto com alcool", "Ciclo oxa + dura", "Posso misturar whey com meu medicamento?", "Posso misturar cabergolina e cafeina?", "Nao tomo alcool, uso sertralina e cafeina"):
            with self.subTest(text=text):
                self.assertIn("substance_interaction", detect_risks(text).risks)
        for text in ("Posso misturar arroz e feijao?", "Whey e creatina?", "Semaglutida ou testosterona?", "Melatonina inibe producao de testosterona?", "Animal Pak + GH Max + ZMA?", "Nao misturo cafeina e sertralina", "Nao tomo alcool, uso sertralina", "Cafeina e cafeina?", "Ciclo dura + Durateston", "Meu treino dura uma hora e tomo whey"):
            with self.subTest(text=text):
                self.assertNotIn("substance_interaction", detect_risks(text).risks)

    def test_food_allergy_and_food_safety(self) -> None:
        for text in ("Tenho alergia a leite", "Alergia a whey?", "Urticaria depois de comer amendoim", "Tenho intolerancia a lactose", "Nao tomo leite e tenho alergia a whey"):
            with self.subTest(text=text):
                self.assertIn("food_allergy_or_reaction", detect_risks(text).risks)
        for text in ("Whey vencido da para tomar?", "Frango fora da geladeira", "Arroz com mofo", "Maltodextrina vencida", "Carne crua e seguro?"):
            with self.subTest(text=text):
                self.assertIn("food_safety_uncertainty", detect_risks(text).risks)
        for text in ("Meu passaporte esta vencido", "Tenho alergia a poeira", "Nao tenho alergia a leite", "O frango nao esta estragado"):
            with self.subTest(text=text):
                self.assertNotIn("food_allergy_or_reaction", detect_risks(text).risks)
                self.assertNotIn("food_safety_uncertainty", detect_risks(text).risks)

    def test_reaction_and_emergency_are_multilabel(self) -> None:
        result = detect_risks("Comi amendoim, estou com urticaria e nao consigo respirar")
        self.assertTrue({"food_allergy_or_reaction", "emergency_symptom"}.issubset(result.risks))

    def test_heat_requires_environment_and_reported_symptom(self) -> None:
        for text in ("Estou tonto no calor intenso", "Estou com nausea treinando no sol", "Fiquei com fraqueza no calor"):
            with self.subTest(text=text):
                result = detect_risks(text)
                self.assertIn("heat_illness_signal", result.risks)
                self.assertNotIn("emergency_symptom", result.risks)
        self.assertTrue({"heat_illness_signal", "emergency_symptom"}.issubset(detect_risks("Estou confuso no calor intenso").risks))
        for text in ("Quais sao os sintomas de insolacao?", "No calor nao estou tonto", "Estou cansado no calor", "Calorias e tontura?", "Estou com fraqueza, sem calor"):
            with self.subTest(text=text):
                self.assertNotIn("heat_illness_signal", detect_risks(text).risks)

    def test_recovery_requires_multiple_distinct_persistent_reports(self) -> None:
        self.assertIn("under_recovery_signal", detect_risks("Ultimamente estou dormindo mal e sinto fadiga").risks)
        self.assertIn("under_recovery_signal", detect_risks("Ha semanas tenho sono ruim. Meu desempenho caiu").risks)
        for text in ("Overtraining?", "Durmo 5 horas por dia", "Estou cansado", "Tenho fadiga e estou exausto ha dias", "Ha semanas nao tenho fadiga e durmo mal", "O que e fadiga e sono ruim persistente?", "Estou dormindo mal e sinto fadiga"):
            with self.subTest(text=text):
                self.assertNotIn("under_recovery_signal", detect_risks(text).risks)

    def test_clinical_context_requires_report(self) -> None:
        for text in ("Tenho diabetes", "Estou gravida", "Tenho 16 anos e quero treinar", "Minha cirurgia foi ontem, estou no pos-parto"):
            with self.subTest(text=text):
                self.assertIn("vulnerable_or_clinical_context", detect_risks(text).risks)
        for text in ("O que e diabetes?", "Nao tenho diabetes", "Treino ha 16 anos", "Hernia de disco?"):
            with self.subTest(text=text):
                self.assertNotIn("vulnerable_or_clinical_context", detect_risks(text).risks)

    def test_lab_requests_do_not_diagnose_or_interpret_raw_numbers(self) -> None:
        for text in ("Interpretacao de exames - hipotireoidismo?", "Avalie meu hemograma", "Testosterona 300 ng/dl esta normal?", "Resultado do meu TSH, devo tratar?"):
            with self.subTest(text=text):
                self.assertIn("clinical_measurement_request", detect_risks(text).risks)
        for text in ("TSH 8 mUI/L", "Como e feito um exame de sangue?", "Meu pace esta normal?", "Avalie meu treino", "Exame de matematica", "Resultado do exame de matematica", "Fiz exame ontem"):
            with self.subTest(text=text):
                self.assertNotIn("clinical_measurement_request", detect_risks(text).risks)

    def test_extreme_plan_negation_and_daily_calories(self) -> None:
        for text in ("Quero cortar agua para emagrecer", "Jejum seco funciona?", "Dieta de 600 kcal por dia", "Quero ficar 3 dias sem comer", "Vou nao comer nada por 3 dias"):
            with self.subTest(text=text):
                self.assertIn("extreme_diet_or_dehydration", detect_risks(text).risks)
        self.assertNotIn("extreme_diet_or_dehydration", detect_risks("Nao quero cortar agua").risks)
        self.assertNotIn("extreme_diet_or_dehydration", detect_risks("Refeicao de 600 kcal").risks)
        self.assertNotIn("extreme_diet_or_dehydration", detect_risks("Gasto 600 kcal por dia na corrida").risks)
        self.assertNotIn("extreme_diet_or_dehydration", detect_risks("Posso nao comer nada antes do treino?").risks)

    def test_unsafe_training_requests(self) -> None:
        self.assertIn("unsafe_training_request", detect_risks("Posso treinar lesionado?").risks)
        self.assertTrue({"unsafe_training_request", "pain_or_possible_injury", "emergency_symptom"}.issubset(detect_risks("Quero treinar com dor no peito agora").risks))
        for text in ("Nao quero treinar lesionado", "Como evitar lesao?", "Como evitar treinar lesionado?", "Posso treinar com dor muscular tardia?"):
            with self.subTest(text=text):
                self.assertNotIn("unsafe_training_request", detect_risks(text).risks)

    def test_crisis_literal_and_negated(self) -> None:
        for text in ("Quero me matar", "Nao quero mais viver", "Quero morrer"):
            with self.subTest(text=text):
                self.assertIn("mental_health_crisis", detect_risks(text).risks)
        for text in ("Nao quero morrer", "Quero morrer de rir", 'A frase "quero morrer" aparece no livro', "Esse treino me mata"):
            with self.subTest(text=text):
                self.assertNotIn("mental_health_crisis", detect_risks(text).risks)

    def test_unicode_normalization_and_original_offsets(self) -> None:
        for text in ("\U0001f4ac DORM\u00caNCIA por dias", "\U0001f4ac DORME\u0302NCIA por dias", "\u00df: CREATINA presta?", "\uff23\uff32\uff25\uff21\uff34\uff29\uff2e\uff21 presta?"):
            with self.subTest(text=text):
                result = detect_risks(text)
                self.assertTrue(result.risks)
                for item in result.evidence:
                    self.assertEqual(item.text, text[item.start:item.end])
        normalized, offsets = normalize_with_offsets("\u00dfE\u0302")
        self.assertEqual(normalized, "sse")
        self.assertEqual(offsets, ((0, 1), (0, 1), (1, 3)))
        result = detect_risks("Dor no peit\u006f\u0301 durante supino?")
        urgent = next(item for item in result.evidence if item.label == "emergency_symptom")
        self.assertTrue(urgent.text.endswith("\u0301"))

    def test_taxonomy_ids_and_serializable_output(self) -> None:
        root = Path(__file__).resolve().parents[1] / "data" / "taxonomy"
        base = json.loads((root / "risks.v1.json").read_text(encoding="utf-8"))
        expansion = json.loads((root / "expansion.v1.1.json").read_text(encoding="utf-8"))
        expected = {item["id"] for item in (*base["risks"], *expansion["risks"])}
        self.assertEqual(set(SUPPORTED_RISKS), expected)
        payload = detect_risks("Creatina presta?").to_dict()
        self.assertEqual(json.loads(json.dumps(payload))["risks"], ["supplement_uncertainty"])

    def test_input_contract(self) -> None:
        with self.assertRaises(TypeError):
            detect_risks(None)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            detect_risks("a" * 10_001)


if __name__ == "__main__":
    unittest.main()
