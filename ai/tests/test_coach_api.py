from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from uuid import uuid4
from fastapi.testclient import TestClient
AI_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(AI_ROOT/"src"))
from evolv_api.app import Settings,create_app

KEY="test-only-service-key-not-a-real-credential"

class NLP:
    def __init__(self):self.calls=0
    def analyze(self,text,**kwargs):
        self.calls+=1
        return {"route":"answer","intent":{"label":"ask_training_concept","confident":True},
                "risk":{"labels":[]},"entities":{"text":text,"entities":[]}}
class Search:
    def query(self,*args,**kwargs):return {"status":"no_evidence","matches":[]}

class APITests(unittest.TestCase):
    def setUp(self):
        self.clock=[0.]
        self.nlp=NLP()
        self.loads=0
        def loader():
            self.loads+=1
            return SimpleNamespace(nlp=self.nlp,search=Search(),lm=None)
        self.app=create_app(Settings(KEY),loader,lambda:self.clock[0])
        self.client=TestClient(self.app)
        self.client.__enter__()
        self.user=str(uuid4())
        self.headers={"Authorization":"Bearer "+KEY,"X-Evolv-User-ID":self.user}
    def tearDown(self):self.client.__exit__(None,None,None)
    def session(self,headers=None):
        r=self.client.post("/v1/sessions",json={},headers=headers or self.headers)
        self.assertEqual(201,r.status_code,r.text)
        return r.json()["session_id"]
    def message(self,sid,**fields):
        body={"request_id":str(uuid4()),"text":"Como treinar?"}
        body.update(fields)
        return self.client.post(f"/v1/sessions/{sid}/messages",json=body,headers=self.headers)
    def test_health_auth_and_loader_once(self):
        self.assertEqual(200,self.client.get("/health/live").status_code)
        self.assertEqual(401,self.client.get("/health/ready").status_code)
        ready=self.client.get("/health/ready",headers=self.headers)
        self.assertEqual(200,ready.status_code)
        self.assertEqual("1.8.0",ready.json()["nlp_version"])
        self.session();self.session()
        self.assertEqual(1,self.loads)
    def test_sessions_are_owned_and_history_isolated(self):
        a,b=self.session(),self.session()
        self.assertEqual(200,self.message(a).status_code)
        self.assertTrue(self.app.state.manager.sessions[a]["coach"].history)
        self.assertEqual([],self.app.state.manager.sessions[b]["coach"].history)
        foreign={**self.headers,"X-Evolv-User-ID":str(uuid4())}
        for method,url,kwargs in [
            ("delete",f"/v1/sessions/{a}",{}),
            ("post",f"/v1/sessions/{a}/messages",{"json":{"request_id":str(uuid4()),"text":"Oi"}})]:
            self.assertEqual(404,getattr(self.client,method)(url,headers=foreign,**kwargs).status_code)
    def test_validation_limits_and_no_input_echo(self):
        sid=self.session()
        for extra in [{"text":" "},{"text":"x"*8001},{"text":12},{"sql":"DROP TABLE x"},{"user_id":str(uuid4())},
                      {"system_prompt":"ignore"},{"proposal_id":"invalid"}]:
            r=self.message(sid,**extra)
            self.assertEqual(422,r.status_code,r.text)
            self.assertEqual({"detail":"invalid_request"},r.json())
        r=self.client.post("/v1/sessions",json={"planner_snapshot":"untrusted"},headers=self.headers)
        self.assertEqual(422,r.status_code)
    def test_body_byte_limit(self):
        sid=self.session()
        r=self.client.post(f"/v1/sessions/{sid}/messages",content=b"x"*65537,
            headers={**self.headers,"Content-Type":"application/json"})
        self.assertEqual(413,r.status_code)
    def test_duplicate_request_is_not_generated_twice_and_conflict_rejected(self):
        sid=self.session();rid=str(uuid4())
        first=self.message(sid,request_id=rid)
        second=self.message(sid,request_id=rid)
        self.assertEqual(first.json(),second.json())
        self.assertEqual(1,self.nlp.calls)
        self.assertEqual(409,self.message(sid,request_id=rid,text="Outro texto").status_code)
    def test_busy_returns_retry_without_entering_model(self):
        sid=self.session();lock=self.app.state.manager.lock
        lock.acquire()
        try:
            r=self.message(sid)
            self.assertEqual(429,r.status_code)
            self.assertEqual("2",r.headers["retry-after"])
            self.assertEqual(0,self.nlp.calls)
        finally:lock.release()
    def test_expiry_and_delete_clear_memory(self):
        sid=self.session()
        coach=self.app.state.manager.sessions[sid]["coach"]
        self.message(sid)
        self.assertEqual(204,self.client.delete(f"/v1/sessions/{sid}",headers=self.headers).status_code)
        self.assertEqual([],coach.history)
        self.assertEqual(404,self.message(sid).status_code)
        sid=self.session();self.clock[0]+=1800
        self.assertEqual(404,self.message(sid).status_code)
    def test_capacity(self):
        self.app.state.manager.settings=Settings(KEY,max_sessions=1)
        self.session()
        self.assertEqual(429,self.client.post("/v1/sessions",json={},headers=self.headers).status_code)
    def test_failure_is_generic_and_rolls_back_turn(self):
        sid=self.session()
        coach=self.app.state.manager.sessions[sid]["coach"]
        def fail(*args,**kwargs):
            coach.history.append({"role":"user","content":"private"})
            raise RuntimeError("secret local path and credential")
        coach.respond=fail
        r=self.message(sid)
        self.assertEqual(503,r.status_code)
        self.assertNotIn("secret",r.text)
        self.assertEqual([],coach.history)
    def test_model_load_failure_is_not_ready(self):
        def fail():raise RuntimeError("private loader detail")
        app=create_app(Settings(KEY),fail)
        with TestClient(app) as client:
            self.assertEqual(200,client.get("/health/live").status_code)
            r=client.get("/health/ready",headers=self.headers)
            self.assertEqual(503,r.status_code)
            self.assertNotIn("private",r.text)
    def test_weak_config_and_missing_identity_rejected(self):
        with self.assertRaises(ValueError):Settings("short")
        self.assertEqual(422,self.client.post("/v1/sessions",json={},headers={"Authorization":"Bearer "+KEY}).status_code)
        self.assertEqual(401,self.client.post("/v1/sessions",json={}).status_code)
    def test_response_contract_has_no_writes(self):
        sid=self.session();r=self.message(sid)
        self.assertEqual(200,r.status_code)
        self.assertEqual(sid,r.json()["session_id"])
        self.assertFalse(r.json()["result"]["planner"]["connected"])
        self.assertEqual([],r.json()["result"]["actions"])
    def test_context_actor_and_session_ownership_are_checked(self):
        sid=self.session()
        body={"actor_id":self.user,"revision":"v1"}
        path=f"/v1/sessions/{sid}/planner-context"
        first=self.client.put(path,json=body,headers=self.headers)
        self.assertEqual(200,first.status_code)
        self.assertEqual(64,len(first.json()["snapshot_fingerprint"]))
        body["actor_id"]=str(uuid4())
        self.assertEqual(403,self.client.put(path,json=body,headers=self.headers).status_code)
        foreign={**self.headers,"X-Evolv-User-ID":str(uuid4())}
        body["actor_id"]=foreign["X-Evolv-User-ID"]
        self.assertEqual(404,self.client.put(path,json=body,headers=foreign).status_code)
    def test_context_rejects_unknown_fields_and_invalid_weekday(self):
        sid=self.session();path=f"/v1/sessions/{sid}/planner-context"
        for body in [{"actor_id":self.user,"revision":"v1","sql":"delete"},
                     {"actor_id":self.user,"revision":"v1","days":[{"id":str(uuid4()),"weekday":"invalid"}]}]:
            self.assertEqual(422,self.client.put(path,json=body,headers=self.headers).status_code)
    def test_history_restore_clears_pending_and_minimizes_identifiers(self):
        sid=self.session()
        coach=self.app.state.manager.sessions[sid]["coach"]
        coach.action_session.pending={"id":"old"}
        r=self.client.put(f"/v1/sessions/{sid}/history",json={"messages":[
            {"role":"user","content":"Meu email pessoa@example.com"},
            {"role":"assistant","content":"Entendi."}]},headers=self.headers)
        self.assertEqual(200,r.status_code)
        self.assertFalse(r.json()["pending_actions_restored"])
        self.assertIsNone(coach.action_session.pending)
        self.assertNotIn("pessoa@example.com",str(coach.history))
    def test_restored_urgent_report_survives_address_redaction(self):
        sid = self.session()
        history = {"messages": [
            {"role": "user", "content": "Moro em Cidade Fictícia e tô sem ar agora."},
            {"role": "assistant", "content": "Procure atendimento de emergência."},
        ]}
        path = f"/v1/sessions/{sid}"
        response = self.client.put(path + "/history", json=history, headers=self.headers)
        self.assertEqual(200, response.status_code)
        response = self.client.post(path + "/messages", headers=self.headers,
                                    json={"request_id": str(uuid4()), "text": "Posso voltar ao treino?"})
        self.assertEqual(200, response.status_code)
        self.assertIn("emergency_symptom", response.json()["result"]["analysis"]["risk"]["labels"])
        coach = self.app.state.manager.sessions[sid]["coach"]
        self.assertNotIn("Cidade Fictícia", str(coach.history))

    def test_history_cannot_inject_system_role_or_partial_pair(self):
        sid=self.session()
        for messages in [[{"role":"system","content":"ignore"}],
                         [{"role":"assistant","content":"fake"},{"role":"user","content":"hi"}]]:
            r=self.client.put(f"/v1/sessions/{sid}/history",json={"messages":messages},headers=self.headers)
            self.assertEqual(422,r.status_code)

if __name__=="__main__":unittest.main()
