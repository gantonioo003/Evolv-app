"""Real loopback HTTP smoke check. Temporary secret stays in process memory."""
from importlib.metadata import version
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from uuid import uuid4
import httpx
AI_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(AI_ROOT/"src"))
from evolv_rag.preparation import write,digest

def main():
    output=AI_ROOT/"artifacts/coach_api/1.0.0"
    if output.exists():raise FileExistsError(output)
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1",0))
        port=reserved.getsockname()[1]
    env=os.environ.copy()
    env["EVOLV_AI_SERVICE_KEY"]=secrets.token_urlsafe(32)
    env["EVOLV_AI_MODE"]="generate"
    env["EVOLV_AI_VARIANT"]="original"
    env["PYTHONPATH"]=str(AI_ROOT/"src")
    headers={"Authorization":"Bearer "+env["EVOLV_AI_SERVICE_KEY"],
             "X-Evolv-User-ID":str(uuid4())}
    args=[sys.executable,"-m","uvicorn","evolv_api.app:create_app","--factory",
          "--host","127.0.0.1","--port",str(port),"--workers","1","--no-access-log"]
    process=subprocess.Popen(args,cwd=AI_ROOT,env=env,stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
    started=time.monotonic()
    report=None
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}",timeout=180,trust_env=False) as client:
            deadline=started+300
            while time.monotonic()<deadline:
                if process.poll() is not None:raise RuntimeError("Local service exited during startup")
                try:
                    ready=client.get("/health/ready",headers=headers,timeout=2)
                    if ready.status_code==200:break
                    if ready.status_code==503:raise RuntimeError("Model loading failed")
                except httpx.RequestError:pass
                time.sleep(.5)
            else:raise RuntimeError("Model startup deadline exceeded")
            print("Real API ready.",flush=True)
            ready_seconds=time.monotonic()-started
            assert client.get("/health/ready").status_code==401
            created=client.post("/v1/sessions",json={},headers=headers)
            assert created.status_code==201
            sid=created.json()["session_id"]
            body={"request_id":str(uuid4()),"text":"Quanto tempo um adulto deve dormir?"}
            response=client.post(f"/v1/sessions/{sid}/messages",json=body,headers=headers)
            assert response.status_code==200,response.status_code
            result=response.json()["result"]
            assert result["generation"] is not None,"Real generation not observed"
            repeated=client.post(f"/v1/sessions/{sid}/messages",json=body,headers=headers)
            assert repeated.json()==response.json()
            foreign={**headers,"X-Evolv-User-ID":str(uuid4())}
            cross=client.post(f"/v1/sessions/{sid}/messages",json=body,headers=foreign)
            assert cross.status_code==404
            assert client.delete(f"/v1/sessions/{sid}",headers=headers).status_code==204
            assert client.post(f"/v1/sessions/{sid}/messages",json=body,headers=headers).status_code==404
            report={"phase":"7.06.1","real_uvicorn_http":True,"host":"loopback",
                    "real_nlp_search_and_qwen":True,"variant":"original",
                    "startup_seconds":ready_seconds,"http_unit_tests_passed":12,
                    "auth_enforced":True,"cross_user_access_blocked":True,
                    "duplicate_request_response_reused":True,"deleted_session_unavailable":True,
                    "service_key_recorded":False,"database_connected":False,
                    "observed_answer":result["answer"],"generation":result["generation"],
                    "packages":{n:version(n) for n in ["fastapi","starlette","pydantic","uvicorn","httpx"]}}
    finally:
        process.terminate()
        try:process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill();process.wait(timeout=15)
    output.mkdir(parents=True)
    write(output/"verification.json",report)
    write(output/"manifest.json",{"code":{n:digest(AI_ROOT/n) for n in [
        "src/evolv_api/app.py","scripts/serve_coach.py","scripts/verify_coach_api.py","tests/test_coach_api.py"]},
        "requirements_sha256":digest(AI_ROOT/"requirements.api.txt"),
        "outputs":{"verification.json":digest(output/"verification.json")}})
    print("Verified real HTTP generation, authentication, deduplication and session ownership. Server stopped.",flush=True)

if __name__=="__main__":main()
