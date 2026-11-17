"""Regression coverage for writer context through the authenticated API."""
import json
import unittest
from uuid import uuid4
import test_coach_api as api


class Writer:
    settings = {"max_input_tokens": 2048}

    def __init__(self):
        self.prompts = []

    def count(self, messages):
        return len(json.dumps(messages, ensure_ascii=False)) // 4

    def write(self, messages):
        self.prompts.append(messages)
        return {"text": "Entendi esse detalhe.", "stopped_at_eos": True}


class WriterAPITests(unittest.TestCase):
    setUp = api.APITests.setUp
    tearDown = api.APITests.tearDown
    session = api.APITests.session
    message = api.APITests.message

    def test_budget_keeps_complete_recent_pairs_and_handles_large_profile(self):
        from evolv_rag.conversation_writer import messages_for_writer, trim_history
        from evolv_rag.account_context import AccountContext
        writer = Writer()
        history = []
        for i in range(15):
            history.extend([{'role': 'user', 'content': f'detalhe {i} ' + 'x' * 120},
                            {'role': 'assistant', 'content': 'entendi ' + 'y' * 120}])
        kept = trim_history(history, writer)
        self.assertGreater(len(kept), 8)
        self.assertLess(len(kept), len(history))
        self.assertEqual(kept[-2:], history[-2:])
        self.assertEqual(len(kept) % 2, 0)
        messages = messages_for_writer(history, 'continuando', AccountContext(), writer.count, 2048)
        self.assertLessEqual(writer.count(messages), 2048)
        self.assertEqual(messages[-1]['content'], 'continuando')
        self.assertEqual(messages[1]['role'], 'user')
        self.assertIsNone(messages_for_writer([], 'x' * 10000, AccountContext(), writer.count, 2048))

    def test_writer_restore_correction_and_account_scope(self):
        writer = Writer()
        self.app.state.manager.prototype.lm = writer
        sid = self.session()
        turns = []
        for text in ["Só consigo terça de manhã", "Corrigindo, quinta à noite", "cheguei aqui", "tô por aqui", "dia corrido"]:
            turns.extend([{"role": "user", "content": text}, {"role": "assistant", "content": "Entendi."}])
        response = self.client.put(f"/v1/sessions/{sid}/history", headers=self.headers, json={"messages": turns})
        self.assertEqual(response.status_code, 200, response.text)
        result = self.message(sid, text="acabei de chegar", account_context={
            "weight_kg": 73, "memory_enabled": True, "memories": ["Prefiro comida caseira"],
        })
        self.assertEqual(result.status_code, 200, result.text)
        prompt = json.dumps(writer.prompts[-1], ensure_ascii=False)
        self.assertIn("quinta à noite", prompt)
        self.assertIn("terça de manhã", prompt)
        self.assertIn("comida caseira", prompt)
        self.assertIn("73", prompt)
        fresh = self.session()
        self.message(fresh, text="acabei de chegar", account_context={
            "memory_enabled": False, "memories": ["SEGREDO_DESATIVADO"], "weight_kg": 90,
        })
        prompt = json.dumps(writer.prompts[-1], ensure_ascii=False)
        for forbidden in ("quinta", "comida caseira", "SEGREDO_DESATIVADO", "73"):
            self.assertNotIn(forbidden, prompt)
        foreign = {**self.headers, "X-Evolv-User-ID": str(uuid4())}
        response = self.client.put(f"/v1/sessions/{sid}/history", headers=foreign, json={"messages": turns})
        self.assertEqual(response.status_code, 404)

    def test_writer_cannot_claim_a_plan_change_that_did_not_happen(self):
        from evolv_rag.conversation_writer import write_conversation

        writer = Writer()
        for claim in (
            "A fruta do café da manhã foi trocada de maçã para pera. Confirmação?",
            "Troquei a fruta do café da manhã.",
        ):
            with self.subTest(claim=claim):
                writer.write = lambda messages: {"text": claim, "stopped_at_eos": True}
                answer = write_conversation(writer, [], "é a fruta do café", None)
                self.assertIn("nenhuma alteração foi executada", answer)

        reply = "Não troquei a fruta. Posso ajudar a conferir as opções."
        writer.write = lambda messages: {"text": reply, "stopped_at_eos": True}
        self.assertEqual(reply, write_conversation(writer, [], "mudou?", None))

    def test_urgent_report_never_reaches_writer(self):
        writer = Writer()
        self.app.state.manager.prototype.lm = writer
        result = self.message(self.session(), text="Tô com aperto no peito e sem ar agora.")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(writer.prompts, [])
