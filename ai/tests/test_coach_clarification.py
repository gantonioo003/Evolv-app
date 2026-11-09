"""Explicit intent fixtures + real extractor/guards/proposals; not classifier accuracy."""
from datetime import date
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from uuid import UUID

AI_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(AI_ROOT/"src"))
from evolv_rag.coach import Coach
from evolv_rag.actions import PlannerSnapshot
from evolv_nlp.entities_v14 import extract_entities,load_catalog,supported_entity_types
from evolv_nlp.activity_type import usable_activity_values
from evolv_rag.safety import preflight, terse_urgent_report

DAY=date(2026,11,3)
CATALOG=load_catalog(AI_ROOT)


class FixedNLP:
    def __init__(self,label,confident=False):
        self.label,self.confident=label,confident

    def analyze(self,text,**kwargs):
        return {"route":"draft_for_confirmation" if self.confident else "clarify",
                "intent":{"label":self.label,"confident":self.confident},"risk":{"labels":[]},
                "entities":extract_entities(text,CATALOG,kwargs.get("reference_date") or DAY).to_dict()}


def snapshot():
    uid=lambda i:str(UUID(int=i))
    return PlannerSnapshot(uid(1),"fixture",workout_plan_id=uid(2),
        days=[{"id":uid(3),"weekday":"tuesday"}],
        workout_exercises=[{"id":uid(4),"canonical":"supino reto","workout_day_id":uid(3)}],
        exercises=[{"id":uid(5),"canonical":"flexao de bracos"}])


