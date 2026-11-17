"""Conversational composition and typed proposals; database writes remain in the backend."""
from datetime import date
import io
import os
import re
from pathlib import Path
from .account_context import account_reply, memory_request, training_goal_reply
from .actions import ActionSession
from .safety import preflight, output_guard, execution_boundary_reply
from .request_intent import (
    asks_to_resume_swap, change_scope, change_inquiry_reply, discusses_swap_impact, explicit_change,
    is_plan_inquiry, meal_qualifiers, read_swap,
)
from .clarification import clarify, plan_preference_reply, proposal_failure, frame
from .grounding import NO_SUPPORT, PARTIAL, select_grounded_answer
from .plan_read import exercise_history_reply, plan_catalogue_reply
from .reviewed_questions import evidence_gap_reply, reviewed_questions, specific_gap
from .conversation_facts import Continuation, logistics_report, observe_report, read_followup, safe_storage_turn
from .dialogue import (ConversationMemory, DialogueContext, playful_aside, resumes_hydration, resumes_topic,
                       topic_reference, training_goal, training_routine)
from .retrieval import dependent, explicit_switch, fold, tokens
from .retrieval_hydration import (
    daily_hydration_guidance, hydration_detail, hydration_quantity_followup, hydration_training_followup,
    is_daily_hydration_request,
)
from .smalltalk import (
    CLARIFY_REPLIES, clear_knowledge_question, conversational_reply, explicit_information_request, is_statement,
    report_followup, varied_reply, wants_information,
)
from .training_questions import (
    EXERCISE_QUESTION, EXERCISE_REFERENCE, answer_deload, complete_exercise_question,
    deload_discussion, plan_exercise,
)
from .turn_context import context_payload, interpret_turn
from .conversation_writer import write_conversation, trim_history

EDUCATIONAL = {"ask_training_concept", "ask_exercise_execution", "ask_nutrition_concept",
               "ask_recovery", "ask_sleep_habits", "ask_hydration", "ask_training_meal_timing",
               "ask_cardio_training", "ask_cooking_guidance", "ask_food_substitution_options",
               "ask_meal_feedback", "ask_sports_conditioning", "ask_food_safety", "ask_supplements",
               "ask_training_program_feedback", "ask_weight_management"}


class MemoryOnlyEncoder:
    """Preserve the legacy feature encoder but redirect its NPZ writes to memory."""
    def __init__(self, encoder):
        self.encoder = encoder

    def encode(self, texts, **kwargs):
        self.encoder.cache_path = io.BytesIO()
        return self.encoder.encode(texts, **kwargs)


class LocalLM:
    def __init__(self, ai_root, *, adapted=False):
        from evolv_openlm.runtime import load_model, load_settings, DEFAULT_CACHE
        self.settings = load_settings()
        checkpoint = None
        if adapted:
            from evolv_openlm.comparison import verify_inputs
            checkpoint, _ = verify_inputs(ai_root, ai_root / "artifacts/openlm_training/1.0.0", DEFAULT_CACHE)
        self.model, self.tokenizer = load_model(self.settings, download=False)
        if adapted:
            from peft import PeftModel, prepare_model_for_kbit_training
            self.model = prepare_model_for_kbit_training(self.model, use_gradient_checkpointing=False)
            self.model = PeftModel.from_pretrained(self.model, str(checkpoint),
                                                  is_trainable=False, local_files_only=True)
            self.model.eval()
        self.model.config.use_cache = True
        self.variant = "adapted_research" if adapted else "original"
        self.context_router_enabled = os.environ.get("EVOLV_AI_CONTEXT_ROUTER", "false").lower() == "true"

    def count(self, messages):
        encoded = self.tokenizer.apply_chat_template(messages, tokenize=True,
            add_generation_prompt=True, return_tensors="pt", return_dict=True)
        return encoded["input_ids"].shape[-1]

    def generate(self, messages):
        from evolv_openlm.runtime import answer
        budget = min(24, self.settings["max_new_tokens"])
        return answer(self.model, self.tokenizer, messages, self.settings, max_new_tokens=budget)

    def interpret(self, messages):
        from evolv_openlm.runtime import answer
        return answer(self.model, self.tokenizer, messages, self.settings,
                      max_new_tokens=min(144, self.settings["max_new_tokens"]))["text"]

    def write(self, messages):
        from evolv_openlm.runtime import answer
        return answer(self.model, self.tokenizer, messages, self.settings)


