from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from uuid import UUID
AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_rag.actions import ActionSession, PlannerSnapshot, proposed_payload, validate_payload
from evolv_rag.coach import Coach
from evolv_rag.safety import preflight, output_guard
from evolv_nlp.entities_v14 import load_catalog, extract_entities

def uid(i):
    return str(UUID(int=i))

class ActionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 2, tzinfo=timezone.utc)
        self.s = PlannerSnapshot(uid(1), "revision1", uid(2), uid(3),
            days=[{"id": uid(4), "weekday": "tuesday"}],
            workout_exercises=[{"id": uid(5), "workout_day_id": uid(4), "canonical": "supino reto"}],
            exercises=[{"id": uid(6), "canonical": "flexao de bracos"}],
            meal_items=[{"id": uid(7), "canonical": "arroz branco cozido"}],
            foods=[{"id": uid(8), "canonical": "feijao preto cozido"}])
        self.catalog = load_catalog(AI_ROOT)
        self.session = ActionSession(self.s, lambda: self.now)
    def analysis(self, kind="move_workout_day", text="Mova o treino de 03/11/2026 para 05/11/2026"):
        return {"intent": {"label": kind, "confident": True}, "risk": {"labels": []},
                "route": "draft_for_confirmation",
                "entities": extract_entities(text, self.catalog, date(2026,11,2)).to_dict()}
    def test_four_dto_kinds_with_actual_entity_extractor(self):
        cases = [self.analysis(), self.analysis("replace_exercise","Troque supino reto por flexao"),
                 self.analysis("replace_meal_item","Troque arroz por feijao"),
                 self.analysis("set_day_activity","Hoje quero descansar")]
        for a in cases:
            payload = proposed_payload(a, self.s)
            self.assertEqual(a["intent"]["label"], payload["kind"])
            self.assertEqual(payload, validate_payload(payload))
    def test_unknown_fields_sql_kind_and_bad_uuid_rejected(self):
        p = proposed_payload(self.analysis(), self.s)
        for changed in [{**p, "sql":"DELETE FROM plans"}, {**p, "kind":"sql"},
                        {**p, "workout_plan_id":"not-a-uuid"}, {**p, "source":"manual"},
                        {**p, "target_weekday":"holiday"}]:
            with self.assertRaises(ValueError):
                validate_payload(changed)
    def test_missing_context_uncertainty_risk_and_unsupported_action(self):
        with self.assertRaises(ValueError):
            proposed_payload(self.analysis(), None)
        for field, value in [("confident",False), ("label","adjust_training_volume")]:
            a = self.analysis(); a["intent"][field] = value
            with self.assertRaises(ValueError):
                self.session.propose(a)
        a = self.analysis(); a["risk"]["labels"] = ["pain_or_possible_injury"]
        with self.assertRaises(ValueError):
            self.session.propose(a)
    def test_confirmation_requires_id_session_and_not_replayed(self):
        p = self.session.propose(self.analysis())
        with self.assertRaises(ValueError):
            ActionSession(self.s).transition(p["id"], "confirm")
        with self.assertRaises(ValueError):
            self.session.transition(uid(999), "confirm")
        result = self.session.transition(p["id"], "confirm")
        self.assertEqual("confirmed_for_planner_preview", result["status"])
        with self.assertRaises(ValueError):
            self.session.transition(p["id"], "confirm")
    def test_expiry_revision_and_rejection(self):
        p = self.session.propose(self.analysis())
        self.now += timedelta(minutes=10)
        with self.assertRaises(ValueError):
            self.session.transition(p["id"], "confirm")
        p = self.session.propose(self.analysis())
        self.session.snapshot.revision = "revision2"
        with self.assertRaises(ValueError):
            self.session.transition(p["id"], "confirm")
        p = self.session.propose(self.analysis())
        self.assertEqual("rejected", self.session.transition(p["id"], "reject")["status"])
    def test_conflicts_crossweek_and_ambiguous_item_fail(self):
        s = deepcopy(self.s); s.days.append({"id":uid(9), "weekday":"thursday"})
        with self.assertRaises(ValueError):
            proposed_payload(self.analysis(), s)
        with self.assertRaises(ValueError):
            proposed_payload(self.analysis(text="Mova de 03/11/2026 para 12/11/2026"), self.s)
        self.s.workout_exercises.append(deepcopy(self.s.workout_exercises[0]))
        with self.assertRaises(ValueError):
            proposed_payload(self.analysis("replace_exercise","Troque supino reto por flexao"),self.s)
    def test_order_missing_replacement_and_negated_spans(self):
        for text in ["Supino reto e flexao","Troque supino reto"]:
            with self.assertRaises(ValueError):
                proposed_payload(self.analysis("replace_exercise",text), self.s)
        a = self.analysis()
        a["entities"]["entities"][0]["attributes"]["negated"] = True
        with self.assertRaises(ValueError):
            proposed_payload(a,self.s)
    def test_preflight_emergency_allergy_privacy_and_output_guards(self):
        self.assertIn("emergency_symptom", preflight("Dor no peito ao correr")["risks"])
        self.assertIn("food_allergy_or_reaction", preflight("Sou alergico a amendoim, posso comer?")["risks"])
        self.assertEqual("privacy_information",preflight("Quero apagar meus dados")["route"])
        for text in ["Ja alterei seu treino.", "[kb:inventado]", "Voce tem tendinite."]:
            self.assertIsNotNone(output_guard(text, []))
        self.assertIsNone(output_guard("Informacao geral [kb:ok]", ["kb:ok"]))
    def test_compound_risk_cannot_confirm_pending_proposal(self):
        p = self.session.propose(self.analysis())
        class NLP:
            def analyze(nlp_self, *args, **kwargs):
                a = self.analysis();a["risk"]["labels"]=["pain_or_possible_injury"]
                return a
        coach = Coach(NLP(), None, planner_snapshot=self.s)
        coach.action_session = self.session
        r = coach.respond("sim",proposal_id=p["id"])
        self.assertEqual([],r["actions"])
        self.assertIsNone(self.session.pending)
    def test_full_preview_flow_and_clear_invalidates_pending(self):
        class NLP:
            def analyze(nlp_self,*args,**kwargs):
                return self.analysis()
        coach = Coach(NLP(),None,planner_snapshot=self.s,now=lambda:self.now)
        proposal = coach.respond("Mova o treino.")["actions"][0]
        result = coach.respond("sim",proposal_id=proposal["id"])
        self.assertEqual("confirmed_for_planner_preview", result["actions"][0]["status"])
        self.assertFalse(result["planner"]["connected"])
        coach.clear()
        self.assertIsNone(coach.action_session.pending)
    def test_negative_hypothetical_compound_requests_require_clarification(self):
        for text in ["Hoje nao quero descansar", "Talvez hoje quero descansar",
                     "Se eu descansar hoje", "Hoje quero descansar e mude minha dieta"]:
            with self.assertRaises(ValueError):
                self.session.propose(self.analysis("set_day_activity",text))
    def test_emergency_takes_priority_over_privacy(self):
        result = preflight("Tenho dor no peito. Quero apagar meus dados.")
        self.assertIn("emergency_symptom", result["risks"])
        self.assertIn("emergência", result["answer"])
    def test_returned_proposal_mutation_does_not_change_pending(self):
        p = self.session.propose(self.analysis())
        p["payload"]["target_weekday"] = "friday"
        p["id"] = uid(999)
        self.assertEqual("thursday", self.session.pending["payload"]["target_weekday"])

if __name__ == "__main__":
    unittest.main()