class ClarificationTests(unittest.TestCase):
    def ask(self,label,text,confident=False,plan=None):
        coach=Coach(FixedNLP(label,confident),None,planner_snapshot=plan)
        result=coach.respond(text,reference_date=DAY)
        self.assertIsNone(result["generation"])
        self.assertFalse(result["planner"]["writes_allowed"])
        return result

    def test_dates_absent_asks_origin_and_destination(self):
        r=self.ask("move_workout_day","Quero reagendar o treino.")
        self.assertEqual(["source_date","target_date"],r["clarification"]["missing_fields"])
        self.assertIn("De qual dia para qual dia",r["answer"])

    def test_known_destination_does_not_get_asked_again(self):
        r=self.ask("move_workout_day","Quero mover o treino para quinta.")
        self.assertEqual(["source_date"],r["clarification"]["missing_fields"])
        self.assertIn("Em qual dia está",r["answer"])
        self.assertNotIn("Para qual dia",r["answer"])

    def test_complete_uncertain_request_checks_intent_not_dates(self):
        r=self.ask("move_workout_day","Remarque de 03/11/2026 para 05/11/2026.")
        self.assertEqual("intent_uncertain",r["clarification"]["reason"])
        self.assertEqual([],r["clarification"]["missing_fields"])
        self.assertEqual([],r["actions"])
        self.assertFalse(r["analysis"]["intent"]["confident"])

    def test_one_source_exercise_asks_only_replacement(self):
        r=self.ask("replace_exercise","Troque o supino reto.")
        self.assertEqual(["replacement_exercise"],r["clarification"]["missing_fields"])

    def test_wrong_uncertain_label_can_guide_question_without_overriding_classifier(self):
        r=self.ask("greeting","Troque o supino reto.")
        self.assertEqual("greeting",r["analysis"]["intent"]["label"])
        self.assertFalse(r["analysis"]["intent"]["confident"])
        self.assertEqual("replace_exercise",r["clarification"]["candidate_intent"])
        self.assertEqual(["replacement_exercise"],r["clarification"]["missing_fields"])
        self.assertFalse(r["clarification"]["authorizes_action"])
        self.assertEqual([],r["actions"])

    def test_incomplete_confident_request_is_reported_as_clarification(self):
        r=self.ask("replace_exercise","Troque o supino reto.",True,snapshot())
        self.assertEqual("clarify",r["analysis"]["route"])
        self.assertEqual("draft_for_confirmation",r["clarification"]["original_route"])
        self.assertEqual([],r["actions"])

    def test_single_explicit_destination_asks_source(self):
        r=self.ask("replace_exercise","Troque aquele exercício por flexão.")
        self.assertEqual(["exercise"],r["clarification"]["missing_fields"])

    def test_no_items_asks_both_roles(self):
        r=self.ask("replace_meal_item","Quero substituir um item do almoço.")
        self.assertEqual(["food","replacement_food"],r["clarification"]["missing_fields"])

    def test_complete_food_pair_not_asked_again_when_uncertain(self):
        r=self.ask("replace_meal_item","Troque arroz por feijão.")
        self.assertEqual("intent_uncertain",r["clarification"]["reason"])

    def test_known_activity_asks_only_date(self):
        r=self.ask("set_day_activity","Quero definir descanso.")
        self.assertEqual(["activity_date"],r["clarification"]["missing_fields"])
        self.assertNotIn("Qual atividade",r["answer"])

    def test_known_date_asks_only_activity(self):
        r=self.ask("set_day_activity","Ajuste a atividade de 12/11/2026.")
        self.assertEqual(["activity_type"],r["clarification"]["missing_fields"])

    def test_complete_activity_uncertainty_is_not_a_missing_slot(self):
        for text in ("Defina descanso em 12/11/2026.","Coloque cardio em 13/11/2026."):
            r=self.ask("set_day_activity",text)
            self.assertEqual("intent_uncertain",r["clarification"]["reason"])
            self.assertEqual([],r["clarification"]["missing_fields"])

    def test_two_activities_ask_which_without_inventing_mixed(self):
        r=self.ask("set_day_activity","Quero musculação e cardio em 12/11/2026.")
        self.assertEqual("ambiguous_activity",r["clarification"]["reason"])
        self.assertEqual([],r["actions"])

    def test_no_direction_does_not_assign_source_by_guess(self):
        r=self.ask("replace_exercise","Supino reto e flexão.")
        self.assertEqual("ambiguous_direction",r["clarification"]["reason"])

    def test_duplicate_plan_item_asks_day(self):
        plan=snapshot();plan.workout_exercises.append(deepcopy(plan.workout_exercises[0]))
        r=self.ask("replace_exercise","Troque supino reto por flexão.",True,plan)
        self.assertEqual("ambiguous_plan_item",r["clarification"]["reason"])
        self.assertEqual([],r["actions"])

    def test_missing_backend_context_does_not_request_private_ids(self):
        r=self.ask("move_workout_day","Mova de 03/11/2026 para 05/11/2026.",True)
        self.assertEqual("plan_context_missing",r["clarification"]["reason"])
        self.assertNotIn("UUID",r["answer"])

    def test_weekly_scope_is_explained(self):
        r=self.ask("move_workout_day","Mova de 03/11/2026 para 12/11/2026.",True,snapshot())
        self.assertEqual("weekly_scope",r["clarification"]["reason"])

    def test_destination_conflict_is_not_a_silent_swap(self):
        plan=snapshot();plan.days.append({"id":str(UUID(int=7)),"weekday":"thursday"})
        r=self.ask("move_workout_day","Mova de 03/11/2026 para 05/11/2026.",True,plan)
        self.assertEqual("destination_conflict",r["clarification"]["reason"])
        self.assertEqual([],r["actions"])

    def test_complete_confident_request_still_requires_proposal_confirmation(self):
        r=self.ask("set_day_activity","Hoje quero descansar.",True,snapshot())
        self.assertIsNone(r["clarification"])
        self.assertEqual("pending_user_confirmation",r["actions"][0]["status"])
        self.assertEqual("rest",r["actions"][0]["payload"]["activity_type"])

    def test_negative_and_hypothetical_requests_do_not_turn_into_actions(self):
        for text in ("Não mude o treino de terça para quinta.","Talvez eu mude o treino amanhã."):
            r=self.ask("move_workout_day",text,True,snapshot())
            self.assertEqual("scope_or_negation",r["clarification"]["reason"])
            self.assertEqual([],r["actions"])

    def test_emergency_and_allergy_override_clarification(self):
        for text in ("Dor no peito e falta de ar. Mude meu treino.","Sou alérgico a amendoim, troca o lanche."):
            r=self.ask("replace_meal_item",text)
            self.assertIsNone(r["clarification"])
            self.assertEqual([],r["actions"])
            self.assertIsNotNone(r["safety"]["preflight_route"])

    def test_declared_unsupported_action_is_not_falsely_promised(self):
        r=self.ask("create_diet_plan","Crie meu primeiro plano alimentar.",True,snapshot())
        self.assertEqual("unsupported_action",r["clarification"]["reason"])
        self.assertEqual([],r["actions"])

    def test_terse_symptom_report_guard_does_not_match_negation_or_educational_question(self):
        for text in ("O que significa dor no peito e falta de ar?", "Não tenho dor no peito e falta de ar.",
                     "Meu pai teve dor no peito e falta de ar ano passado."):
            self.assertFalse(terse_urgent_report(text),text)

    def test_terse_emergency_remains_prioritized_in_followup(self):
        coach=Coach(FixedNLP("move_workout_day"),None)
        coach.respond("Dor no peito e falta de ar.",reference_date=DAY)
        result=coach.respond("E posso mudar meu treino?",reference_date=DAY)
        self.assertIsNone(result["clarification"])
        self.assertIn("emergency_symptom",result["analysis"]["risk"]["labels"])


class ActivityEntityTests(unittest.TestCase):
    def test_normalization_preserves_original_unicode_spans(self):
        for word,value in (("descanso","rest"),("musculação","resistance"),("cardio","cardio"),("mista","mixed")):
            text=f"Defina {word} no dia 15/11/2026."
            found=[e for e in extract_entities(text,CATALOG,DAY).entities if e.entity_type=="activity_type"]
            self.assertEqual([value],[e.value for e in found])
            self.assertTrue(all(text[e.start:e.end]==e.text for e in found))
        self.assertIn("activity_type",supported_entity_types(CATALOG))

    def test_rest_interval_is_not_a_rest_day(self):
        for text in ("Aumente o descanso entre séries.","Quero descanso de 90 segundos no supino.","Tempo de descanso maior."):
            self.assertEqual(set(),usable_activity_values(text))

    def test_negation_hypothesis_and_third_party_are_not_asserted(self):
        for text in ("Não quero fazer cardio amanhã.","Se eu fizer musculação hoje?","Meu pai vai fazer cardio hoje.","Talvez eu faça cardio."):
            self.assertEqual(set(),usable_activity_values(text),text)


if __name__=="__main__":unittest.main()