class Coach:
    def __init__(self, nlp, search, lm=None, *, planner_snapshot=None, now=None):
        self.nlp, self.search, self.lm = nlp, search, lm
        self.history = []
        self.memory = ConversationMemory()
        self.action_session = ActionSession(planner_snapshot, now)
        self.router_draft = None

    @property
    def dialogue(self):
        return self.memory.active

    @property
    def interprets_context(self):
        return callable(getattr(self.lm, "interpret", None)) and getattr(self.lm, "context_router_enabled", True)

    def clear(self):
        self.history.clear()
        self.memory = ConversationMemory()
        self.action_session.clear()
        self.router_draft = None

    def _continue_hydration(self, text):
        current = self.dialogue if self.dialogue and self.dialogue.topic == "daily_hydration" else None
        saved = self.memory.latest("daily_hydration")
        if is_daily_hydration_request(text):
            return DialogueContext(topic="daily_hydration", anchor=text[:800],
                                   details=saved.details if saved else [])
        if resumes_hydration(text):
            return saved
        if current and hydration_detail(text):
            return current.with_detail(text)
        if current and (resumes_topic(text) or hydration_quantity_followup(text)):
            return current
        return None

    def _answer_with_sources(self, clean, today, result, *, turn_context=None, plan_fact=None):
        history = self.history
        prior_users = [m["content"] for m in history[-4:] if m["role"] == "user"]
        if (self.dialogue and dependent(clean) and not explicit_switch(clean) and prior_users
                and (playful_aside(prior_users[-1]) or conversational_reply(prior_users[-1]))):
            history = [{"role": "user", "content": self.dialogue.anchor}]
            prior_users = [self.dialogue.anchor]
        contextual_search = getattr(self.search, "query_conversation", None)
        reviewed = ([match for doc in reviewed_questions(clean)
                     if (match := self.search.reviewed_document(doc, as_of=today))]
                    if plan_fact and hasattr(self.search, "reviewed_document") else [])
        if reviewed:
            retrieved = {"status": "found", "matches": reviewed, "method": "reviewed_document"}
            use_previous = False
        elif contextual_search:
            retrieved = contextual_search(clean, history[-16:], as_of=today)
            use_previous = retrieved.get("context", {}).get("used", False)
        else:
            use_previous = len(clean.split()) < 8
            query = "\n".join(prior_users[-1:] + [clean]) if use_previous else clean
            retrieved = self.search.query(query, as_of=today)
        previous = prior_users[-1] if use_previous and prior_users else None
        result["retrieval"] = retrieved
        if self.lm is None and retrieved["matches"]:
            return "Fontes localizadas; geração desativada nesta execução de análise."

        grounded = self._select_sources(clean, previous, retrieved, turn_context, plan_fact)
        retry_attempted = False
        if contextual_search and self.lm is not None and (
                grounded is None or grounded.status in {"insufficient", "invalid_selection"}):
            # Try a standalone search, with conversational filler removed from the query.
            # The selector still sees the original wording, including any qualifiers.
            keywords = tokens(clean)
            retry_query = clean if use_previous else " ".join(keywords)
            if len(keywords) >= 3 and (use_previous or retry_query.casefold() != clean.casefold()):
                retry_attempted = True
                alternate = self.search.query(retry_query, as_of=today)
                first_ids = {row["id"] for row in retrieved["matches"]}
                alternate["matches"] = [row for row in alternate["matches"] if row["id"] not in first_ids]
                retry = self._select_sources(clean, previous, alternate, turn_context, plan_fact)
                if retry and retry.status in {"supported_excerpt", "partial"}:
                    grounded, retrieved = retry, alternate
                    result["retrieval"] = retrieved

        if grounded is None:
            result["grounding"] = {"status": "no_evidence", "retry_attempted": retry_attempted}
            return evidence_gap_reply(clean, NO_SUPPORT)
        result["retrieval"]["matches"] = grounded.matches
        result["generation"] = grounded.generation
        result["grounding"] = {"status": grounded.status, "method": "source_excerpt",
                               "retry_attempted": retry_attempted}
        if output_guard(grounded.text, [row["id"] for row in grounded.matches]):
            result["grounding"]["status"] = "blocked"
            result["safety"]["generated_output_blocked"] = True
            return evidence_gap_reply(clean, NO_SUPPORT)
        if grounded.status in {"insufficient", "invalid_selection"}:
            return evidence_gap_reply(clean, grounded.text)
        return grounded.text

    def _answer_reviewed(self, documents, question, today, result, *, answer=None):
        matches = [match for doc in documents if (match := self.search.reviewed_document(doc, as_of=today))]
        return self._render_reviewed(matches, documents, question, result, answer=answer)

    def _render_reviewed(self, matches, documents, question, result, *, answer=None):
        if not matches:
            result["grounding"] = {"status": "no_evidence", "method": "reviewed_guidance"}
            return evidence_gap_reply(question, "Não tenho uma fonte revisada para responder a esse ponto agora.")
        partial = len(matches) < len(documents)
        result["retrieval"] = {"status": "found", "matches": matches, "method": "reviewed_document"}
        result["grounding"] = {"status": "partial" if partial else "supported_excerpt", "method": "reviewed_guidance"}
        passages = [f"{match['generation_context']['text']} [{match['id']}]" for match in matches]
        if answer is not None and len(matches) == 1 and not partial:
            passages = [f"{answer} [{matches[0]['id']}]"]
        if documents == ("hydration_is_individual",) and re.search(r"\b(?:todo mundo|todas as pessoas)\b", fold(question)):
            passages[0] = "Não. " + passages[0]
        if partial:
            passages.append(PARTIAL)
        reply = "\n\n".join(passages)
        if output_guard(reply, [match["id"] for match in matches]):
            result["grounding"]["status"] = "blocked"
            result["safety"]["generated_output_blocked"] = True
            return evidence_gap_reply(question, NO_SUPPORT)
        return reply

    def _answer_continuation(self, continuation, today, result):
        if continuation.document is None:
            return continuation.answer
        documents = (continuation.document,)
        if hasattr(self.search, "reviewed_document"):
            return self._answer_reviewed(documents, continuation.query, today, result, answer=continuation.answer)
        retrieved = self.search.query(continuation.query, as_of=today)
        matches = [row for row in retrieved["matches"] if row.get("document_id") == continuation.document]
        return self._render_reviewed(matches[:1], documents, continuation.query, result, answer=continuation.answer)

    def _select_sources(self, text, previous, retrieved, turn_context=None, plan_fact=None):
        if retrieved["matches"]:
            return select_grounded_answer(self.lm, text, previous, retrieved["matches"],
                                          turn_context=turn_context, plan_fact=plan_fact)
        return None

    def _plan_and_knowledge(self, text, today, account_day, focus):
        """Resolve the plan half of two explicit, independent questions."""
        start = r"(?:qual|quais|quantas?|quantos?|como|o que|oq|por que|pra que)\b"
        parts = re.split(rf"(?:\?\s+(?:e\s+)?|\s+e\s+)(?={start})", text, flags=re.I)
        if len(parts) != 2:
            return None
        snapshot = self.action_session.snapshot
        answers = []
        for part in parts:
            current = fold(part)
            answer = None
            if re.search(r"\b(?:ficha|meu treino|minha dieta|meu plano|de hoje)\b", current):
                answer = plan_catalogue_reply(part, snapshot, today, account_day)
                if not answer and re.search(r"\b(?:quantas?|quais?) (?:reps|repeticoes)\b", current):
                    answer, _ = plan_exercise(part, snapshot, today, focus, account_day)
            answers.append(answer)
        if bool(answers[0]) == bool(answers[1]):
            return None
        index = 0 if answers[0] else 1
        return answers[index], parts[1 - index]

    def _interpretation(self, text):
        from dataclasses import replace

        history = self.history
        previous = next((row["content"] for row in reversed(history) if row["role"] == "user"), "")
        swap = read_swap(previous) if previous and not preflight(previous) else None
        pending_request = ({"sai": swap.old, "entra": swap.new, "refeicoes": sorted(swap.meals),
                            "consulta": swap.inquiry} if swap else None)
        context = context_payload(history, self.memory, self.action_session.snapshot,
                                  self.action_session.pending, pending_request)
        suggestion = interpret_turn(self.lm, text, context)
        if not suggestion:
            return None, context
        kind, value = suggestion
        if kind == "troca":
            # The model can recognize a continuation, but only an explicit request or a
            # meal supplied in response to a pending explicit request may create a proposal.
            if swap and asks_to_resume_swap(text):
                return (kind, swap), context
            named = meal_qualifiers(text)
            asked_for_meal = history and "em qual refeicao" in fold(history[-1]["content"])
            slot_reply = fold(text).strip(" .!").removeprefix("so ")
            if (swap and not swap.inquiry and not swap.meals and asked_for_meal and len(named) == 1
                    and re.fullmatch(r"(?:n[oa]|d[oa]) [\w ]+", slot_reply)
                    and slot_reply.split(" ", 1)[1] in named):
                return (kind, replace(swap, meals=frozenset(named))), context
            return None, context
        return (kind, value), context

    def _respond_to_interpretation(self, clean, today, product_today, account_day, result):
        suggestion, context = self._interpretation(clean)
        if not suggestion:
            return None
        kind, value = suggestion
        analysis = result["analysis"]
        reply = None
        if (kind == "papo" and "?" not in clean and not wants_information(clean)
                and not context["pedido_de_troca"] and not context["proposta_pendente"]):
            analysis["route"] = "conversation"
            reply = value
        elif kind == "lembrar" and re.search(r"\b(?:falei|disse|comentei|lembra\w*|mencionei)\b", fold(clean)):
            analysis["route"] = "answer"
            reply = f"Você disse: “{value}”"
        elif kind == "troca":
            resolved = self.action_session.resolve_food_swap(value, product_today, account_day, requested=True)
            if resolved:
                reply, proposal = resolved
                analysis["route"] = "draft_for_confirmation" if proposal else "answer"
                if proposal:
                    analysis["proposal_basis"] = "contextual_meal_swap_with_explicit_request"
                    result["actions"] = [proposal]
        elif kind == "pergunta":
            snapshot = self.action_session.snapshot
            reply = plan_catalogue_reply(value, snapshot, product_today, account_day)
            if not reply:
                reply, exercise = plan_exercise(value, snapshot, product_today, account_day=account_day)
                if exercise:
                    self.memory = self.memory.recording("workout_exercise", clean, {"exercise": exercise})
            if not reply:
                followup = read_followup(self.memory, value)
                if followup:
                    reply = self._answer_continuation(followup, today, result)
                elif hasattr(self.search, "reviewed_document") and (documents := reviewed_questions(value)):
                    reply = self._answer_reviewed(documents, value, today, result)
                else:
                    reply = self._answer_with_sources(value, today, result, turn_context=context)
            analysis["route"] = "answer"
        if reply:
            analysis["context_interpretation"] = kind
        return reply

    def respond(self, text, *, reference_date=None, proposal_id=None, account=None, recalled=None):
        from evolv_nlp.privacy import review_text
        if not isinstance(text, str) or not text.strip() or len(text) > 8000:
            raise ValueError("Mensagem deve ter entre 1 e 8000 caracteres.")
        today = reference_date or date.today()
        account_day = account.day if account else None
        product_today = account_day.date if account_day else today
        clean = review_text(text).minimized_text[:8000]
        prior_user_messages = [m for m in self.history[-4:] if m["role"] == "user"]
        context = "\n".join(m["content"] for m in prior_user_messages)[-16000:]
        recent_replies = [m["content"] for m in self.history[-8:] if m["role"] == "assistant"]
        # Risk checks are local and retain only labels. Masked text goes to the models.
        guard = preflight(text, prior_user_messages)
        if self.nlp is None:
            from .qwen_router import respond
            analysis = {"route": "answer", "intent": {"label": "qwen", "confident": False},
                        "risk": {"labels": guard["risks"] if guard else []}, "entities": {"entities": []},
                        "interpreter": "qwen"}
            result = self._result(analysis, guard)
            if guard:
                self.action_session.clear()
                self.router_draft = None
                analysis["route"] = guard["route"]
                reply = guard["answer"]
            elif proposal_id is not None:
                reply = self._review_proposal(clean, proposal_id, result)
            else:
                reply = respond(self, clean, product_today, account, recalled, result)
            return self._finish(result, clean, reply, guard)
        memory_item = None
        social = None
        prior_followup = read_followup(self.memory, clean) if guard is None and proposal_id is None else None
        documents = ()
        catalogue_reply = None
        gap = None
        if guard is None and proposal_id is None:
            scope = change_scope(clean)
            if scope in {None, "inquiry"}:
                catalogue_reply = plan_catalogue_reply(clean, self.action_session.snapshot, product_today, account_day)
                gap = specific_gap(clean)
                if hasattr(self.search, "reviewed_document"):
                    documents = reviewed_questions(clean)
            memory = memory_request(clean, account) if account and recalled is None else None
            saved_reply = (account_reply(clean, account)
                           if account and memory is None and recalled is None and not prior_followup else None)
            logged = (exercise_history_reply(clean, account, self.action_session.snapshot)
                      if account and not memory and not catalogue_reply else None)
            if logged:
                social = ("account_exercise_history", logged)
            elif recalled is not None and prior_followup is None and not catalogue_reply:
                excerpts = [review_text(excerpt).minimized_text for excerpt in recalled]
                reply = ("Nesta conversa, você me disse " + " ".join(f"“{excerpt}”" for excerpt in excerpts)
                         if excerpts else "Procurei no histórico desta conversa e não achei uma mensagem sobre isso.")
                social = ("conversation_recall", reply)
            elif memory:
                reply, memory_item = memory
                social = ("account_memory", reply)
            elif saved_reply:
                social = ("account_information", saved_reply)
            else:
                social = conversational_reply(clean, recent_replies)
        if guard:
            analysis = {"route": guard["route"], "intent": {"label": "guarded", "confident": False},
                        "risk": {"labels": guard["risks"]}, "entities": {"entities": []}}
            self.action_session.clear()
        elif social:
            analysis = {"route": "conversation", "intent": {"label": social[0], "confident": True},
                        "risk": {"labels": []}, "entities": {"entities": []}}
        else:
            analysis = self.nlp.analyze(clean, context=context, reference_date=today, pending_action=None)
            # A restriction about transport, storage or timing can inherit a weak risk from older text.
            # Recheck the actual message while keeping rule matches and urgent labels authoritative.
            risks = set(analysis["risk"]["labels"])
            if (context and proposal_id is None and (logistics_report(clean) or prior_followup)
                    and risks and risks <= {"under_recovery_signal", "food_safety_uncertainty"}
                    and not analysis["risk"].get("rules", {}).get("risks")):
                current = self.nlp.analyze(clean, context="", reference_date=today, pending_action=None)
                if not current["risk"]["labels"]:
                    analysis = current
            # Packaging and storage logistics can look like unsafe-food reports to the classifier.
            # Use the narrow, read-only handler when no safety rule or other risk agrees.
            risk = analysis["risk"]
            if (proposal_id is None and risk["labels"] == ["food_safety_uncertainty"]
                    and not risk.get("rules", {}).get("risks")
                    and safe_storage_turn(self.memory, clean, prior_followup)):
                analysis = {**analysis, "route": "answer",
                            "risk": {**risk, "labels": [], "routing_basis": "storage_logistics"}}
            # A read-only catalogue query and a general sleep question can look like risk to the model.
            # Restrict the exception to those cases and retain independent rules and critical labels.
            risk = analysis["risk"]
            folded = fold(clean)
            general_sleep = (documents == ("sleep_recovery_explanation",)
                             and not re.search(r"\b(?:meu|minha|eu|estou|tenho|sinto|nao consigo|ins[oô]nia)\b", folded))
            if (proposal_id is None and not risk.get("rules", {}).get("risks")
                    and ((general_sleep and risk["labels"] == ["under_recovery_signal"])
                         or (catalogue_reply and risk["labels"] == ["food_safety_uncertainty"]))):
                analysis = {**analysis, "route": "answer",
                            "risk": {**risk, "labels": [], "routing_basis": "verified_read_only_question"}}
        route = analysis["route"]
        conversational_statement = (is_statement(clean) and not explicit_change(clean)
                                    and proposal_id is None and not analysis["risk"]["labels"])
        if conversational_statement and callable(getattr(self.lm, "write", None)):
            analysis["route"] = route = "conversation"
        can_route = (guard is None and not analysis["risk"]["labels"] and proposal_id is None and social is None
                     and route not in {"urgent_referral", "crisis_referral", "safety_information_only"})
        scope = change_scope(clean) if can_route else None
        plan_review = plan_preference_reply(clean, self.action_session.snapshot) if can_route else None
        execution_boundary = execution_boundary_reply(clean) if can_route else None
        food_swap = None
        if can_route and not execution_boundary:
            resume_swap = asks_to_resume_swap(clean)
            impact = discusses_swap_impact(clean)
            swap = read_swap(clean)
            if (resume_swap or impact) and prior_user_messages:
                previous = prior_user_messages[-1]["content"]
                if resume_swap and discusses_swap_impact(previous) and len(prior_user_messages) > 1:
                    previous = prior_user_messages[-2]["content"]
                if not preflight(previous, []):
                    swap = read_swap(previous)
            if swap:
                food_swap = self.action_session.resolve_food_swap(
                    swap, product_today, account_day, requested=resume_swap or not swap.inquiry and not impact,
                )
        old_memory = self.memory
        if can_route and scope is None and not execution_boundary:
            self.memory = observe_report(self.memory, clean)
        remembered_report = self.memory != old_memory
        continuation = ((read_followup(self.memory, clean) if remembered_report else prior_followup)
                        if can_route else None)
        if (can_route and self.dialogue and self.dialogue.topic == "daily_hydration"
                and hydration_training_followup(clean)):
            continuation = Continuation(query="Hidratação durante exercício em dia quente suor ingestão de água",
                                        document="hydration_is_individual")
        resumed_swap = self.action_session.complete_swap(analysis) if can_route and not execution_boundary and not food_swap else None
        if not can_route or execution_boundary or food_swap:
            self.action_session.incomplete_swap = None
        may_continue = (not analysis["risk"]["labels"] and guard is None and proposal_id is None
                        and route in {"answer", "clarify"})
        hydration = self._continue_hydration(clean) if may_continue else None
        resume = may_continue and (resumes_topic(clean) or resumes_hydration(clean))
        routine = (self.dialogue and self.dialogue.topic == "training_goal" and may_continue
                   and training_routine(clean) and is_statement(clean))
        knowledge_fallback = (can_route and route in {"clarify", "draft_for_confirmation"} and hydration is None
                              and (clear_knowledge_question(clean)
                                   or (scope is None and explicit_information_request(clean))
                                   or (route == "clarify" and analysis["intent"]["label"] in EDUCATIONAL
                                       and wants_information(clean))))
        followup = (report_followup(clean) if can_route and scope is None and not knowledge_fallback
                    and route in {"answer", "clarify", "draft_for_confirmation", "conversation"} else None)
        result = self._result(analysis, guard)
        result["knowledge_only_fallback"] = knowledge_fallback
        training_reply, exercise = None, None
        focus = (self.dialogue.facts.get("exercise")
                 if self.dialogue and self.dialogue.topic == "workout_exercise" and not explicit_switch(clean) else None)
        combined = (self._plan_and_knowledge(clean, product_today, account_day, focus)
                    if can_route and scope is None and not explicit_change(clean)
                    and self.lm is not None and wants_information(clean) else None)
        completed_question = (complete_exercise_question(clean, self.history, self.action_session.snapshot)
                              if can_route and scope is None else None)
        if (can_route and scope is None and not any((combined, resumed_swap, food_swap, execution_boundary,
                                                   catalogue_reply, documents, gap))
                and route in {
                    "answer", "clarify", "draft_for_confirmation"
                }):
            training_reply, exercise = plan_exercise(clean, self.action_session.snapshot, product_today, focus, account_day)
            if not training_reply and deload_discussion(clean, self.dialogue):
                training_reply = answer_deload(clean, self.search, today, result)
        if guard:
            reply = guard["answer"]
        elif social:
            reply = social[1]
            if social[0] in {"greeting", "conversation_check_in", "conversation_opening", "acknowledgment"}:
                reply = write_conversation(self.lm, self.history, clean, account) or reply
            elif social[0] == "account_information" and self.history:
                reply = write_conversation(self.lm, self.history, clean, account) or reply
        elif analysis["risk"]["labels"] or route in {"urgent_referral", "crisis_referral", "safety_information_only"}:
            self.action_session.clear()
            reply = ("Não consigo avaliar ou diagnosticar isso pela conversa. Procure avaliação "
                     "profissional; diante de risco imediato, procure atendimento de emergência.")
        elif proposal_id is not None:
            reply = self._review_proposal(clean, proposal_id, result)
        elif execution_boundary:
            analysis["route"] = "conversation"
            reply = execution_boundary
        elif food_swap:
            reply, proposal = food_swap
            analysis["route"] = "draft_for_confirmation" if proposal else "answer"
            if proposal:
                analysis["proposal_basis"] = "plan_catalogue_food_swap"
                result["actions"] = [proposal]
        elif scope in {"negated", "hypothetical", "compound"}:
            analysis["route"] = "clarify"
            question = {
                "negated": "Certo, vou manter seu plano como está.",
                "hypothetical": "Posso conversar sobre essa possibilidade. Seu plano continua como está.",
                "compound": "Qual dessas mudanças você quer revisar primeiro? Seu plano continua como está.",
            }[scope]
            result["clarification"] = frame("scope_or_negation", analysis["intent"]["label"], [], question)
            reply = question
        elif resumed_swap:
            analysis["route"] = "draft_for_confirmation"
            analysis["proposal_basis"] = "clarification_completed"
            result["actions"] = [resumed_swap]
            reply = "Agora identifiquei os dois itens. Abra a prévia para conferir antes de confirmar."
        elif combined:
            plan_reply, knowledge_question = combined
            analysis["route"] = "answer"
            if plan_reply.endswith("?"):
                analysis["route"] = "clarify"
                result["clarification"] = frame("plan_reference", analysis["intent"]["label"], [], plan_reply)
            source_reply = self._answer_with_sources(
                knowledge_question, today, result, plan_fact=plan_reply if not plan_reply.endswith("?") else None
            )
            reply = f"{plan_reply}\n\n{source_reply}"
        elif completed_question:
            analysis["route"] = "answer"
            reply, exercise = plan_exercise(completed_question, self.action_session.snapshot, product_today,
                                            account_day=account_day)
            if exercise:
                self.memory = self.memory.recording("workout_exercise", completed_question, {"exercise": exercise})
            if not reply:
                reply = self._answer_with_sources(completed_question, today, result)
        elif continuation and (not documents or continuation.document in {
            "sleep_recovery_explanation", "sleep_duration_adults",
        }):
            if continuation.clarify:
                analysis["route"] = "clarify"
                result["clarification"] = frame("context_missing_detail", analysis["intent"]["label"], [], continuation.answer)
            else:
                analysis["route"] = "answer"
            reply = self._answer_continuation(continuation, today, result)
            if (continuation.document in {"sets_repetitions_plain", "rest_between_sets_context"}
                    and any(row.get("document_id") == continuation.document for row in result["retrieval"]["matches"])):
                self.memory = self.memory.remembering(DialogueContext(
                    topic="knowledge", anchor=continuation.query, facts={"document": continuation.document}
                ))
        elif catalogue_reply:
            analysis["route"] = "answer"
            reply = catalogue_reply
        elif documents:
            analysis["route"] = "answer"
            reply = self._answer_reviewed(documents, clean, today, result)
            if result["grounding"]["status"] == "supported_excerpt":
                self.memory = self.memory.remembering(DialogueContext(
                    topic="knowledge", anchor=clean[:800], facts={"document": documents[0]}
                ))
        elif gap:
            analysis["route"] = "clarify"
            result["clarification"] = frame("evidence_gap", analysis["intent"]["label"], [], gap)
            reply = gap
        elif scope == "inquiry" and is_plan_inquiry(clean):
            analysis["route"] = "answer"
            reply = change_inquiry_reply(analysis, self.action_session.snapshot, product_today, account_day)
        elif training_reply:
            analysis["route"] = "answer"
            reply = training_reply
            if exercise:
                self.memory = self.memory.recording("workout_exercise", clean, {"exercise": exercise})
            elif not self.dialogue or "deload" in clean.lower() or result["retrieval"]["status"] == "not_requested":
                self.memory = self.memory.remembering(DialogueContext(topic="knowledge", anchor=clean[:800]))
        elif plan_review:
            analysis["route"] = "conversation"
            reply = plan_review
            if re.search(r"\bbiceps\b", fold(clean)):
                self.memory = self.memory.recording("training_review", clean, {"focus": "bíceps"})
        elif hydration:
            reply, evidence = daily_hydration_guidance(
                clean, hydration.details, resuming=resume)
            result["retrieval"] = {"status": "found", "matches": [evidence]}
            result["grounding"] = {"status": "supported_excerpt", "method": "reviewed_guidance"}
            analysis["route"] = "answer"
            self.memory = self.memory.remembering(hydration)
        elif resume:
            analysis["route"] = "conversation"
            if resumes_hydration(clean):
                reply = "Claro. O que você quer entender sobre hidratação?"
            elif self.dialogue:
                reply = f"Claro, vamos voltar ao que você trouxe: “{self.dialogue.anchor}”. O que você quer explorar agora?"
            else:
                reply = "Claro. Qual assunto você quer retomar?"
        elif may_continue and is_statement(clean) and playful_aside(clean):
            analysis["route"] = "conversation"
            reply = (f"Haha, boa. Voltamos a falar sobre {topic_reference(self.dialogue)}?"
                     if self.dialogue else "Haha, boa. Me conta o que você tem em mente hoje.")
        elif routine:
            analysis["route"] = "conversation"
            self.memory = self.memory.remembering(self.dialogue.with_detail(clean))
            reply = ("Entendi como você treina hoje. Pensando no seu objetivo, tem algum exercício "
                     "em que você quer progredir primeiro?")
        elif (can_route and scope in {None, "inquiry"} and not explicit_change(clean)
              and route != "request_text_description" and self.interprets_context
              and (interpreted := self._respond_to_interpretation(clean, today, product_today, account_day, result))):
            reply = interpreted
        elif (can_route and scope is None and wants_information(clean) and not focus
              and EXERCISE_REFERENCE.search(clean)):
            analysis["route"] = "clarify"
            reply = EXERCISE_QUESTION
            result["clarification"] = frame("plan_reference", analysis["intent"]["label"], ["exercise"], reply)
        elif (can_route and not explicit_change(clean) and scope is None
              and not self.action_session.pending
              and route in {"conversation", "clarify", "answer"}
              and (conversational_statement or (route == "clarify" and not wants_information(clean)))
              and (written := write_conversation(self.lm, self.history, clean, account,
                                                self.action_session.snapshot))):
            analysis["route"] = "conversation"
            reply = written
        elif followup or remembered_report:
            analysis["route"] = "conversation"
            reply = followup or "Entendi. Vou considerar esse detalhe aqui na conversa."
            if training_goal(clean):
                self.memory = self.memory.remembering(DialogueContext(topic="training_goal", anchor=clean[:800]))
                if account:
                    reply = training_goal_reply(account) or reply
        elif route == "draft_for_confirmation" and not knowledge_fallback:
            question = clarify(analysis, clean, self.action_session.snapshot)
            if question:
                result["clarification"] = question
                reply = question["answer"]
            else:
                try:
                    proposal = self.action_session.propose(analysis)
                    result["actions"] = [proposal]
                    reply = "Preparei a proposta. Abra a prévia para conferir o que muda antes de confirmar."
                except ValueError as exc:
                    result["clarification"] = proposal_failure(analysis, exc)
                    reply = result["clarification"]["answer"]
        elif route == "request_text_description":
            reply = "Descreva a imagem em texto para eu entender sua pergunta."
        elif route in {"clarify", "clarify_pending_action", "review_pending_action"} and not knowledge_fallback:
            swap = self.action_session.propose_explicit_swap(analysis)
            if swap:
                analysis["route"] = "draft_for_confirmation"
                analysis["proposal_basis"] = "explicit_swap_with_plan_targets"
                result["actions"] = [swap]
                reply = "Identifiquei os itens da troca. Abra a prévia para conferir antes de confirmar."
            elif route in {"clarify_pending_action", "review_pending_action"}:
                result["clarification"] = frame("proposal_id_required", analysis["intent"]["label"], [],
                    "Para confirmar ou recusar, use os botões da proposta nesta conversa. Se não houver uma proposta válida, peça uma nova alteração.")
                reply = result["clarification"]["answer"]
            else:
                question = (f"Isso tem a ver com {topic_reference(self.dialogue)} ou você quer mudar de assunto?"
                            if self.dialogue else varied_reply(CLARIFY_REPLIES, recent_replies))
                result["clarification"] = clarify(analysis, clean, self.action_session.snapshot, default_question=question)
                if result["clarification"] is None:
                    result["clarification"] = frame("intent_uncertain", analysis["intent"]["label"], [], question)
                reply = result["clarification"]["answer"]
        elif analysis["intent"]["label"] == "out_of_scope" and not knowledge_fallback:
            reply = "Posso ajudar com treino, alimentação e recuperação. Qual é sua dúvida nesses assuntos?"
        else:
            turn_context = (context_payload(self.history, self.memory, self.action_session.snapshot,
                                            self.action_session.pending)
                            if self.interprets_context else None)
            reply = self._answer_with_sources(clean, today, result, turn_context=turn_context)
            retrieval_context = result["retrieval"].get("context", {})
            if (result.get("grounding", {}).get("status") in {"supported_excerpt", "partial"}
                    and (not self.dialogue or not dependent(clean)
                         or retrieval_context.get("reason") == "independent_new_subject")):
                self.memory = self.memory.remembering(DialogueContext(topic="knowledge", anchor=clean[:800]))
        if result["clarification"] is not None:
            self.action_session.remember_incomplete_swap(analysis, result["clarification"])
            if self.action_session.incomplete_swap is not None:
                question = result["clarification"]
                question.update(requires_complete_request=False, answer=question["question"])
                reply = question["answer"]
            result["clarification"]["original_route"] = analysis["route"]
            if analysis["route"] == "draft_for_confirmation":
                analysis["route"] = "clarify"
        if memory_item:
            result["memory_item"] = memory_item
        return self._finish(result, clean, reply, guard)

    @staticmethod
    def _result(analysis, guard):
        result = {"schema_version": "coach.1.2.0", "mode": "local_research",
                  "analysis": analysis, "retrieval": {"status": "not_requested", "matches": []},
                  "answer": "", "generation": None, "actions": [],
                  "planner": {"writes_allowed": False, "connected": False},
                  "privacy": {"history": "session_memory_only", "automatic_training": False},
                  "history_turns_dropped": 0}
        result["clarification"] = None
        result["safety"] = {"preflight_route": guard["route"] if guard else None,
                            "generated_output_blocked": False}
        return result

    def _review_proposal(self, clean, proposal_id, result):
        from evolv_nlp.entities import normalize_text
        decision_text = normalize_text(clean).strip(" .!")
        decision_text = " ".join(decision_text.split())
        if decision_text in {"sim", "confirmo", "pode confirmar", "confirmar",
                             "confirmo a proposta", "confirmo essa proposta"}:
            decision = "confirm"
        elif (decision_text in {"nao", "rejeito", "cancelar", "cancela", "deixa quieto",
                                "prefiro manter como esta", "deixa quieto prefiro manter como esta"}
              or (self.nlp is None and re.search(
                  r"\bnao quero (?:mais )?(?:trocar|mudar|alterar|substituir)\b", decision_text
              )) or (self.nlp is None and "?" not in clean and re.match(
                  r"^(?:(?:pera|espera|pensando melhor)[, ]+)?(?:cancela|cancele|cancelar) "
                  r"(?:(?:o|esse) pedido|(?:a|essa) (?:troca|mudanca|proposta|previa))\b", decision_text
              ))):
            decision = "reject"
        else:
            decision = None
        try:
            if decision is None:
                raise ValueError("Confirme ou rejeite explicitamente a proposta.")
            proposal = self.action_session.transition(proposal_id, decision)
            result["actions"] = [proposal]
            reply = ("Autorização registrada para pedir a prévia ao Planner. O plano ainda não foi alterado."
                     if decision == "confirm" else "Proposta cancelada. Seu plano segue como estava.")
        except ValueError as exc:
            reply = str(exc)
        return reply

    def _finish(self, result, clean, reply, guard):
        result["answer"] = reply
        result["dialogue_context"] = self.memory.model_dump()
        supplied = {row["id"] for row in result["retrieval"]["matches"]}
        cited = set(re.findall(r"\[(kb:[^\]\s]+)\]", reply))
        result["citations"] = {"supplied_chunk_ids": sorted(supplied),
                               "cited_chunk_ids": sorted(cited),
                               "unknown_chunk_ids": sorted(cited - supplied),
                               "claim_faithfulness_verified": False}
        # In-memory, minimized inputs; bounded complete user/assistant pairs.
        user_turn = {"role": "user", "content": clean,
                     "critical_risks": guard.get("current_critical_risks", []) if guard else []}
        self.history.extend([user_turn, {"role": "assistant", "content": reply}])
        kept = trim_history(self.history, self.lm)
        result["history_turns_dropped"] = (len(self.history) - len(kept)) // 2
        self.history = kept
        return result


def load_nlp(ai_root: Path, version="1.8.0"):
    if version == "1.9.0":
        from evolv_nlp.recognition_pipeline import RecognitionPipeline
        return RecognitionPipeline(ai_root)
    if version != "1.8.0":
        raise ValueError("Invalid NLP version")
    from evolv_nlp.corrected_pipeline import CorrectedCoachPipeline
    nlp = CorrectedCoachPipeline(ai_root)
    if nlp.predictor.encoder is not None:
        nlp.predictor.encoder = MemoryOnlyEncoder(nlp.predictor.encoder)
    return nlp


def load_coach(ai_root: Path, *, generate=True, adapted=False, nlp_version="1.8.0",
               retrieval_version="1.1.2", interpreter="nlp"):
    from .retrieval_runtime import load_search
    if interpreter not in {"nlp", "qwen"} or (interpreter == "qwen" and not generate):
        raise ValueError("Qwen interpretation requires generation mode.")
    nlp = load_nlp(ai_root, nlp_version) if interpreter == "nlp" else None
    search = load_search(ai_root, retrieval_version)
    return Coach(nlp, search, LocalLM(ai_root, adapted=adapted) if generate else None)
