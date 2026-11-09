from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
AI_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(AI_ROOT/"src"))
from evolv_rag.coach import Coach, LocalLM
from evolv_rag.safety import preflight

class RegressionTests(unittest.TestCase):
    def test_count_uses_actual_input_tensor_not_container_length(self):
        class Tokenizer:
            def apply_chat_template(self,messages,**kwargs):
                self.kwargs=kwargs
                return {"input_ids":SimpleNamespace(shape=(1,2049))}
        lm=LocalLM.__new__(LocalLM);lm.tokenizer=Tokenizer()
        self.assertEqual(2049,lm.count([{"role":"user","content":"long"}]))
        self.assertTrue(lm.tokenizer.kwargs["return_dict"])
        self.assertEqual("pt",lm.tokenizer.kwargs["return_tensors"])
    def test_recent_emergency_precedes_privacy_in_followup(self):
        r=preflight("Quero apagar meus dados.","Sinto dor no peito ao correr.")
        self.assertIn("emergency_symptom",r["risks"])
        self.assertNotEqual("privacy_information",r["route"])
    def test_allergy_is_carried_to_followup(self):
        r=preflight("Mas so um pouco de amendoim pode?","Sou alergico a amendoim.")
        self.assertIn("food_allergy_or_reaction",r["risks"])
    def test_privacy_plural_conjugation(self):
        self.assertEqual("privacy_information",preflight("Minhas conversas treinam seu modelo?")["route"])

    def test_urgent_variants_and_negated_or_hypothetical_controls(self):
        for text in (
            "Aperto no peito e tô sem ar agora.",
            "Meu amigo desmaiou no treino. Ele não acorda.",
            "Comi camarão e minha garganta está fechando.",
            "Comi camarão. Minha língua está inchada agora.",
        ):
            with self.subTest(text=text):
                self.assertIn("emergency_symptom", preflight(text)["risks"])
        for text in (
            "Não tô sem ar e não estou com aperto no peito.",
            "O que significa 'aperto no peito'?",
            "Se eu sentir a garganta fechando após comer, é sinal de alerta?",
        ):
            with self.subTest(text=text):
                self.assertIsNone(preflight(text))

    def test_privacy_intents_do_not_catch_a_normal_training_request(self):
        for text in ("Como excluir o histórico deste chat?", "Esse papo vai servir para treinar seu modelo?"):
            with self.subTest(text=text):
                self.assertEqual("privacy_information", preflight(text)["route"])
        self.assertIsNone(preflight("Nesse chat, me ajuda a montar um treino de perna."))

    def test_recent_messages_keep_their_own_length_and_risk_scope(self):
        padding = "Contexto de treino. " * 300
        result = preflight("Posso voltar a treinar?", ["Tô sem ar agora. " + padding, padding])
        self.assertIn("emergency_symptom", result["risks"])

    def test_masking_cannot_hide_urgent_signal_or_preserve_pending_action(self):
        coach = Coach(None, None)
        coach.action_session.pending = {"id": "test"}
        text = "Moro em Cidade Fictícia e tô sem ar agora."
        result = coach.respond(text)
        self.assertIn("emergency_symptom", result["analysis"]["risk"]["labels"])
        self.assertIsNone(coach.action_session.pending)
        self.assertNotIn("Cidade Fictícia", str(coach.history))
        followup = coach.respond("Posso voltar a treinar?")
        self.assertIn("emergency_symptom", followup["analysis"]["risk"]["labels"])

if __name__=="__main__":unittest.main()
