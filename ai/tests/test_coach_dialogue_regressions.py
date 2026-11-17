from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
AI_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(AI_ROOT/"src"))
from evolv_rag.coach import Coach, LocalLM
from evolv_rag.dialogue import ConversationMemory
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

    def test_informal_greeting_does_not_go_to_the_classifier(self):
        coach = Coach(None, None)
        for text in ("Ooi", "Ooooi, tudo bem?", "Oii Coach!"):
            with self.subTest(text=text):
                result = coach.respond(text)
                self.assertEqual("greeting", result["analysis"]["intent"]["label"])
                self.assertFalse(result["actions"])

    def test_sleep_followup_uses_the_reported_hours_with_a_reviewed_source(self):
        class UncertainNlp:
            def analyze(self, text, **kwargs):
                return {"route": "clarify", "intent": {"label": "clarification", "confident": False},
                        "risk": {"labels": []}, "entities": {"text": text, "entities": []}}

        class Search:
            def reviewed_document(self, document, **kwargs):
                return {"id": f"kb:{document}", "document_id": document,
                        "generation_context": {"text": "Trecho de teste."}}

        coach = Coach(UncertainNlp(), Search())
        first = coach.respond("Sabe me dizer se todas pessoas no mundo precisam dormir a mesma quantidade de horas?")
        self.assertIn("varia entre pessoas", first["answer"])
        scenario = coach.respond(
            "Entendi, por exemplo se em certa semana eu estou com muita correria do trabalho e acabar dormindo "
            "por uma semana 3/4h por dia, o quanto isso esta impactando meu progresso?"
        )
        self.assertIn("3 a 4 horas de sono por noite durante uma semana", scenario["answer"])
        self.assertIn("não dá para estimar", scenario["answer"])
        self.assertEqual(["kb:sleep_recovery_explanation"], scenario["citations"]["cited_chunk_ids"])
        self.assertFalse(scenario["actions"])
        question = ("Pode me explicar o por que o sono é tao importante para meu progresso na academia, "
                    "tente explicar com uma forma de falar leiga que todos entendam")
        followup = coach.respond(question)["answer"]
        self.assertIn("3 a 4 horas", followup)
        self.assertIn("recuperação entre treinos", followup)

        reopened = Coach(UncertainNlp(), Search())
        reopened.memory = ConversationMemory.model_validate(scenario["dialogue_context"])
        self.assertIn("3 a 4 horas", reopened.respond("E como isso afeta meu treino?")["answer"])
        self.assertIn("5 horas", reopened.respond("Na verdade, 5h por noite.")["answer"])
        corrected = reopened.respond(question)["answer"]
        self.assertIn("5 horas", corrected)
        self.assertIn("uma semana", corrected)
        reopened.respond("Dormi 6h.")
        updated = reopened.respond(question)["answer"]
        self.assertIn("6 horas", updated)
        self.assertNotIn("uma semana", updated)
        fresh = Coach(UncertainNlp(), Search())
        self.assertNotIn("3 a 4 horas", fresh.respond(question)["answer"])
        urgent = reopened.respond("Dormi 4 horas e estou com dor no peito agora. Isso afeta meu treino?")
        self.assertIn("emergency_symptom", urgent["analysis"]["risk"]["labels"])

if __name__=="__main__":unittest.main()
