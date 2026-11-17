"""Regression tests for the boundary between interpretation and proposals."""

from datetime import date
import json
from pathlib import Path
import sys
import unittest
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evolv_rag.actions import PlannerSnapshot
from evolv_rag.coach import Coach


def uid(number):
    return str(UUID(int=number))


class NLP:
    def analyze(self, text, **_):
        return {"route": "clarify", "intent": {"label": "clarification", "confident": False},
                "risk": {"labels": []}, "entities": {"text": text, "entities": []}}


class LM:
    settings = {"max_input_tokens": 2048}

    def __init__(self, kind, text=""):
        self.output = {"tipo": kind, "texto": text}
        self.calls = []

    def count(self, _):
        return 100

    def interpret(self, messages):
        self.calls.append(json.loads(messages[-1]["content"]))
        return json.dumps(self.output)


class ContextInterpretationTests(unittest.TestCase):
    def test_recall_uses_an_actual_user_turn(self):
        lm = LM("lembrar", "1")
        coach = Coach(NLP(), None, lm)
        coach.history = [{"role": "user", "content": "Eu só consigo ir no sábado."},
                         {"role": "assistant", "content": "Entendi."}]
        result = coach.respond("Que dia eu falei que podia ir?")
        self.assertIn("sábado", result["answer"])
        self.assertEqual("assistant", lm.calls[0]["historico"][1]["papel"])
        self.assertFalse(result["actions"])

    def test_an_explicit_swap_can_be_completed_by_meal_without_applying_it(self):
        snapshot = PlannerSnapshot(
            uid(1), "context-test", diet_plan_id=uid(2),
            meal_items=[{"id": uid(3), "canonical": "ovo", "meal_name": "Almoço",
                         "approved_replacement_ids": [uid(5)]},
                        {"id": uid(4), "canonical": "ovo", "meal_name": "Jantar",
                         "approved_replacement_ids": [uid(5)]}],
            foods=[{"id": uid(5), "canonical": "tofu"}],
        )
        lm = LM("troca")
        coach = Coach(NLP(), None, lm, planner_snapshot=snapshot)
        first = coach.respond("Troque meu ovo por tofu.", reference_date=date(2026, 11, 10))
        self.assertFalse(first["actions"])
        result = coach.respond("Só no jantar.", reference_date=date(2026, 11, 10))
        proposal, = result["actions"]
        self.assertEqual(uid(4), proposal["payload"]["meal_item_id"])
        self.assertEqual("pending_user_confirmation", proposal["status"])
        self.assertFalse(result["planner"]["writes_allowed"])
        self.assertEqual("ovo", lm.calls[-1]["pedido_de_troca"]["sai"])

        other = Coach(NLP(), None, lm, planner_snapshot=snapshot)
        self.assertFalse(other.respond("Só no jantar.")["actions"])
        self.assertFalse(other.respond("Posso trocar ovo por tofu?")["actions"])
        self.assertFalse(other.respond("Não faça a troca.")["actions"])

        mistaken = LM("papo", "Aí vai o jantar, com tofu no lugar do ovo!")
        coach = Coach(NLP(), None, mistaken, planner_snapshot=snapshot)
        self.assertFalse(coach.respond("Troque meu ovo por tofu.")["actions"])
        result = coach.respond("Só no jantar.")
        self.assertFalse(result["actions"])
        self.assertNotIn("no lugar do ovo", result["answer"])

    def test_urgent_safety_does_not_call_the_model(self):
        lm = LM("papo", "Continue.")
        result = Coach(NLP(), None, lm).respond("Estou com aperto no peito e sem ar agora.")
        self.assertIn("emergency_symptom", result["analysis"]["risk"]["labels"])
        self.assertFalse(lm.calls)


if __name__ == "__main__":
    unittest.main()
