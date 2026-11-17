from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
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

    def test_explicit_food_swap_only_creates_proposal_when_approved_and_unambiguous(self):
        self.s.meal_items[0]["approved_replacement_ids"] = [uid(8)]
        session = ActionSession(self.s, lambda: self.now)
        for text in ("Posso trocar arroz por feijao?", "Não troque arroz por feijao",
                     "Troque arroz por feijao e mude o treino"):
            with self.subTest(text=text):
                analysis = self.analysis("replace_meal_item", text)
                analysis["intent"]["confident"] = False
                self.assertIsNone(session.propose_explicit_swap(analysis))
        analysis = self.analysis("replace_meal_item", "Troque arroz por feijao.")
        analysis["intent"]["confident"] = False
        self.assertIsNone(ActionSession().propose_explicit_swap(analysis))
        proposal = session.propose_explicit_swap(analysis)
        self.assertEqual("pending_user_confirmation", proposal["status"])
        self.assertEqual(uid(8), proposal["payload"]["replacement_food_id"])
        self.assertFalse(analysis["intent"]["confident"])
        self.s.meal_items[0]["approved_replacement_ids"] = []
        self.assertIsNone(ActionSession(self.s).propose_explicit_swap(analysis))
    def test_questions_and_mixed_commands_never_open_a_proposal(self):
        for text in (
            "Posso trocar supino reto por flexão?",
            "Pode trocar supino reto por flexão?",
            "Se der, troque supino reto por flexão.",
            "Não troque supino reto por flexão.",
            "Troque supino reto por flexão. Mude o treino também.",
            "Troque supino reto por flexão e me explica como treinar.",
            "Troca supino reto por flexão, mas n mude o dia.",
            "Meu amigo quer trocar supino reto por flexão.",
        ):
            with self.subTest(text=text):
                analysis = self.analysis("replace_exercise", text)
                with self.assertRaises(ValueError):
                    self.session.propose(analysis)
                analysis["intent"]["confident"] = False
                self.assertIsNone(self.session.propose_explicit_swap(analysis))
                self.assertIsNone(self.session.pending)

    def test_low_confidence_recovery_uses_exact_targets_and_keeps_confirmation(self):
        analysis = self.analysis("replace_exercise", "Tá, agora troque o supino reto por flexão de braços.")
        analysis["intent"]["confident"] = False
        proposal = self.session.propose_explicit_swap(analysis)
        self.assertEqual("pending_user_confirmation", proposal["status"])
        self.assertEqual(uid(5), proposal["payload"]["workout_day_exercise_id"])
        self.assertEqual(uid(6), proposal["payload"]["replacement_exercise_id"])
        self.assertFalse(analysis["intent"]["confident"])

    def test_meal_name_must_match_and_disambiguates_duplicate_food(self):
        breakfast = {"id": uid(7), "canonical": "ovo", "meal_name": "Café da manhã",
                     "approved_replacement_ids": [uid(8)]}
        lunch = {**breakfast, "id": uid(9), "meal_name": "Almoço"}
        self.s.meal_items = [breakfast, lunch]
        self.s.foods = [{"id": uid(8), "canonical": "tofu"}]
        session = ActionSession(self.s)
        for text in ("Troque ovo por tofu.", "Troque ovo do jantar por tofu."):
            with self.subTest(text=text):
                analysis = self.analysis("replace_meal_item", text)
                analysis["intent"]["confident"] = False
                self.assertIsNone(session.propose_explicit_swap(analysis))
        analysis = self.analysis("replace_meal_item", "Troque o ovo do café da manhã por tofu.")
        analysis["intent"]["confident"] = False
        proposal = session.propose_explicit_swap(analysis)
        self.assertEqual(uid(7), proposal["payload"]["meal_item_id"])
        analysis["entities"]["entities"] = [e for e in analysis["entities"]["entities"] if e["entity_type"] != "meal"]
        self.assertEqual(uid(7), session.propose_explicit_swap(analysis)["payload"]["meal_item_id"])

    def test_new_exact_swap_is_not_mistaken_for_confirming_an_older_proposal(self):
        self.s.meal_items = [{"id": uid(7), "canonical": "ovo", "meal_name": "Café da manhã",
                              "approved_replacement_ids": [uid(8)]}]
        self.s.foods = [{"id": uid(8), "canonical": "tofu"}]
        text = "Troque o ovo do café da manhã por tofu."
        analysis = self.analysis("confirm_planner_action", text)
        analysis["intent"]["confident"] = False
        analysis["route"] = "clarify_pending_action"
        nlp = Mock()
        nlp.analyze.return_value = analysis
        coach = Coach(nlp, Mock(), planner_snapshot=self.s)
        proposal, = coach.respond(text)["actions"]
        self.assertEqual("pending_user_confirmation", proposal["status"])
        self.assertEqual("replace_meal_item", proposal["payload"]["kind"])
        self.assertEqual(uid(8), proposal["payload"]["replacement_food_id"])

    def test_natural_meal_swap_from_iphone_uses_position_and_requires_confirmation(self):
        self.s.meal_items = [
            {"id": uid(7), "canonical": "arroz branco cozido", "meal_name": "Primeira refeição",
             "meal_position": 0, "approved_replacement_ids": [uid(8)]},
            {"id": uid(9), "canonical": "arroz branco cozido", "meal_name": "Refeição principal",
             "meal_position": 1, "approved_replacement_ids": [uid(8)]},
        ]
        self.s.foods = [{"id": uid(8), "canonical": "Macarrão cozido"}]
        nlp = Mock()
        def analyze(text, **kwargs):
            result = self.analysis("replace_meal_item", text)
            result["intent"]["confident"] = False
            result["route"] = "clarify"
            return result
        nlp.analyze.side_effect = analyze
        coach = Coach(nlp, Mock(), planner_snapshot=self.s)
        for text in (
            "Hoje tenho 3 refeições só mas não vou conseguir comer arroz branco poderia trocar por macarrão simples tipo spaghetti?",
            "Mas macarrão por arroz não vai mudar tanta coisa, não acha? Não tenho arroz em casa só macarrão entendeu?!",
        ):
            reply = coach.respond(text)
            self.assertFalse(reply["actions"])
            self.assertIn("refeição", reply["answer"])
            self.assertNotIn("vou manter", reply["answer"])
        request = "Eu quero que você mude pegue o arroz tire e coloque macarrão na refeição 2"
        proposal, = coach.respond(request)["actions"]
        self.assertEqual("pending_user_confirmation", proposal["status"])
        self.assertEqual(uid(9), proposal["payload"]["meal_item_id"])
        self.assertEqual(uid(8), proposal["payload"]["replacement_food_id"])
        followup = coach.respond("Faça a troca")
        self.assertFalse(followup["actions"])
        self.assertIn("já está pronta", followup["answer"])
        self.assertFalse(coach.respond("confirmo")["actions"])
        confirmed = coach.respond("confirmo", proposal_id=proposal["id"])
        self.assertEqual("confirmed_for_planner_preview", confirmed["actions"][0]["status"])
        self.assertFalse(confirmed["planner"]["writes_allowed"])

        continuation = Coach(nlp, Mock(), planner_snapshot=self.s)
        self.assertFalse(continuation.respond("Posso trocar arroz da segunda refeição por macarrão?")["actions"])
        drafted, = continuation.respond("Faça a troca")["actions"]
        self.assertEqual(uid(9), drafted["payload"]["meal_item_id"])
        self.assertEqual("pending_user_confirmation", drafted["status"])
        fresh = Coach(nlp, Mock(), planner_snapshot=self.s)
        self.assertFalse(fresh.respond("Faça a troca")["actions"])
        self.s.meal_items[1]["approved_replacement_ids"] = []
        fresh = Coach(nlp, Mock(), planner_snapshot=self.s)
        reply = fresh.respond("Arroz branco cozido deve sair da segunda refeição e deve entrar macarrão")
        self.assertFalse(reply["actions"])
        self.assertIn("não está aprovada", reply["answer"])

    def test_contextual_swap_requires_fresh_snapshot_and_clear_slot_reply(self):
        first = self.analysis("replace_exercise", "Troca esse por flexão.")
        question = {"reason": "missing_fields", "missing_fields": ["exercise"], "candidate_intent": "replace_exercise"}
        second = self.analysis("replace_exercise", "Supino reto. Quero trocar ele pela flexão mesmo.")
        self.session.remember_incomplete_swap(first, question)
        proposal = self.session.complete_swap(second)
        self.assertEqual("pending_user_confirmation", proposal["status"])
        self.assertEqual(uid(5), proposal["payload"]["workout_day_exercise_id"])
        self.assertEqual(uid(6), proposal["payload"]["replacement_exercise_id"])
        self.assertIsNone(self.session.complete_swap(second))
        self.session.remember_incomplete_swap(first, question)
        self.session.snapshot.revision = "new-revision"
        self.assertIsNone(self.session.complete_swap(second))

        self.session.remember_incomplete_swap(first, question)
        self.assertIsNone(self.session.complete_swap(
            self.analysis("replace_exercise", "Supino reto. Quero trocar ele pela remada mesmo.")
        ))
        self.session.remember_incomplete_swap(first, question)
        self.now += timedelta(minutes=10)
        self.assertIsNone(self.session.complete_swap(second))

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
