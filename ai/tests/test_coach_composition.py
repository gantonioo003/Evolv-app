from copy import deepcopy
from datetime import date
from pathlib import Path
import sys
import unittest
AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_rag.coach import Coach
from evolv_rag.actions import PlannerSnapshot
from evolv_rag.account_context import AccountContext
from evolv_rag.grounding import NO_SUPPORT, PARTIAL

class NLP:
    route = "answer"
    label = "ask_training_concept"
    risks = []
    def analyze(self, text, **kwargs):
        self.received = text, kwargs
        return {"route": self.route, "intent": {"label": self.label, "confident": False},
                "risk": {"labels": self.risks}, "entities": {"entities": []}}

class Retrieval:
    def __init__(self):
        self.calls = []
        self.rows = [{"id": "kb:test:v1:001", "generation_context": {
            "text": "Treino tem limites.", "not_for": "Diagnosticar", "source_ids": ["s1"]}}]
    def query(self, text, **kwargs):
        self.calls.append(text)
        return {"status": "found" if self.rows else "no_evidence", "matches": deepcopy(self.rows)}

class LM:
    settings = {"max_input_tokens": 4000}
    variant = "test_double"
    decision = "RESPONDE 1"
    def count(self, messages):
        return sum(len(x["content"]) for x in messages)
    def generate(self, messages):
        self.messages = messages
        return {"text": self.decision, "generated_tokens": 4}

