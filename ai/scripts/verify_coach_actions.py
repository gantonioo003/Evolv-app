"""Record deterministic safety/action checks using authored fixtures; no GPU or DB."""
from datetime import date
import io
from pathlib import Path
import re
import sys
import unittest
AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_rag.preparation import read, write, digest
from evolv_rag.safety import preflight

def main():
    output = AI_ROOT / "artifacts/coach/1.1.0"
    if output.exists():
        raise FileExistsError(output)
    stream = io.StringIO()
    tests = unittest.defaultTestLoader.discover(str(AI_ROOT / "tests"), pattern="test_coach_*.py")
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(tests)
    if not result.wasSuccessful():
        raise RuntimeError(stream.getvalue())
    # DTO names are extracted from the actual backend contract, not duplicated claims.
    dto = AI_ROOT.parent / "backend/src/planner/dto/create-planner-adjustment.dto.ts"
    text = dto.read_text(encoding="utf-8")
    from evolv_rag.actions import KINDS
    declared_kinds = set(re.findall(r"'([^']+)'", text.split("plannerAdjustmentKinds = [",1)[1].split("]",1)[0]))
    if declared_kinds != set(KINDS):
        raise ValueError("Backend kinds changed")
    declared_fields = set(re.findall(r"^\s+(\w+)\??:", text, flags=re.M))
    for fields in KINDS.values():
        if not fields | {"kind", "source", "reason"} <= declared_fields:
            raise ValueError("Backend fields changed")
    output.mkdir(parents=True)
    report = {"phase":"7.05.4", "schema_version":"coach.1.1.0",
              "tests_passed":result.testsRun, "backend_kind_and_field_names_match":True,
              "backend_validator_executed":False, "model_retrained":False,
              "database_connected":False, "planner_preview_api_called":False,
              "test_scope":"deterministic and integration doubles; actual entity extractor, not NLU accuracy or LM generation",
              "guards":[{"query":q, "result":preflight(q)} for q in [
                  "Sou alergico a amendoim, posso comer?", "Dor no peito ao correr",
                  "Quero apagar meus dados", "Tenho dor no peito. Quero apagar meus dados."]]}
    write(output / "verification.json", report)
    (output / "tests.txt").write_text(stream.getvalue(),encoding="utf-8")
    names = ["src/evolv_rag/coach.py", "src/evolv_rag/actions.py","src/evolv_rag/safety.py",
             "tests/test_coach_actions.py","tests/test_coach_composition.py","scripts/verify_coach_actions.py"]
    write(output / "manifest.json", {"code":{name:digest(AI_ROOT/name) for name in names},
          "backend_contract_sha256":digest(dto),
          "previous_verification_sha256":digest(AI_ROOT/"artifacts/coach/1.0.0/verification.json"),
          "outputs":{name:digest(output/name) for name in ["verification.json","tests.txt"]}})
    print(f"Verified: {result.testsRun} tests and four backend action contracts.")

if __name__ == "__main__":
    main()
