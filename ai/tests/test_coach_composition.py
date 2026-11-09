from copy import deepcopy
from pathlib import Path
import sys
import unittest
AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_rag.coach import Coach
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

    def test_previous_user_question_is_context_but_assistant_claim_is_excluded(self):
        self.c.history = [{"role": "user", "content": "O que é volume?"},
                          {"role": "assistant", "content": "Afirmação inventada na resposta anterior."}]
        self.c.respond("E nesse caso?")
        self.assertIn("O que é volume?", self.lm.messages[-1]["content"])
        self.assertNotIn("Afirmação inventada", str(self.lm.messages))

if __name__ == "__main__":
    unittest.main()