class CoachCompositionTests(unittest.TestCase):
    def setUp(self):
        self.nlp, self.search, self.lm = NLP(), Retrieval(), LM()
        self.c = Coach(self.nlp, self.search, self.lm)

    def test_iphone_deload_questions_continue_without_proposing_edits(self):
        self.nlp.route, self.nlp.label = "clarify", "adjust_training_volume"
        self.search.rows = [
            {"id": "kb:deload:v1:001", "document_id": "deload_meaning"},
            {"id": "kb:progress:v1:001", "document_id": "training_plateau_review_context"},
        ]
        self.c.respond("Oi")
        self.c.respond("Tudo bem?")
        first = self.c.respond("Veja bem eu estou faz varios meses treinando duro qria saber oq vc acha de fazer uma semana de deload?")
        self.assertIn("fadiga", first["answer"])
        second = self.c.respond("Eu estou me sentindo um pouco desestimulado, e sem conseguir evoluir os pesos, talvez seja melhor fazer essa de deload ou tem outra saida?")
        self.assertIn("revisando a progressão", second["answer"])
        self.assertEqual([], second["actions"])
        self.assertIn("vários exercícios", self.c.respond("Ainda não consigo evoluir as cargas")["answer"])

    def test_iphone_remada_question_uses_catalog_in_the_active_plan(self):
        snapshot = PlannerSnapshot(
            "test", "v1", workout_plan_id="workout",
            days=[{"id": "day", "weekday": "monday"}],
            workout_exercises=[{"id": "item", "workout_day_id": "day", "canonical": "remada cavalinho",
                                "display_name": "Remada cavalinho", "equipment": "landmine", "muscle_group": "upper_back",
                                "instructions": "Puxe a barra mantendo o tronco firme."}],
        )
        coach = Coach(self.nlp, self.search, self.lm, planner_snapshot=snapshot)
        self.nlp.route = "clarify"
        result = coach.respond("Oq seria remada cavalinho q tem no treino de hoje?", reference_date=date(2026, 11, 9))
        self.assertIn("barra apoiada em uma das pontas", result["answer"])
        self.assertEqual([], result["actions"])
        self.assertEqual([], self.search.calls)
        coach.respond("Isso, valeu.")
        answer = coach.respond("E ela trabalha o quê?")
        self.assertIn("costas", answer["answer"])
        self.assertEqual([], answer["actions"])

    def test_account_memory_requires_permission_and_is_independent_of_chat(self):
        text = "Lembre que prefiro treinar à noite"
        self.assertNotIn("memory_item", self.c.respond(text, account=AccountContext()))
        allowed = AccountContext(memory_enabled=True)
        result = self.c.respond(text, account=allowed)
        self.assertEqual("prefiro treinar à noite", result["memory_item"])
        private = self.c.respond("Lembre que prefiro usar o email pessoa@example.com", account=allowed)
        self.assertNotIn("memory_item", private)
        separate = Coach(self.nlp, self.search, self.lm)
        enabled = allowed.model_copy(update={"memories": [result["memory_item"]]})
        reply = separate.respond("Que horário eu prefiro treinar?", account=enabled)
        self.assertIn("à noite", reply["answer"])
        self.assertEqual({"topics": []}, reply["dialogue_context"])
        self.assertNotIn("à noite", separate.respond("Que horário eu prefiro treinar?", account=AccountContext())["answer"])

    def test_correction_survives_long_chat_and_does_not_leak_to_a_new_chat(self):
        coach = self.c
        coach.respond("Treino depois das 20h porque é quando dá.")
        coach.respond("Corrigindo, meu treino à noite é só terça e sábado.")
        for topic in range(12):
            coach.respond(f"Como treinar no exemplo {topic}?")
        for _ in range(60):
            coach.respond("Valeu!")
        result = coach.respond("Quais eram mesmo meus dias de treino à noite?", recalled=[])
        self.assertIn("terça e sábado", result["answer"])
        self.assertEqual(1, result["history_turns_dropped"])
        fresh = Coach(self.nlp, self.search, self.lm)
        answer = fresh.respond("Quais eram mesmo meus dias de treino à noite?", recalled=[])
        self.assertNotIn("sábado", answer["answer"])
        self.assertIn("desta conversa", answer["answer"])

    def test_cooking_constraints_are_updated_and_reused_after_an_aside(self):
        coach = self.c
        for message in (
            "Queria jantar com comida feita em casa.",
            "Tenho vinte minutos e um fogão pequeno.",
            "Na real dá meia hora.",
            "Gosto de feijão.",
            "A propósito tô com saudade de tocar violão.",
        ):
            coach.respond(message)
        reply = coach.respond("Voltando: me dá duas ideias que caibam no tempo que eu falei.")
        for detail in ("30 minutos", "fogão pequeno", "feijão"):
            self.assertIn(detail, reply["answer"])
        self.assertNotIn("20 minutos", reply["answer"])
        self.assertEqual([], reply["actions"])

    def test_social_conversation_moves_to_training_concepts_and_recalls_the_day(self):
        self.nlp.route = "clarify"
        self.search.rows = [
            {"id": "kb:sets:v1:001", "document_id": "sets_repetitions_plain",
             "generation_context": {"text": "Uma série reúne repetições."}},
            {"id": "kb:rest:v1:001", "document_id": "rest_between_sets_context",
             "generation_context": {"text": "Uma pausa permite recuperar parte do esforço."}},
        ]
        self.c.respond("Só consigo ir pra academia sábado de manhã essa semana.")
        for _ in range(15):
            self.c.respond("Valeu")
        definition = self.c.respond("Me ajuda: como explico pra ela o que é uma série?")
        self.assertIn("Uma série reúne repetições.", definition["answer"])
        pause = self.c.respond("E precisa fazer tudo sem pausa?")
        self.assertIn("Uma pausa permite", pause["answer"])
        self.assertIn("sábado de manhã", self.c.respond("Que dia mesmo eu disse que a gente ia?")["answer"])

    def test_reviewed_deload_definition_and_calendar_answer_both_parts(self):
        definition = {"id": "kb:deload:v1:001", "generation_context": {"text": "Deload reduz o estresse."}}
        calendar = {"id": "kb:calendar:v1:001", "generation_context": {"text": "Não há frequência única."}}
        sources = {"deload_meaning": definition, "deload_not_fixed_calendar": calendar}
        self.search.reviewed_document = lambda document, **kwargs: sources.get(document)
        self.nlp.route = "clarify"
        answer = self.c.respond("O que é deload e qual é o intervalo exato obrigatório entre deloads?")
        self.assertEqual("supported_excerpt", answer["grounding"]["status"])
        self.assertCountEqual([definition["id"], calendar["id"]], answer["citations"]["cited_chunk_ids"])
        self.assertEqual([], self.search.calls)
        sources.pop("deload_not_fixed_calendar")
        answer = self.c.respond("O que é deload e qual é o intervalo exato obrigatório entre deloads?")
        self.assertEqual("partial", answer["grounding"]["status"])
        self.assertEqual([definition["id"]], answer["citations"]["cited_chunk_ids"])
        gap = self.c.respond("Qual hormônio específico explica todos os efeitos do deload?")
        self.assertIn("Não tenho evidência", gap["answer"])
        self.assertEqual([], gap["citations"]["cited_chunk_ids"])

    def test_rest_continuation_never_substitutes_an_unrelated_candidate(self):
        self.search.reviewed_document = lambda document, **kwargs: None
        self.c.memory = self.c.memory.recording("knowledge", "O que é uma série?", {"document": "sets_repetitions_plain"})
        answer = self.c.respond("E preciso fazer tudo sem pausa?")
        self.assertEqual("no_evidence", answer["grounding"]["status"])
        self.assertEqual([], self.search.calls)
        self.assertEqual([], answer["citations"]["cited_chunk_ids"])
        self.assertIn("pausa entre séries", answer["answer"])

    def test_catalogue_reads_approved_foods_and_keeps_ambiguous_meals_read_only(self):
        self.c.action_session.snapshot = PlannerSnapshot(
            "test", "v1", diet_plan_id="diet",
            meal_items=[
                {"id": "item1", "canonical": "ovo", "meal_name": "Café da manhã",
                 "approved_replacement_ids": ["food1"]},
                {"id": "item2", "canonical": "ovo", "meal_name": "Almoço"},
            ],
            foods=[{"id": "food1", "canonical": "tofu"}, {"id": "food2", "canonical": "frango"}],
        )
        self.nlp.route, self.nlp.label = "draft_for_confirmation", "replace_meal_item"
        answer = self.c.respond("Quais as opções aprovadas para substituir o ovo do café da manhã?")
        self.assertIn("tofu", answer["answer"])
        self.assertNotIn("frango", answer["answer"])
        self.assertEqual([], answer["actions"])
        self.assertIn("Em qual refeição", self.c.respond(
            "Quais as opções aprovadas para substituir ovo na minha dieta?")["answer"])
        self.assertIn("motivo", self.c.respond("Por que colocaram ovo na minha dieta?")["answer"])
        self.assertEqual([], self.search.calls)

    def test_catalogue_reps_use_the_asked_day_or_clarify_if_ranges_differ(self):
        self.c.action_session.snapshot = PlannerSnapshot(
            "test", "v1", workout_plan_id="workout",
            days=[{"id": "mon", "weekday": "monday"}, {"id": "tue", "weekday": "tuesday"}],
            workout_exercises=[
                {"id": "item1", "workout_day_id": "mon", "canonical": "leg press", "min_reps": 8, "max_reps": 10},
                {"id": "item2", "workout_day_id": "tue", "canonical": "leg press", "min_reps": 10, "max_reps": 12},
            ],
        )
        ambiguous = self.c.respond("Qual a faixa de reps do leg press?")
        self.assertIn("Qual dia", ambiguous["answer"])
        resolved = self.c.respond("Qual a faixa de reps do leg press de terça?")
        self.assertIn("10 a 12 repetições", resolved["answer"])
        self.assertEqual([], resolved["actions"])

    def test_food_storage_logistics_can_continue_without_overriding_safety(self):
        self.c.respond("Queria levar um lanche para o trabalho.")
        self.nlp.route = "safety_information_only"
        self.nlp.risks = ["food_safety_uncertainty"]
        report = self.c.respond("Meu armário fica longe da geladeira.")
        self.assertEqual("storage_logistics", report["analysis"]["risk"]["routing_basis"])
        reply = self.c.respond("E qual opção posso levar fechada?")
        self.assertIn("sem geladeira", reply["answer"])
        self.assertIn("embalagens fechadas", reply["answer"])
        self.assertEqual([], reply["actions"])
        hazard = self.c.respond("Posso levar frango que ficou a noite fora da geladeira?")
        self.assertEqual("safety_information_only", hazard["analysis"]["route"])
        self.assertEqual([], hazard["actions"])

    def test_saved_account_schedule_is_distinct_from_the_conversation(self):
        account = AccountContext(training_time="19:30")
        self.c.respond("Treino às 8h esta semana.", account=account)
        reply = self.c.respond("Qual horário de treino está salvo na minha conta?", account=account)
        self.assertIn("19:30", reply["answer"])
        self.assertNotIn("8h", reply["answer"])

    def test_uses_profile_to_avoid_requesting_available_days_again(self):
        profile = AccountContext(weight_kg=73, training_days=["monday", "friday"])
        self.assertIn("73 kg", self.c.respond("Qual é meu peso?", account=profile)["answer"])
        goal = self.c.respond("Quero ganhar força", account=profile)
        self.assertIn("2 dias disponíveis no perfil", goal["answer"])

    def test_older_context_recall_quotes_only_provided_chat_excerpts(self):
        reply = self.c.respond("O que eu falei sobre barra?", recalled=["Eu prefiro usar a barra."])
        self.assertIn("Eu prefiro usar a barra", reply["answer"])
        self.assertEqual([], reply["actions"])

    def test_long_light_conversation_does_not_fill_grounded_prompt(self):
        for text in ("Oi", "Tudo bem?", "Tô de boa", "Só queria bater um papo", "Valeu") * 15:
            self.assertEqual("conversation", self.c.respond(text)["analysis"]["route"])
        self.assertEqual([], self.search.calls)
        self.assertEqual(8, len(self.c.history))
        result = self.c.respond("Qual a diferença entre séries e repetições?")
        self.assertEqual("supported_excerpt", result["grounding"]["status"])

    def test_bulk_training_request_invites_review_and_never_drafts(self):
        self.nlp.route = "draft_for_confirmation"
        result = self.c.respond("Tira todos os exercícios de bíceps")
        self.assertIn("O que está motivando isso", result["answer"])
        self.assertEqual([], result["actions"])

    def test_clear_coaching_question_uses_evidence_when_intent_classifier_is_wrong(self):
        self.nlp.route, self.nlp.label = "clarify", "adjust_training_intensity"
        for question in ("O que é RIR e repetições em reserva?", "Quanto de fibras a OMS recomenda por dia?"):
            with self.subTest(question=question):
                result = self.c.respond(question)
                self.assertEqual("supported_excerpt", result["grounding"]["status"])
                self.assertEqual([], result["actions"])
        result = self.c.respond("Como eu mudo o treino de terça para sexta?")
        self.assertIsNone(result.get("grounding"))
    def test_informal_report_inquiry_and_risk_take_distinct_paths(self):
        self.nlp.route, self.nlp.label = "draft_for_confirmation", "replace_exercise"
        report = self.c.respond("Boa noite, cheguei cansado hj.")
        self.assertEqual("conversation", report["analysis"]["route"])
        question = self.c.respond("Posso trocar o supino por flexão?")
        self.assertEqual("answer", question["analysis"]["route"])
        self.assertEqual([], question["actions"])
        danger = self.c.respond("Oi, tô sem ar agora. Troque o supino por flexão.")
        self.assertIn("emergency_symptom", danger["analysis"]["risk"]["labels"])
        self.assertEqual([], danger["actions"])
        self.assertEqual([], self.search.calls)

    def test_prompt_keeps_boundaries_and_compacts_source_metadata(self):
        result = self.c.respond("Como treinar?")
        prompt = self.lm.messages[-1]["content"]
        self.assertIn("Diagnosticar", prompt)
        self.assertNotIn('"source_ids"', prompt)
        self.assertEqual("Treino tem limites. [kb:test:v1:001]", result["answer"])
        self.assertEqual(["s1"], result["retrieval"]["matches"][0]["generation_context"]["source_ids"])
        self.assertEqual([], result["actions"])
        self.assertFalse(result["planner"]["writes_allowed"])
    def test_risk_and_pending_routes_bypass_generation_and_retrieval(self):
        for route in ["urgent_referral", "safety_information_only", "clarify_pending_action",
                      "draft_for_confirmation"]:
            self.nlp.route = route
            self.c.respond("Teste?")
        self.assertEqual([], self.search.calls)
        self.assertFalse(hasattr(self.lm, "messages"))
    def test_knowledge_fallback_keeps_uncertainty_but_not_actions(self):
        self.nlp.route = "clarify"
        self.assertTrue(self.c.respond("Como treinar?")["knowledge_only_fallback"])
        self.nlp.label = "move_workout_day"
        self.assertFalse(self.c.respond("Pode mudar?")["knowledge_only_fallback"])
        self.assertEqual(1, len(self.search.calls))
    def test_no_evidence_never_calls_lm(self):
        self.search.rows = []
        self.c.respond("Como treinar?")
        self.assertFalse(hasattr(self.lm, "messages"))
    def test_history_isolated_bounded_and_resettable(self):
        other = Coach(NLP(), Retrieval(), LM())
        for _ in range(8):
            self.c.respond("Como treinar?")
        self.assertEqual(8, len(self.c.history))
        self.assertEqual([], other.history)
        self.c.clear()
        self.assertEqual([], self.c.history)
    def test_overflow_requests_shorter_question_without_calling_model(self):
        self.lm.settings = {"max_input_tokens": 1}
        result = self.c.respond("Como treinar?")
        self.assertEqual("context_too_long", result["grounding"]["status"])
        self.assertFalse(hasattr(self.lm, "messages"))
        self.assertEqual([], result["citations"]["supplied_chunk_ids"])
    def test_invalid_input(self):
        for text in [" ", None, "a" * 8001]:
            with self.assertRaises(ValueError):
                self.c.respond(text)
    def test_identifiers_minimized_before_nlp_and_history(self):
        self.c.respond("Meu email é pessoa@example.com. Como treinar?")
        self.assertNotIn("pessoa@example.com", self.nlp.received[0])
        self.assertNotIn("pessoa@example.com", str(self.c.history))
    def test_citations_checked_against_delivered_evidence(self):
        result = self.c.respond("Como treinar?")
        self.assertEqual([], result["citations"]["unknown_chunk_ids"])
        self.assertEqual(["kb:test:v1:001"], result["citations"]["cited_chunk_ids"])
        self.assertFalse(result["citations"]["claim_faithfulness_verified"])

    def test_free_text_with_valid_citation_is_rejected(self):
        self.lm.decision = "Ganhe músculo em uma semana. [kb:test:v1:001]"
        result = self.c.respond("Como treinar?")
        self.assertEqual(NO_SUPPORT, result["answer"])
        self.assertEqual("invalid_selection", result["grounding"]["status"])
        self.assertEqual([], result["citations"]["cited_chunk_ids"])

    def test_unavailable_source_selection_is_rejected(self):
        self.lm.decision = "RESPONDE 2"
        result = self.c.respond("Como treinar?")
        self.assertEqual(NO_SUPPORT, result["answer"])
        self.assertEqual([], result["citations"]["cited_chunk_ids"])

    def test_partial_answer_retains_evidence_and_acknowledges_gap(self):
        self.lm.decision = "PARCIAL 1"
        result = self.c.respond("Como treinar?")
        self.assertEqual(f"Treino tem limites. [kb:test:v1:001] {PARTIAL}", result["answer"])
        self.assertEqual("partial", result["grounding"]["status"])

    def test_model_can_decline_irrelevant_retrieval(self):
        self.lm.decision = "SEM_BASE"
        result = self.c.respond("Como treinar?")
        self.assertEqual(NO_SUPPORT, result["answer"])
        self.assertEqual("insufficient", result["grounding"]["status"])
        self.assertEqual([], result["citations"]["cited_chunk_ids"])

    def test_mixed_question_combines_plan_fact_and_validated_sources(self):
        snapshot = PlannerSnapshot(
            "actor", "rev", workout_plan_id="workout",
            days=[{"id": "day", "weekday": "wednesday"}],
            workout_exercises=[{"id": "item", "workout_day_id": "day", "canonical": "remada cavalinho",
                                "min_reps": 8, "max_reps": 10}],
        )
        self.search.rows = [
            {"id": "kb:reps:v1:001", "generation_context": {"text": "Uma repetição é uma execução do movimento."}},
            {"id": "kb:series:v1:001", "generation_context": {"text": "Uma série agrupa repetições."}},
        ]
        self.lm.decision = "RESPONDE 1,2"
        coach = Coach(self.nlp, self.search, self.lm, planner_snapshot=snapshot)
        result = coach.respond("Quantas repetições tem a remada cavalinho na minha ficha? "
                               "Qual é a diferença entre séries e repetições?")
        self.assertIn("8 a 10 repetições", result["answer"])
        self.assertIn("fato_da_ficha", self.lm.messages[-1]["content"])
        self.assertEqual(["kb:reps:v1:001", "kb:series:v1:001"], result["citations"]["cited_chunk_ids"])
        self.assertEqual([], result["actions"])
        self.lm.decision = "RESPONDE 1,3"
        fallback = coach.respond("Quantas repetições tem a remada cavalinho na minha ficha? "
                                 "Qual é a diferença entre séries e repetições?")
        self.assertIn("8 a 10 repetições", fallback["answer"])
        self.assertIn(NO_SUPPORT, fallback["answer"])
        self.assertEqual([], fallback["citations"]["cited_chunk_ids"])

    def test_missing_exercise_asks_only_for_exercise(self):
        self.c.action_session.snapshot = PlannerSnapshot(
            "actor", "rev", workout_plan_id="workout",
            workout_exercises=[{"id": "item", "workout_day_id": "day", "canonical": "remada cavalinho",
                                "instructions": "Puxe a barra mantendo o tronco firme."}],
        )
        result = self.c.respond("Como faço esse exercício?")
        self.assertEqual(["exercise"], result["clarification"]["missing_fields"])
        self.assertEqual("Qual exercício da ficha você quer conferir?", result["answer"])
        followup = self.c.respond("A remada cavalinho")
        self.assertIn("Puxe a barra mantendo o tronco firme.", followup["answer"])
        self.assertFalse(followup["actions"])
        self.assertEqual([], self.search.calls)

    def test_search_retries_with_new_evidence_and_validates_original_message(self):
        class ContextualRetrieval(Retrieval):
            def query_conversation(self, text, history, **kwargs):
                return {"status": "no_evidence", "matches": []}

        search = ContextualRetrieval()
        message = "Gostaria de saber como organizar a rotina de treinos?"
        result = Coach(self.nlp, search, self.lm).respond(message)
        self.assertNotEqual(message, search.calls[0])
        self.assertIn(message, self.lm.messages[-1]["content"])
        self.assertTrue(result["grounding"]["retry_attempted"])
        self.assertEqual("supported_excerpt", result["grounding"]["status"])

    def test_daily_hydration_uses_context_and_respects_risk(self):
        self.nlp.route = "clarify"
        self.nlp.label = "clarification"
        result = self.c.respond("Gostaria de saber tipo o quanto de agua preciso beber ao dia?")
        self.assertIn("dia comum ou num dia de treino?", result["answer"])
        self.assertEqual(["kb:daily_hydration:v1.0.0:001"], result["citations"]["cited_chunk_ids"])
        result = self.c.respond("Tenho 1.78 e 73kg quanto de agua por dia?")
        self.assertIn("as medidas que você passou", result["answer"])
        self.assertIn("Quanto tempo costuma durar seu treino", result["answer"])
        self.assertEqual([], result["actions"])
        result = self.c.respond("Sinto dor no peito e falta de ar, quanta água devo beber por dia?")
        self.assertEqual("safety_information_only", result["analysis"]["route"])
        self.assertEqual([], result["citations"]["cited_chunk_ids"])

    def test_hydration_profile_survives_asides_and_topic_switch_in_same_conversation(self):
        first = self.c.respond("Quanto eu preciso de agua para tomar todo dia?")
        self.assertIn("dia comum ou num dia de treino", first["answer"])
        profile = "Dias comuns, 23 anos, 73kg,1.78, faco so academia 4 vezes por semana"
        result = self.c.respond(profile)
        self.assertIn("você está pensando nos dias comuns", result["answer"])
        self.assertEqual([profile], result["dialogue_context"]["topics"][-1]["details"])
        aside = self.c.respond("Ronald McDonalds é o cara")
        self.assertEqual("conversation", aside["analysis"]["route"])
        self.assertIn("hidratação", aside["answer"])
        for _ in range(5):
            self.c.respond("Valeu")
        self.c.respond("Quero ganhar força")
        self.assertEqual("training_goal", self.c.dialogue.topic)
        resumed = self.c.respond("Voltando à água")
        self.assertIn("Voltando à água nos dias comuns", resumed["answer"])
        self.assertEqual([profile], self.c.dialogue.details)
        self.assertIn("nos dias comuns", self.c.respond("E quantos litros então?")["answer"])
        self.assertEqual([], resumed["actions"])
        self.c.clear()
        result = self.c.respond("Voltando à água")
        self.assertEqual({"topics": []}, result["dialogue_context"])

    def test_first_grounded_question_can_anchor_conversation_with_comparative_wording(self):
        text = "Todo mundo deve beber a mesma quantidade de água no treino?"
        result = self.c.respond(text)
        self.assertEqual("supported_excerpt", result["grounding"]["status"])
        self.assertEqual(text, self.c.dialogue.anchor)

    def test_previous_user_question_is_context_but_assistant_claim_is_excluded(self):
        self.c.history = [{"role": "user", "content": "O que é volume?"},
                          {"role": "assistant", "content": "Afirmação inventada na resposta anterior."}]
        self.c.respond("E nesse caso?")
        self.assertIn("O que é volume?", self.lm.messages[-1]["content"])
        self.assertNotIn("Afirmação inventada", str(self.lm.messages))

    def test_conversational_opening_and_question_use_the_right_routes(self):
        for text, label in (
            ("Oi!", "greeting"),
            ("Tudo bem, e você?", "greeting"),
            ("Queria trocar uma ideia", "conversation_opening"),
            ("Quero falar de treino", "conversation_topic"),
            ("Valeu pela ajuda", "acknowledgment"),
        ):
            with self.subTest(text=text):
                result = self.c.respond(text)
                self.assertEqual("conversation", result["analysis"]["route"])
                self.assertEqual(label, result["analysis"]["intent"]["label"])
                self.assertEqual("not_requested", result["retrieval"]["status"])
                self.assertEqual([], result["actions"])
        self.assertFalse(hasattr(self.nlp, "received"))
        self.assertFalse(hasattr(self.lm, "messages"))
        result = self.c.respond("Oi, qual a diferença entre séries e repetições?")
        self.assertEqual("supported_excerpt", result["grounding"]["status"])
        self.assertEqual(1, len(self.search.calls))

    def test_greetings_vary_without_calling_the_language_model(self):
        replies = {self.c.respond("Oi")["answer"] for _ in range(3)}
        self.assertEqual(3, len(replies))
        self.assertFalse(hasattr(self.lm, "messages"))

    def test_safety_and_explicit_confirmation_keep_priority(self):
        result = self.c.respond("Oi!", proposal_id="test-proposal")
        self.assertEqual("Confirme ou rejeite explicitamente a proposta.", result["answer"])
        result = self.c.respond("Oi, sinto dor no peito e falta de ar.")
        self.assertIn("emergency_symptom", result["analysis"]["risk"]["labels"])
        self.assertEqual([], self.search.calls)


    def test_reports_get_followups_and_statements_can_request_information(self):
        for text, expected in (
            ("Treinei perna hoje", "durante o treino"),
            ("Dormi cinco horas ontem", "ao acordar"),
            ("Quero ganhar força", "seu objetivo"),
            ("Prefiro treinar à noite", "sua preferência"),
        ):
            with self.subTest(text=text):
                result = self.c.respond(text)
                self.assertEqual("conversation", result["analysis"]["route"])
                self.assertIn(expected, result["answer"])
                self.assertEqual([], result["actions"])
        self.assertEqual([], self.search.calls)
        self.nlp.route = "clarify"
        result = self.c.respond("Quero entender o que é deload")
        self.assertEqual("supported_excerpt", result["grounding"]["status"])
        result = self.c.respond("Treinei hoje e quero trocar o supino")
        self.assertNotEqual("conversation", result["analysis"]["route"])


if __name__ == "__main__":
    unittest.main()
