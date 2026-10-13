"""Ephemeral conversational context; no persistent memory or automatic approval."""
from datetime import date

from evolv_nlp.entities import normalize_text
from evolv_nlp.risk_rules_v13 import detect_risks


def analyze_conversation(pipeline, messages: list[dict], reference_date: date) -> dict:
    if not isinstance(messages, list) or not 1 <= len(messages) <= 20:
        raise ValueError("Conversa deve conter entre 1 e 20 mensagens")
    for message in messages:
        if message.get("role") not in {"user", "assistant"} or not isinstance(message.get("content"), str):
            raise ValueError("Mensagem invalida")
        if not message["content"].strip() or len(message["content"]) > 8000:
            raise ValueError("Conteudo invalido")
    if messages[-1]["role"] != "user":
        raise ValueError("Ultima mensagem deve ser do usuario")
    report = pipeline.analyze(messages[-1]["content"], reference_date)
    earlier = [m for m in messages[:-1] if m["role"] == "user"][-3:]
    from evolv_nlp.entities_v13 import extract_entities
    candidates = []
    prior_risks = set()
    for index, message in enumerate(earlier):
        prior_risks.update(detect_risks(message["content"]).risks)
        for entity in extract_entities(message["content"], pipeline.catalog, reference_date).entities:
            if entity.entity_type in {"exercise", "food", "modality", "goal"} and not entity.attributes.get("negated"):
                candidates.append({"entity_type": entity.entity_type, "value": entity.value,
                                   "source_user_turn": index, "resolved": False})
    folded = normalize_text(messages[-1]["content"])
    import re
    elliptical = bool(re.search(r"\b(?:esse|essa|isso|aquele|aquela|o mesmo|a mesma|e amanha|e depois)\b|^\s*(?:por que|pq|sim|nao)\s*[?!.]*$", folded))
    if elliptical and earlier and report["decision"]["status"] != "safety_review":
        report["decision"] = {"status": "clarify", "route": "clarify", "reasons": ["unresolved_conversation_reference"]}
        report["clarification"] = "A qual parte da conversa voce esta se referindo?"
        report["proposal"] = None
    if prior_risks and report["decision"]["route"] == "planner_preview":
        report["decision"] = {"status": "clarify", "route": "clarify", "reasons": ["prior_risk_context_requires_review"]}
        report["clarification"] = "Esse pedido esta relacionado ao desconforto ou risco que voce mencionou antes?"
        report["proposal"] = None
    report["conversation_context"] = {
        "provided_user_turns": len(earlier) + 1, "reference_candidates": candidates,
        "prior_risk_signals": sorted(prior_risks), "references_resolved_automatically": False,
        "assistant_text_is_authorization": False, "confirmation_requires_trusted_pending_action": True,
        "persistent_memory": False, "conversation_training_authorized": False,
        "history_is_not_new_medical_clearance": True,
    }
    return report
