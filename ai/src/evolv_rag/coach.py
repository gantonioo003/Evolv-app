"""Research-only conversational composition. No Planner/database connection."""
from datetime import date
import io
import re
from pathlib import Path
from .actions import ActionSession
from .safety import preflight, output_guard
from .clarification import clarify, proposal_failure, frame
from .grounding import select_grounded_answer

EDUCATIONAL = {"ask_training_concept", "ask_exercise_execution", "ask_nutrition_concept",
               "ask_recovery", "ask_sleep_habits", "ask_hydration", "ask_training_meal_timing",
               "ask_cardio_training", "ask_cooking_guidance", "ask_food_substitution_options"}


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

    def count(self, messages):
        encoded = self.tokenizer.apply_chat_template(messages, tokenize=True,
            add_generation_prompt=True, return_tensors="pt", return_dict=True)
        return encoded["input_ids"].shape[-1]

    def generate(self, messages):
        from evolv_openlm.runtime import answer
        budget = min(24, self.settings["max_new_tokens"])
        return answer(self.model, self.tokenizer, messages, self.settings, max_new_tokens=budget)


class Coach:
    def __init__(self, nlp, search, lm=None, *, planner_snapshot=None, now=None):
        self.nlp, self.search, self.lm = nlp, search, lm
        self.history = []
        self.action_session = ActionSession(planner_snapshot, now)

    def clear(self):
        self.history.clear()
        self.action_session.clear()

    def respond(self, text, *, reference_date=None, proposal_id=None):
        from evolv_nlp.privacy import review_text
        if not isinstance(text, str) or not text.strip() or len(text) > 8000:
            raise ValueError("Mensagem deve ter entre 1 e 8000 caracteres.")
        today = reference_date or date.today()
        clean = review_text(text).minimized_text[:8000]
        context = "\n".join(m["content"] for m in self.history[-4:])[-16000:]
        prior_user_messages = [m for m in self.history[-4:] if m["role"] == "user"]
        # Risk checks are local and retain only labels. Masked text goes to the models.
        guard = preflight(text, prior_user_messages)
        if guard:
            analysis = {"route": guard["route"], "intent": {"label": "guarded", "confident": False},
                        "risk": {"labels": guard["risks"]}, "entities": {"entities": []}}
            self.action_session.clear()
        else:
            analysis = self.nlp.analyze(clean, context=context, reference_date=today, pending_action=None)
        route = analysis["route"]
        knowledge_fallback = (route == "clarify" and not analysis["risk"]["labels"]
                              and analysis["intent"]["label"] in EDUCATIONAL
                              and "?" in clean)
        result = {"schema_version": "coach.1.2.0", "mode": "local_research",
                  "analysis": analysis, "retrieval": {"status": "not_requested", "matches": []},
                  "answer": "", "generation": None, "actions": [],
                  "planner": {"writes_allowed": False, "connected": False},
                  "privacy": {"history": "session_memory_only", "automatic_training": False},
                  "history_turns_dropped": 0}
        result["clarification"] = None
        result["knowledge_only_fallback"] = knowledge_fallback
        result["safety"] = {"preflight_route": guard["route"] if guard else None,
                            "generated_output_blocked": False}
        if guard:
            reply = guard["answer"]
        elif analysis["risk"]["labels"] or route in {"urgent_referral", "crisis_referral", "safety_information_only"}:
            self.action_session.clear()
            reply = ("Não consigo avaliar ou diagnosticar isso pela conversa. Procure avaliação "
                     "profissional; diante de risco imediato, procure atendimento de emergência.")
        elif proposal_id is not None:
            from evolv_nlp.entities import normalize_text
            decision_text = normalize_text(clean).strip(" .!")
            if decision_text in {"sim", "confirmo", "pode confirmar", "confirmar"}:
                decision = "confirm"
            elif decision_text in {"nao", "rejeito", "cancelar", "cancela"}:
                decision = "reject"
            else:
                decision = None
            try:
                if decision is None:
                    raise ValueError("Confirme ou rejeite explicitamente a proposta.")
                proposal = self.action_session.transition(proposal_id, decision)
                result["actions"] = [proposal]
                reply = ("Autorização registrada para pedir a prévia ao Planner. O plano ainda não foi alterado."
                         if decision == "confirm" else "Proposta rejeitada. O plano não foi alterado.")
            except ValueError as exc:
                reply = str(exc)
        elif route in {"clarify_pending_action", "review_pending_action"}:
            result["clarification"] = frame("proposal_id_required", analysis["intent"]["label"], [],
                "Para confirmar ou recusar, use os botões da proposta nesta conversa. Se não houver uma proposta válida, peça uma nova alteração.")
            reply = result["clarification"]["answer"]
        elif route == "draft_for_confirmation":
            question = clarify(analysis, clean, self.action_session.snapshot)
            if question:
                result["clarification"] = question
                reply = question["answer"]
            else:
                try:
                    proposal = self.action_session.propose(analysis)
                    result["actions"] = [proposal]
                    reply = ("Proposta preparada para a prévia do Planner: " + proposal["payload"]["kind"] +
                             ". Confirme pelo identificador da proposta; nenhuma mudança foi aplicada.")
                except ValueError as exc:
                    result["clarification"] = proposal_failure(analysis, exc)
                    reply = result["clarification"]["answer"]
        elif route == "request_text_description":
            reply = "Descreva a imagem em texto para eu entender sua pergunta."
        elif route == "clarify" and not knowledge_fallback:
            result["clarification"] = clarify(analysis, clean, self.action_session.snapshot)
            if result["clarification"] is None:
                result["clarification"] = frame("intent_uncertain", analysis["intent"]["label"], [],
                    "Você quer tirar uma dúvida, registrar algo que já fez ou pedir uma alteração no plano?")
            reply = result["clarification"]["answer"]
        elif analysis["intent"]["label"] == "out_of_scope":
            reply = "Posso ajudar com treino, alimentação e recuperação. Qual é sua dúvida nesses assuntos?"
        else:
            prior_users = [m["content"] for m in self.history[-4:] if m["role"] == "user"]
            if hasattr(self.search, "query_conversation"):
                retrieved = self.search.query_conversation(clean, self.history, as_of=today)
                use_previous = retrieved.get("context", {}).get("used", False)
            else:
                use_previous = len(clean.split()) < 8
                query = "\n".join(prior_users[-1:] + [clean]) if use_previous else clean
                retrieved = self.search.query(query, as_of=today)
            result["retrieval"] = retrieved
            if not retrieved["matches"]:
                reply = "Não encontrei na base um trecho que responda a essa pergunta."
                result["grounding"] = {"status": "no_evidence"}
            elif self.lm is None:
                reply = "Fontes localizadas; geração desativada nesta execução de análise."
            else:
                previous = prior_users[-1] if use_previous and prior_users else None
                grounded = select_grounded_answer(self.lm, clean, previous, retrieved["matches"])
                reply = grounded.text
                result["retrieval"]["matches"] = grounded.matches
                result["generation"] = grounded.generation
                result["grounding"] = {"status": grounded.status, "method": "source_excerpt"}
                blocked = output_guard(reply, [row["id"] for row in grounded.matches])
                if blocked:
                    reply = blocked
                    result["grounding"]["status"] = "blocked"
                    result["safety"]["generated_output_blocked"] = True
        if result["clarification"] is not None:
            result["clarification"]["original_route"] = analysis["route"]
            if analysis["route"] == "draft_for_confirmation":
                analysis["route"] = "clarify"
        result["answer"] = reply
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
        self.history = self.history[-8:]
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


def load_coach(ai_root: Path, *, generate=True, adapted=False, nlp_version="1.8.0", retrieval_version="1.1.2"):
    from .retrieval_runtime import load_search
    nlp = load_nlp(ai_root, nlp_version)
    search = load_search(ai_root, retrieval_version)
    return Coach(nlp, search, LocalLM(ai_root, adapted=adapted) if generate else None)
