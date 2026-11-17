"""Regression coverage for Qwen routing with authenticated fixture data."""
from datetime import date
import json
import unittest
from uuid import UUID

from evolv_rag.account_context import AccountContext, AccountDay
from evolv_rag.actions import PlannerSnapshot
from evolv_rag.coach import Coach
from evolv_rag.safety import output_guard


def uid(number):
    return str(UUID(int=number))


class Interpreter:
    settings = {"max_input_tokens": 8192}

    def count(self, messages):
        return len(json.dumps(messages)) // 4

    def interpret(self, _):
        return self.output if isinstance(self.output, str) else json.dumps(self.output)


class QwenRouterTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 11, 11)
        self.model = Interpreter()
        self.coach = Coach(None, None, self.model, planner_snapshot=PlannerSnapshot(
            actor_id=uid(1), revision="test", workout_plan_id=uid(2), diet_plan_id=uid(3),
            days=[{"id": uid(4), "weekday": "wednesday", "title": "Inferiores"}],
            week=[
                {"date": "2026-11-11", "activity_type": "resistance", "workout_day_id": uid(4), "title": "Inferiores"},
                {"date": "2026-11-12", "activity_type": "rest", "workout_day_id": None, "title": "Descanso"},
            ],
            workout_exercises=[{"id": uid(5), "workout_day_id": uid(4), "canonical": "Subida no banco",
                                "min_reps": 10, "max_reps": 12, "rest_seconds": 90,
                                "instructions": "Faça as repetições por perna."}],
            meal_items=[{"id": uid(6), "meal_name": "Jantar", "meal_position": 2,
                         "canonical": "Salmão", "approved_replacement_ids": [uid(7)]}],
            foods=[{"id": uid(7), "canonical": "Peito de frango"}],
        ))

    def send(self, text, **prediction):
        self.model.output = prediction
        return self.coach.respond(text, reference_date=self.today)

    def test_approved_portion_stays_bound_to_the_selected_meal(self):
        snapshot = self.coach.action_session.snapshot
        dinner = snapshot.meal_items[0]
        dinner["approved_replacement_portions"] = [{"food_id": uid(7), "amount": "120 g"}]
        snapshot.meal_items.append({**dinner, "id": uid(8), "meal_name": "Almoço"})
        self.send("Corrigindo: quero olhar jantar. Lá tem Salmão?", op="chat")
        option = self.send("E a quantidade aprovada de Peito de frango pra essa substituição?", op="unclear")
        self.assertIn("120 g", option["answer"])
        self.assertFalse(option["actions"])
        self.send("O de almoço fica.", op="chat")
        reply = self.send("Beleza, registra essa substituição na refeição que corrigi, pela opção acima. "
                          "Deixa pra eu confirmar na prévia.", op="unclear")
        proposal, = reply["actions"]
        self.assertEqual(proposal["payload"]["meal_item_id"], uid(6))
        self.assertEqual(proposal["payload"]["replacement_food_id"], uid(7))
        self.assertFalse(reply["planner"]["writes_allowed"])

    def test_reporting_a_missed_meal_is_read_only_until_the_approved_swap_is_requested(self):
        report = self.send("Não comi Salmão de jantar. Acabou aqui. Isso foi só um relato.", op="replace_food")
        self.assertFalse(report["actions"])
        option = self.send("No cardápio consta Peito de frango como opção nesse horário?", op="unclear")
        self.assertIn("plano aprova Peito de frango", option["answer"])
        self.assertFalse(option["actions"])
        reply = self.send("Se estiver, quero usar de agora em diante na ficha. "
                          "O de almoço segue igual. É pra aplicar agora direto na ficha.", op="unclear")
        proposal, = reply["actions"]
        self.assertEqual(proposal["payload"]["meal_item_id"], uid(6))
        self.assertEqual(proposal["status"], "pending_user_confirmation")

    def test_acknowledging_a_meal_does_not_consume_the_option_or_prepare_a_proposal(self):
        self.send("Quanto de Salmão aparece no jantar?", op="chat")
        self.send("Qual opção cadastrada eu posso usar no lugar dele?", op="chat")
        note = self.send("Certo, nessa refeição só. Sei que tem o mesmo alimento em outro horário.",
                         op="replace_food", item="Salmão", replacement="Peito de frango", meal="Jantar",
                         purpose="apply", request_evidence="Qual opção cadastrada eu posso usar no lugar dele?")
        self.assertFalse(note["actions"])
        reply = self.send("Pode fazer essa troca aí na ficha, da porção original pela aprovada. "
                          "Me mostra a prévia primeiro, sem aplicar.", op="unclear")
        proposal, = reply["actions"]
        self.assertEqual(proposal["payload"]["meal_item_id"], uid(6))
        self.assertEqual(proposal["status"], "pending_user_confirmation")

    def test_a_casual_aside_can_be_answered_without_reclassifying_a_pending_swap(self):
        self.send("Quanto de Salmão aparece no jantar?", op="chat")
        self.send("Qual opção cadastrada eu posso usar no lugar dele?", op="chat")
        self.model.write = lambda messages: {"text": "Putz, perder o fone é chato.", "stopped_at_eos": True}
        aside = self.send("Aliás, esqueci meu fone no ônibus. Mas bora voltar pra ficha depois.",
                          op="replace_food", item="salmão", replacement="frango", purpose="apply")
        self.assertIn("perder o fone", aside["answer"])
        self.assertFalse(aside["actions"])
        result = self.send("Pode fazer essa troca na ficha. Quero ver a prévia.", op="unclear")
        self.assertEqual(result["actions"][0]["status"], "pending_user_confirmation")

    def test_uses_the_named_free_date_for_a_one_off_reschedule_after_a_missing_workout_query(self):
        source = self.send("Se eu faltar quarta, o treino é qual? Tenho reunião.", op="unclear")
        self.assertIn("Inferiores", source["answer"])
        check = self.send("Pensei em encaixar na quinta. Quero ver se esse dia tá realmente livre.", op="unclear")
        self.assertIn("Quinta está livre", check["answer"])
        self.assertFalse(check["actions"])
        self.send("Minha rotina das próximas semanas continua igual, beleza?", op="chat")
        reply = self.send("Então remarca esse treino pro dia livre que falei, só agora e sem mexer nas outras semanas. "
                          "É pra aplicar agora direto na ficha.", op="unclear")
        proposal, = reply["actions"]
        self.assertEqual(proposal["payload"]["kind"], "move_workout_occurrence")
        self.assertEqual(proposal["payload"]["target_date"], "2026-11-12")
        self.assertFalse(reply["planner"]["writes_allowed"])

    def test_scope_requires_user_evidence_then_resumes_the_pending_move(self):
        first = self.send("Pega o treino de quarta e bota na quinta, ok?", op="move_workout",
                          day="quarta", destination="quinta", scope="recurring")
        self.assertEqual(first["actions"], [])
        self.assertIn("nesta semana", first["answer"])
        second = self.send("só nesta semana", op="continue", scope="week")
        action, = second["actions"]
        self.assertEqual(action["status"], "pending_user_confirmation")
        self.assertEqual(action["payload"]["kind"], "move_workout_occurrence")
        self.assertEqual(action["payload"]["source_date"], "2026-11-11")
        self.assertEqual(action["payload"]["target_date"], "2026-11-12")
        self.assertFalse(second["planner"]["writes_allowed"])

    def test_model_can_authorize_an_informal_scope_without_a_fixed_phrase(self):
        first = self.send("joga o de quarta p quinta pfv", op="move_workout",
                          day="quarta", destination="quinta", purpose="apply",
                          request_evidence="joga o de quarta p quinta")
        self.assertFalse(first["actions"])
        reply = self.send("td smn msm", op="continue", scope="recurring",
                          scope_evidence="td smn", day="sábado", destination="sexta")
        action, = reply["actions"]
        self.assertEqual(action["status"], "pending_user_confirmation")
        self.assertEqual(action["payload"]["workout_day_id"], uid(4))
        self.assertEqual(action["payload"]["target_weekday"], "thursday")

    def test_consultation_and_preview_do_not_get_automatic_authorization(self):
        prediction = dict(op="replace_food", item="salmão", replacement="frango", meal="jantar")
        inquiry = self.send("Posso trocar salmão por frango no jantar?",
                            purpose="apply", request_evidence="trocar salmão por frango", **prediction)
        self.assertEqual(inquiry["actions"], [])
        preview = self.send("Quero ver a prévia de salmão por frango no jantar",
                            purpose="preview", request_evidence="ver a prévia", **prediction)
        self.assertEqual(preview["actions"][0]["status"], "pending_user_confirmation")
        direct = self.send("Tira o salmão do jantar e põe frango no lugar pfv",
                           purpose="apply", request_evidence="Tira o salmão do jantar e põe frango no lugar", **prediction)
        self.assertEqual(direct["actions"][0]["status"], "pending_user_confirmation")

    def test_calendar_read_handles_short_followup_and_session_title_without_actions(self):
        snapshot = self.coach.action_session.snapshot
        snapshot.days[0]["title"] = snapshot.week[0]["title"] = "Superiores B"
        self.send("Me manda minha rotina de treino semanal p eu ver", op="week")
        short = self.send("Hoje é dia de que?", op="move_workout", purpose="inquire")
        direct = self.send("Qual o meu treino de hoje?", op="exercise", item="Superiores B", day="quarta")
        for result in (short, direct):
            self.assertIn("Quarta (11/11): Superiores B.", result["answer"])
            self.assertEqual(result["actions"], [])
            self.assertEqual(result["analysis"]["intent"]["label"], "week")
        rest = self.send("Qual o treino de quinta?", op="week", day="quinta")
        self.assertIn("descanso", rest["answer"])

    def test_calendar_followup_uses_saved_subject_after_an_aside_and_crosses_into_monday(self):
        self.today = date(2026, 11, 15)
        self.coach.action_session.snapshot.week = [
            {"date": "2026-11-09", "activity_type": "resistance", "title": "Treino antigo"},
            {"date": "2026-11-15", "activity_type": "rest", "title": None},
            {"date": "2026-11-16", "activity_type": "resistance", "title": "Treino remarcado"},
        ]
        first = self.send("Qual meu treino hj?", op="week", day="hoje")
        self.assertIn("Domingo (15/11): descanso.", first["answer"])
        self.coach.memory = self.coach.memory.model_validate_json(self.coach.memory.model_dump_json()).minimized()
        self.coach.history = []
        self.send("Valeu pela ajuda", op="chat")
        reply = self.send("E amanhã?", op="unclear")
        self.assertIn("Segunda (16/11): Treino remarcado.", reply["answer"])
        self.assertFalse(reply["actions"])

    def test_calendar_clarification_and_followup_are_reads_even_if_the_model_predicts_a_move(self):
        self.coach.action_session.snapshot.week.append(
            {"date": "2026-11-14", "activity_type": "cardio", "title": "Circuito complementar"},
        )
        guessed_move = {"op": "move_workout", "day": "quarta", "destination": "quinta", "purpose": "apply"}
        reference = self.send("Tem treino naquele dia? Ainda não falei qual.", **guessed_move)
        self.assertIn("Qual dia", reference["answer"])
        saturday = self.send("No sábado, era o que eu tava pensando.", **guessed_move)
        self.assertIn("Circuito complementar", saturday["answer"])
        self.send("Quantos dias de treino minha ficha tem na semana?", op="chat")
        monday = self.send("E o segunda, na mesma semana?", **guessed_move)
        self.assertIn("Segunda", monday["answer"])
        self.assertFalse(monday["actions"])

    def test_remembers_the_first_workout_read_across_other_topics(self):
        self.send("Qual meu treino hoje?", op="chat")
        self.send("O que eu como no jantar?", op="chat")
        self.send("E o treino de quinta?", op="week", day="quinta")
        first = self.send("E o treino que eu tinha consultado primeiro, lembra qual era?", op="recall", turn=1)
        self.assertIn("Quarta (11/11): Inferiores.", first["answer"])
        self.assertFalse(first["actions"])

    def test_recalls_a_report_from_this_chat_without_using_account_memory(self):
        self.send("Antes da gente seguir, saio do estágio mais tarde. Isso é contexto, tá?", op="chat")
        self.coach.history = []
        followup = self.send("O que eu tinha dito sobre a minha rotina hoje? Só o motivo que te contei.", op="memory")
        self.assertIn("saio do estágio mais tarde", followup["answer"])
        self.assertNotIn("memory_item", followup)
        self.assertFalse(followup["actions"])

    def test_diet_followup_reads_current_menu_and_never_reuses_workout_subject(self):
        snapshot = self.coach.action_session.snapshot
        snapshot.meal_items[0]["amount"] = "100 g"
        snapshot.meal_items.append({**snapshot.meal_items[0], "id": uid(8),
                                    "meal_name": "Almoço", "amount": "130 g", "canonical": "Tofu"})
        self.send("Qual meu treino hj?", op="week", day="hoje")
        lunch = self.send("O que eu como no almoço?", op="chat")
        self.assertIn("Almoço: Tofu (130 g).", lunch["answer"])
        self.send("Valeu!", op="chat")
        dinner = self.send("e no jantar?", op="unclear")
        self.assertIn("Jantar: Salmão (100 g).", dinner["answer"])
        self.assertFalse(dinner["actions"])
        wrong_day = self.send("E amanhã, o que como no almoço?", op="diet", meal="almoço")
        self.assertNotIn("Tofu", wrong_day["answer"])

    def test_diet_filters_the_same_rotation_and_day_type_as_the_diet_tab(self):
        snapshot = self.coach.action_session.snapshot
        snapshot.diet_variants = True
        snapshot.diet_rotation_size = 2
        rotation = (self.today - date(1970, 1, 1)).days % 2
        item = snapshot.meal_items[0]
        snapshot.meal_items = [
            {**item, "day_type": "training_day", "rotation_index": rotation, "amount": "155 g"},
            {**item, "day_type": "rest_day", "rotation_index": rotation, "canonical": "Ovo"},
            {**item, "day_type": "training_day", "rotation_index": 1 - rotation, "canonical": "Tofu"},
        ]
        account = AccountContext(day=AccountDay(date=self.today, source="workout_plan",
                                 activity_type="resistance", nutrition_day_type="training_day"))
        self.model.output = {"op": "diet", "meal": "jantar"}
        result = self.coach.respond("O que eu como no jantar?", reference_date=self.today, account=account)
        self.assertEqual(result["answer"], "Jantar: Salmão (155 g).")
        self.assertFalse(result["actions"])

    def test_reads_a_portion_then_reuses_the_verified_item_for_a_food_preview(self):
        snapshot = self.coach.action_session.snapshot
        snapshot.meal_items.extend([{**snapshot.meal_items[0], "id": uid(8), "meal_name": "Almoço",
                                    "amount": "85 g", "approved_replacement_portions": [
                                        {"food_id": uid(7), "amount": "110 g"}]},
                                   {"id": uid(9), "meal_name": "Almoço", "canonical": "Pepino"}])
        first = self.send("No almoço tá aparecendo quanto de salmão?", op="chat")
        self.assertIn("85 g", first["answer"])
        self.send("Vou passar no mercado antes", op="chat")
        option = self.send("Tô pensando em usar peito de frango pra aquela refeição. Tá cadastrado?",
                           op="food_options", item="peito de frango")
        self.assertIn("110 g", option["answer"])
        self.assertFalse(option["actions"])
        reply = self.send("Agr quero mesmo substituir o que a gente falou, só nesse horário do plano. "
                          "Só prepara a prévia pra eu conferir.",
                          op="unclear")
        action, = reply["actions"]
        self.assertEqual(action["status"], "pending_user_confirmation")
        self.assertEqual(action["payload"]["meal_item_id"], uid(8))
        self.assertEqual(action["payload"]["replacement_food_id"], uid(7))
        self.assertFalse(reply["planner"]["writes_allowed"])

    def test_first_mentioned_meal_is_not_the_first_meal_of_the_day(self):
        snapshot = self.coach.action_session.snapshot
        item = snapshot.meal_items[0]
        snapshot.meal_items.extend([
            {**item, "id": uid(8), "meal_name": "Almoço", "meal_position": 1},
            {**item, "id": uid(9), "meal_name": "Café da manhã", "meal_position": 0},
        ])
        self.send("O salmão aparece no almoço e no jantar?", op="chat")
        self.send("Tô pensando no peito de frango. Será que cabe no almoço?", op="chat")
        self.send("Quero manter o jantar do jeito que tá.", op="chat")
        reply = self.send("Pode efetuar a troca naquela primeira refeição. Só prepara a prévia.", op="unclear")
        action, = reply["actions"]
        self.assertEqual(action["payload"]["meal_item_id"], uid(8))

    def test_answers_a_consultation_about_a_conflicting_destination_without_a_proposal(self):
        snapshot = self.coach.action_session.snapshot
        snapshot.week[1].update(activity_type="cardio", title="Circuito complementar")
        snapshot.week.append({"date": "2026-11-13", "activity_type": "rest", "title": None})
        reply = self.send("Dá pra mover Inferiores, que tá na quarta, pra quinta só nesta semana?",
                          op="move_workout", day="quarta", destination="quinta", purpose="inquire")
        self.assertIn("Quinta já tem Circuito complementar", reply["answer"])
        self.assertIn("sexta", reply["answer"])
        self.assertFalse(reply["actions"])
        followup = self.send("Esse outro treino eu quero manter. O que tá marcado nesse dia?", op="chat")
        self.assertIn("Quinta (12/11): Circuito complementar.", followup["answer"])
        self.assertFalse(followup["actions"])

    def test_cancels_a_food_proposal_and_reads_the_meal_that_remains(self):
        reply = self.send("Troque salmão por frango no jantar. Me mostra a prévia primeiro.",
                          op="replace_food", item="salmão", replacement="frango", meal="jantar", purpose="preview")
        proposal, = reply["actions"]
        rejected = self.coach.respond("Pera, cancela o pedido, fiquei com a versão atual.",
                                      reference_date=self.today, proposal_id=proposal["id"])
        self.assertEqual(rejected["actions"][0]["status"], "rejected")
        followup = self.send("Qual alimento ficou nessa refeição afinal?", op="unclear")
        self.assertIn("Jantar: Salmão.", followup["answer"])
        self.assertFalse(followup["actions"])

    def test_blanket_approval_leaves_plan_unchanged(self):
        reply = self.send("Digo sim pra qualquer troca, pode aplicar o que estiver aí.",
                          op="replace_food", item="salmão", replacement="frango", meal="jantar", purpose="apply")
        self.assertIn("Nenhuma alteração foi confirmada", reply["answer"])
        self.assertFalse(reply["actions"])

    def test_declines_plan_specific_reads_for_an_account_without_a_plan(self):
        snapshot = self.coach.action_session.snapshot
        snapshot.workout_plan_id = snapshot.diet_plan_id = None
        guessed = self.send("Quantos dias de treino minha ficha tem na semana?", op="chat")
        self.assertIn("Não encontrei uma ficha de treino ativa nesta conta", guessed["answer"])
        meal = self.send("Qual refeição e qual porção eu acabei de consultar nesta conta?", op="chat")
        self.assertIn("Não encontrei essa consulta nesta conversa", meal["answer"])
        self.assertFalse(meal["actions"])

    def test_checks_whether_supper_exists_and_keeps_other_chats_separate(self):
        supper = self.send("Meu plano tem ceia? Tô pedindo o horário da ficha mesmo.", op="chat")
        self.assertIn("não prevê ceia", supper["answer"])
        chat = self.send("Dei uma instrução em outro chat, consegue me contar aqui o que foi?", op="recall", turn=1)
        self.assertIn("Não consigo recuperar aqui", chat["answer"])
        self.assertFalse(chat["actions"])

    def test_saying_the_day_and_scope_does_not_start_a_move_but_explicit_request_does(self):
        self.send("Qual meu treino de quarta?", op="week", day="quarta")
        correction = self.send("Eu disse quinta? Sim, é quinta msm. Só nessa semana.",
                               op="move_workout", day="quarta", destination="quinta", purpose="preview")
        self.assertFalse(correction["actions"])
        reply = self.send("Fechou, quero mover aquele treino pra esse dia só dessa vez. Quero ver a prévia.",
                          op="move_workout", day="quarta", destination="quinta", purpose="preview")
        proposal, = reply["actions"]
        self.assertEqual(proposal["status"], "pending_user_confirmation")
        self.assertEqual(proposal["payload"]["target_date"], "2026-11-12")

    def test_resuming_the_topic_does_not_replace_the_verified_origin_or_the_stated_destination(self):
        self.send("Qual meu treino de quarta?", op="week", day="quarta")
        option = self.send("Se passar pra quinta, é só uma possibilidade por enquanto.", op="unclear")
        self.assertIn("Quinta está livre", option["answer"])
        self.assertFalse(option["actions"])
        self.send("Blz, agora vamos voltar pro plano mesmo.", op="week", day="segunda")
        self.send("Eu disse quinta? Sim, é quinta msm. O pulo é só nessa semana.", op="unclear")
        reply = self.send("Fechou, quero mover aquele treino pra esse dia só dessa vez. É pra aplicar agora direto na ficha.",
                          op="move_workout", day="segunda", destination="sábado", purpose="apply")
        proposal, = reply["actions"]
        self.assertEqual(proposal["payload"]["source_date"], "2026-11-11")
        self.assertEqual(proposal["payload"]["target_date"], "2026-11-12")
        self.assertEqual(proposal["status"], "pending_user_confirmation")

    def test_reference_to_a_free_day_uses_the_calendar_and_the_workout_in_difficult_schedule(self):
        snapshot = self.coach.action_session.snapshot
        snapshot.week.append({"date": "2026-11-13", "activity_type": "rest", "title": None})
        self.send("Tá ficando apertado treinar na quarta: meu turno mudou.", op="chat")
        free = self.send("O sexta tá sobrando mesmo na minha ficha?", op="chat")
        self.assertIn("Sexta (13/11): descanso.", free["answer"])
        self.send("Blz, agora vamos voltar pro plano mesmo.", op="week", day="segunda")
        reply = self.send("Quero deixar naquele dia livre toda semana daqui pra frente, pode mudar. Quero ver a prévia.",
                          op="move_workout", day="segunda", destination="sábado", scope="recurring", purpose="preview")
        proposal, = reply["actions"]
        self.assertEqual(proposal["payload"]["target_weekday"], "friday")
        self.assertEqual(proposal["payload"]["workout_day_id"], uid(4))

    def test_a_weekly_title_lookup_uses_the_ficha_even_if_the_model_guesses_a_move(self):
        self.coach.action_session.snapshot.days[0]["weekday"] = "thursday"
        read = self.send("Pra confirmar: onde fica Inferiores toda semana agora?",
                         op="move_workout", day="quarta", destination="sexta", scope="recurring", purpose="preview")
        self.assertEqual(read["answer"], "Quinta: Inferiores na ficha semanal.")
        self.assertFalse(read["actions"])

    def test_a_move_from_that_day_uses_the_verified_read_instead_of_the_models_guess(self):
        self.send("Minha agenda muda por causa do estágio. Quem tá marcado na quarta?", op="chat")
        self.send("Só no horário fixo mesmo", op="chat")
        reply = self.send("Pode mover o treino desse dia pra quinta toda semana. Quero confirmar na prévia.",
                          op="move_workout", day="segunda", destination="quinta", scope="recurring", purpose="preview")
        action, = reply["actions"]
        self.assertEqual(action["payload"]["workout_day_id"], uid(4))
        self.assertEqual(action["payload"]["target_weekday"], "thursday")

    def test_move_reuses_verified_workout_and_corrected_availability_in_a_preview(self):
        self.send("Dá uma olhada no treino de quarta?", op="chat")
        corrected = self.send("Vixe, falei domingo no automático. quinta é que tá livre.", op="chat")
        self.assertFalse(corrected["actions"])
        self.send("Qual foi o dia que eu disse que tá livre agora?", op="recall", turn=3)
        reply = self.send("Passa o treino que tu viu pro dia corrigido, mas só dessa semana aí. "
                          "Só prepara a prévia pra eu conferir.", op="move_workout")
        action, = reply["actions"]
        self.assertEqual(action["status"], "pending_user_confirmation")
        self.assertEqual(action["payload"]["source_date"], "2026-11-11")
        self.assertEqual(action["payload"]["target_date"], "2026-11-12")
        self.assertFalse(reply["planner"]["writes_allowed"])

    def test_reselects_the_destination_without_losing_scope_after_a_calendar_conflict(self):
        snapshot = self.coach.action_session.snapshot
        snapshot.week.extend([
            {"date": "2026-11-13", "activity_type": "cardio", "workout_day_id": None, "title": "Cardio"},
            {"date": "2026-11-14", "activity_type": "rest", "workout_day_id": None, "title": None},
        ])
        blocked = self.send("Quero a prévia pra mover meu treino de quarta pra sexta só dessa semana",
                            op="move_workout", day="quarta", destination="sexta", purpose="preview")
        self.assertIn("já tem atividade", blocked["answer"])
        self.assertIn("sábado", blocked["answer"])
        self.assertFalse(blocked["actions"])
        reply = self.send("Então no sábado", op="chat")
        action, = reply["actions"]
        self.assertEqual(action["payload"]["source_date"], "2026-11-11")
        self.assertEqual(action["payload"]["target_date"], "2026-11-14")

    def test_scope_reply_recovers_invalid_model_json_but_requires_a_verified_draft(self):
        self.model.output = '{"op":"continue","scope":"this_week"}'
        without_draft = self.coach.respond("So nesta semana mesmo", reference_date=self.today)
        self.assertEqual(without_draft["actions"], [])
        self.send("Passa o treino de hoje para amanhã pfv", op="move_workout", day="hoje",
                  destination="amanhã", purpose="apply", request_evidence="Passa o treino de hoje para amanhã")
        self.model.output = '{"op":"continue","scope":"this_week"}'
        result = self.coach.respond("So nesta semana mesmo", reference_date=self.today)
        action, = result["actions"]
        self.assertEqual(action["status"], "pending_user_confirmation")
        self.assertEqual(action["payload"]["kind"], "move_workout_occurrence")
        self.assertEqual(action["payload"]["source_date"], "2026-11-11")
        self.assertEqual(action["payload"]["target_date"], "2026-11-12")

    def test_scope_recovery_does_not_turn_a_preview_or_changed_plan_into_a_write(self):
        first = dict(op="move_workout", day="quarta", destination="quinta", purpose="preview",
                     request_evidence="prévia")
        self.send("Quero a prévia de mover quarta pra quinta", **first)
        result = self.send("só nesta semana", op="chat")
        self.assertEqual(result["actions"][0]["status"], "pending_user_confirmation")
        self.send("Muda quarta pra quinta", **{**first, "purpose": "apply", "request_evidence": "Muda"})
        self.coach.action_session.snapshot.revision = "changed-plan"
        result = self.send("só nesta semana", op="continue", scope="week")
        self.assertEqual(result["actions"], [])

    def test_prescription_uses_requested_fields_and_disregards_generated_values(self):
        result = self.send("Subida no banco de quarta, quanto descanso e quantas reps?",
                           op="exercise", day="quarta", item="Subida no banco", fields={"reps": 999, "rest": 800})
        self.assertIn("90 segundos", result["answer"])
        self.assertIn("10 a 12 por perna", result["answer"])
        self.assertNotIn("999", result["answer"])
        self.assertNotIn("800", result["answer"])

    def test_food_inquiry_is_read_only_and_never_picks_an_unapproved_alternative(self):
        result = self.send("Na última refeição de hoje não consigo comer salmão, pode trocar por frango ou carne?",
                           op="food_options", item="salmão", meal="refeição", options=["frango", "carne"])
        self.assertEqual(result["actions"], [])
        self.assertIn("Peito de frango", result["answer"])
        result = self.send("Troque salmão por carne no jantar", op="replace_food",
                           item="salmão", meal="jantar", replacement="carne")
        self.assertEqual(result["actions"], [])
        self.assertIn("Peito de frango", result["answer"])

    def test_temporary_food_swap_does_not_prepare_a_permanent_menu_change(self):
        result = self.send("Troca salmão por frango no jantar só dessa semana ai",
                           op="replace_food", item="salmão", replacement="frango",
                           meal="jantar", purpose="preview")
        self.assertFalse(result["actions"])
        self.assertIn("altera o cardápio", result["answer"])

    def test_correction_and_spoken_claim_cannot_change_the_plan(self):
        result = self.send("Troquei meu plantão, na verdade vou estar livre na sexta.",
                           op="day_activity", day="sexta", activity="resistance")
        self.assertEqual(result["actions"], [])
        self.assertIsNotNone(output_guard("A programação foi ajustada.", ()))


    def test_does_not_guess_the_meal_when_food_appears_twice(self):
        snapshot = self.coach.action_session.snapshot
        snapshot.meal_items.append({**snapshot.meal_items[0], "id": uid(8),
                                    "meal_name": "Almoço", "meal_position": 1})
        reply = self.send("Troca salmão por frango", op="replace_food",
                          item="salmão", meal="jantar", replacement="frango")
        self.assertEqual(reply["actions"], [])
        self.assertIn("Em qual refeição", reply["answer"])
        reply = self.send("É a fruta do almoço que eu quis dizer", op="food_options",
                          item="salmão", options=["frango"])
        proposal, = reply["actions"]
        self.assertEqual(proposal["payload"]["meal_item_id"], uid(8))
        rejected = self.coach.respond("Deixa como está, não quero mais trocar",
                                      reference_date=self.today, proposal_id=proposal["id"])
        self.assertEqual(rejected["actions"][0]["status"], "rejected")

    def test_availability_corrections_survive_restore_without_remarking_workout(self):
        messages = ("Consigo treinar segunda no horário do almoço e sexta à noite",
                    "Só tenho uma bolsa térmica para levar comida",
                    "Segunda mudou para quarta",
                    "Corrigindo, quarta é à tarde")
        for text in messages:
            result = self.send(text, op="move_workout", day="segunda", destination="quarta", purpose="apply",
                               request_evidence=text[:100])
            self.assertEqual(result["actions"], [])
        self.coach.memory = self.coach.memory.model_validate_json(self.coach.memory.model_dump_json()).minimized()
        self.coach.history = []
        result = self.send("Quais horários eu falei e o que tenho para levar comida?", op="unclear")
        self.assertIn("quarta à tarde", result["answer"])
        self.assertIn("sexta à noite", result["answer"])
        self.assertIn("bolsa térmica", result["answer"])
        self.assertNotIn("segunda", result["answer"])
        self.coach.clear()
        self.assertNotIn("sexta à noite", self.send("Qual horário eu falei?", op="recall")["answer"])

    def test_meal_scope_does_not_replace_pending_items(self):
        snapshot = self.coach.action_session.snapshot
        snapshot.meal_items.append({**snapshot.meal_items[0], "id": uid(8),
                                    "meal_name": "Almoço", "meal_position": 1})
        first = self.send("Troca salmão por frango", op="replace_food", item="salmão", replacement="frango",
                          purpose="apply", request_evidence="Troca salmão por frango")
        self.assertEqual(first["actions"], [])
        result = self.send("só no almoço", op="continue", meal="Almoço", meal_evidence="no almoço",
                           scope="week", item="maçã", replacement="tofu")
        action, = result["actions"]
        self.assertEqual(action["payload"]["meal_item_id"], uid(8))
        self.assertEqual(action["payload"]["replacement_food_id"], uid(7))
        self.assertEqual(action["status"], "pending_user_confirmation")

    def test_move_preserves_origin_when_user_supplies_new_destination(self):
        snapshot = self.coach.action_session.snapshot
        snapshot.days.append({"id": uid(8), "weekday": "friday", "title": "Superiores"})
        self.send("Move o treino de quarta para sexta toda semana", op="move_workout",
                  day="quarta", destination="sexta", scope="recurring", purpose="apply",
                  request_evidence="Move o treino de quarta para sexta")
        result = self.send("Então deixa na quinta toda semana", op="move_workout",
                           day="quinta", destination="sexta", scope="recurring")
        action, = result["actions"]
        self.assertEqual(action["payload"]["workout_day_id"], uid(4))
        self.assertEqual(action["payload"]["target_weekday"], "thursday")

    def test_food_reference_survives_restore_and_uses_current_catalogue(self):
        self.send("O que tem no jantar?", op="diet", meal="jantar")
        self.coach.memory = self.coach.memory.model_validate_json(self.coach.memory.model_dump_json()).minimized()
        self.coach.history = []
        result = self.send("Troca aquele peixe por frango no jantar", op="replace_food", item="peixe",
                           replacement="frango", purpose="apply", request_evidence="Troca aquele peixe por frango")
        self.assertEqual(result["actions"][0]["payload"]["meal_item_id"], uid(6))
        self.coach.action_session.snapshot.meal_items[0]["canonical"] = "Atum"
        result = self.send("Troca aquele peixe por frango no jantar", op="replace_food", item="peixe",
                           replacement="frango", purpose="apply", request_evidence="Troca aquele peixe por frango")
        self.assertEqual(result["actions"], [])

    def test_cross_chat_confirmation_cannot_complete_current_draft(self):
        self.send("Muda o treino de quarta para quinta", op="move_workout", day="quarta", destination="quinta",
                  purpose="apply", request_evidence="Muda o treino de quarta para quinta")
        draft = self.coach.router_draft
        result = self.send("Sim, aplica a troca que combinei na outra conversa", op="continue", scope="recurring")
        self.assertEqual(result["actions"], [])
        self.assertEqual(self.coach.router_draft, draft)

    def test_report_followed_by_explicit_move_is_still_a_request(self):
        text = "Só consigo treinar na quinta, então move o treino de quarta para quinta toda semana"
        result = self.send(text, op="move_workout", day="quarta", destination="quinta", scope="recurring",
                           purpose="apply", request_evidence="move o treino de quarta para quinta")
        action, = result["actions"]
        self.assertEqual(action["payload"]["target_weekday"], "thursday")

    def test_availability_correction_replaces_a_rejected_day(self):
        self.send("Consigo ir terça cedo e sexta à noite", op="chat")
        self.send("Ops, terça não funciona. Quinta de manhã", op="chat")
        reply = self.send("Quais dias eu falei?", op="unclear")["answer"]
        self.assertIn("quinta de manhã", reply)
        self.assertIn("sexta à noite", reply)
        self.assertNotIn("terça", reply)

    def test_question_about_rescheduling_does_not_authorize_then_can_preview(self):
        text = "Preciso mudar o treino de quarta para quinta. O que mudaria se fosse só nesta semana?"
        result = self.send(text, op="move_workout", day="quarta", destination="quinta",
                           purpose="apply", request_evidence=text, scope="week")
        self.assertEqual(result["actions"], [])
        self.assertIn("apenas o calendário", result["answer"])
        confirmed = self.send("Quero fixar esse dia. Prepara a prévia.", op="unclear")
        action, = confirmed["actions"]
        self.assertEqual(action["status"], "pending_user_confirmation")
        self.assertEqual(action["payload"]["kind"], "move_workout_day")
        self.assertEqual(action["payload"]["target_weekday"], "thursday")

    def test_named_dates_for_preview_survive_invalid_model_output(self):
        self.model.output = "JSON inválido"
        result = self.coach.respond("Preciso jogar o treino de quarta na quinta só nesta semana. "
                                   "Só prepara a prévia pra eu conferir.", reference_date=self.today)
        action, = result["actions"]
        self.assertEqual(action["status"], "pending_user_confirmation")
        self.assertEqual(action["payload"]["source_date"], "2026-11-11")
        self.assertEqual(action["payload"]["target_date"], "2026-11-12")

    def test_workout_calendar_reads_count_and_restored_day(self):
        result = self.send("Quantos dias de treino minha ficha tem na semana?", op="week", day="hoje")
        self.assertIn("1 dia de treino", result["answer"])
        result = self.send("O que aparece na quarta depois de desfazer?", op="move_workout",
                           day="quarta", destination="quinta", purpose="apply")
        self.assertIn("Quarta (11/11): Inferiores.", result["answer"])
        self.assertEqual(result["actions"], [])

    def test_uses_trusted_amounts_and_order_of_previously_mentioned_meals(self):
        snapshot = self.coach.action_session.snapshot
        dinner = snapshot.meal_items[0]
        dinner.update(amount="85 g", approved_replacement_portions=[{"food_id": uid(7), "amount": "110 g"}])
        snapshot.meal_items.append({**dinner, "id": uid(8), "meal_name": "Almoço",
                                    "meal_position": 1, "amount": "65 g", "approved_replacement_portions": []})
        read = self.send("Tem salmão no jantar e no almoço?", op="food_options", item="salmão")
        self.assertIn("Jantar e Almoço", read["answer"])
        self.send("A entrega chega amanhã cedo.", op="chat")
        read = self.send("Na primeira refeição, repete a quantidade e a opção cadastrada.",
                         op="diet", meal="primeira refeição")
        self.assertIn("Salmão (85 g)", read["answer"])
        self.assertIn("Peito de frango (110 g)", read["answer"])
        self.assertNotIn("65 g", read["answer"])
        self.assertEqual(read["actions"], [])

    def test_recalls_time_constraint_from_transcript_instead_of_model_safety_guess(self):
        self.send("Antes de sair, preciso guardar minha chave.", op="chat")
        self.send("Meu tempo está curto: vou buscar minha irmã.", op="chat")
        recalled = self.send("O que eu disse que encurtou meu tempo?", op="safety")
        self.assertIn("vou buscar minha irmã", recalled["answer"])
        self.assertEqual(recalled["actions"], [])

    def test_exercise_while_deciding_has_no_proposal_then_resolves_a_named_option(self):
        snapshot = self.coach.action_session.snapshot
        snapshot.exercises = [
            {"id": uid(12), "canonical": "Subida no banco"},
            {"id": uid(13), "canonical": "Subida no banco com halteres"},
        ]
        read = self.send("Queria ver uma troca para Subida no banco no treino de quarta. Ainda tô decidindo.",
                         op="replace_exercise", item="Subida no banco", replacement="outro")
        self.assertEqual(read["actions"], [])
        reply = self.send("Escolhi Subida no banco com halteres. Prepara a prévia dessa troca.", op="unclear")
        action, = reply["actions"]
        self.assertEqual(action["status"], "pending_user_confirmation")
        self.assertEqual(action["payload"]["workout_day_exercise_id"], uid(5))
        self.assertEqual(action["payload"]["replacement_exercise_id"], uid(13))

    def test_long_quote_is_irrelevant_for_read_only_preview_request(self):
        for purpose in ("preview", "apply"):
            reply = self.send("Quero ver a prévia de trocar salmão por frango no jantar.",
                              op="replace_food", item="salmão", replacement="frango",
                              purpose=purpose, request_evidence="citação " * 40)
            self.assertEqual(reply["actions"][0]["status"], "pending_user_confirmation")

    def test_effect_question_about_colloquial_move_stays_read_only(self):
        text = "Preciso jogar o treino de quarta na quinta. O que aconteceria se fosse só nesta semana?"
        reply = self.send(text, op="move_workout", day="quarta", destination="quinta",
                          purpose="apply", request_evidence=text)
        self.assertEqual(reply["actions"], [])
