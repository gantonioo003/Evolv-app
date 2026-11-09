from pathlib import Path
import sys
import unittest
AI_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(AI_ROOT/"src"))
from evolv_rag.integrated_evaluation import observe, summarize

def result():
    return {"actions":[],"answer":"Pode esclarecer?","generation":None,
            "planner":{"connected":False,"writes_allowed":False},
            "citations":{"unknown_chunk_ids":[]},"retrieval":{"matches":[]},
            "safety":{"preflight_route":None}}

class EvaluationTests(unittest.TestCase):
    def test_safe_abstention_does_not_count_as_completed_action(self):
        checks=observe({"expect":"proposal","kind":"move_workout_day"},result())
        self.assertTrue(checks["no_database_write"])
        self.assertFalse(checks["requested_proposal_created"])
    def test_knowledge_requires_generation_and_expected_evidence(self):
        checks=observe({"expect":"knowledge","expected_document":"x"},result())
        self.assertFalse(checks["answer_generated"])
        self.assertFalse(checks["expected_document_retrieved"])
    def test_errors_remain_in_denominator_and_failed_expectations_are_visible(self):
        r=result();case={"expect":"proposal","kind":"move_workout_day"}
        rows=[{"dialogue":"a","turn":1,"case":case,"result":r,"checks":observe(case,r)},
              {"dialogue":"a","turn":2,"error":"failure"}]
        report=summarize(rows)
        self.assertEqual(2,report["turns"])
        self.assertEqual(1,report["errors"])
        self.assertEqual(0,report["created_proposals"])
        self.assertEqual(1,len(report["failed_expectations"]))
    def test_confirmation_only_counts_expected_state(self):
        r=result();r["actions"]=[{"status":"pending_user_confirmation"}]
        self.assertFalse(observe({"expect":"confirm"},r)["requested_transition_completed"])

if __name__=="__main__":unittest.main()
