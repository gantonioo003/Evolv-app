"""Paired evaluation checks: leakage, family resampling and real saved LoRA loading."""
from pathlib import Path
import sys
import tempfile
import unittest

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_openlm.comparison import aggregate_nll, build_cases, diagnostics, paired_bootstrap, prompt_messages
from evolv_openlm.comparison_report import CRITERIA, preference, validate_review


class ComparisonTests(unittest.TestCase):
    def test_batched_left_padding_matches_single_greedy(self):
        import torch
        from transformers import AutoModelForCausalLM,Qwen3Config
        from evolv_openlm.batched_inference import answer_batch

        class Batch(dict):
            def to(self,device):
                return Batch({k:v.to(device) for k,v in self.items()})

        class Tokenizer:
            eos_token_id=2
            pad_token_id=2
            padding_side="left"
            def apply_chat_template(self,messages,**kwargs):
                rows=[[int(x) for x in ms[-1]["content"].split()] for ms in messages]
                width=max(map(len,rows))
                return Batch(input_ids=torch.tensor([[2]*(width-len(r))+r for r in rows]),
                    attention_mask=torch.tensor([[0]*(width-len(r))+[1]*len(r) for r in rows]))
            def decode(self,ids,**kwargs):
                return " ".join(str(x) for x in ids if x != 2)
        torch.manual_seed(23)
        model=AutoModelForCausalLM.from_config(Qwen3Config(vocab_size=64,hidden_size=32,intermediate_size=64,
            num_hidden_layers=1,num_attention_heads=2,num_key_value_heads=1,head_dim=16,max_position_embeddings=64))
        model.eval()
        messages=[[{"role":"user","content":s}] for s in ["1 7 8","1 9","1 5 6 7"]]
        settings={"max_input_tokens":10,"max_new_tokens":5}
        batched=answer_batch(model,Tokenizer(),messages,settings,device="cpu")
        single=[answer_batch(model,Tokenizer(),[m],settings,device="cpu")[0] for m in messages]
        self.assertEqual([r["text"] for r in batched],[r["text"] for r in single])
        self.assertEqual([r["input_tokens"] for r in batched],[3,2,4])
        self.assertEqual([r["generated_tokens"] for r in batched],[r["generated_tokens"] for r in single])
        with self.assertRaises(ValueError):
            answer_batch(model,Tokenizer(),messages,{**settings,"max_input_tokens":2},device="cpu")

    def test_batch_timing_is_counted_once(self):
        from evolv_openlm.comparison_report import summarize
        cases=[{"id":str(i),"suite":"frozen_test" if i<2 else "challenge"} for i in range(4)]
        reviews={c["id"]:{v:{"scores":{x:2 for x in CRITERIA},"critical_flags":[],"reason":"ok"}
                           for v in ["original","adapted"]} for c in cases}
        generations={v:[{"id":c["id"],"batch_id":v+":0","seconds":10,"generated_tokens":20,
            "diagnostics":{"empty":False,"truncated_at_budget":False}} for c in cases] for v in ["original","adapted"]}
        summary=summarize(cases,generations,reviews)
        self.assertEqual(summary["all"]["original"]["total_generation_seconds"],10)
        self.assertEqual(summary["all"]["original"]["aggregate_tokens_per_second"],8)

    def test_reference_never_reaches_generation_prompt(self):
        row = {"messages":[{"role":"system","content":"system"},{"role":"user","content":"primeira"},
            {"role":"assistant","content":"contexto anterior"},{"role":"user","content":"pergunta"},
            {"role":"assistant","content":"SEGREDO_REFERENCIA"}]}
        prompt = prompt_messages(row)
        self.assertEqual(prompt[-1]["content"], "pergunta")
        self.assertIn("contexto anterior", str(prompt))
        self.assertNotIn("SEGREDO_REFERENCIA", str(prompt))
        self.assertEqual(len(row["messages"]),5)

    def test_invalid_conversation_rejected(self):
        with self.assertRaises(ValueError):
            prompt_messages({"messages":[{"role":"user","content":"question"}]})

    def test_token_weighted_aggregate_and_paired_groups(self):
        original = [{"id":"a","group_id":"family1","target_tokens":1,"nll_sum":4},
                    {"id":"b","group_id":"family1","target_tokens":9,"nll_sum":18},
                    {"id":"c","group_id":"family2","target_tokens":2,"nll_sum":8}]
        adapted = [{**r,"nll_sum":r["nll_sum"]-r["target_tokens"]} for r in original]
        self.assertAlmostEqual(aggregate_nll(original)["nll"], 2.5)
        result = paired_bootstrap(original, adapted, replicates=100)
        self.assertEqual(result["groups"],2)
        for edge in result["interval_95_percentile"]:
            self.assertAlmostEqual(edge,-1)
        self.assertEqual(result,paired_bootstrap(original,adapted,replicates=100))

    def test_unpaired_ids_or_tokens_rejected(self):
        row = {"id":"a","group_id":"g","target_tokens":2,"nll_sum":3}
        for altered in [{**row,"id":"b"},{**row,"target_tokens":3},{**row,"group_id":"other"}]:
            with self.assertRaises(ValueError):
                paired_bootstrap([row],[altered],replicates=10)

    def test_duplicate_cases_rejected(self):
        challenge={"id":"same","category":"test","prompt":"x","expectation":"y"}
        with self.assertRaises(ValueError):
            build_cases([], [challenge,challenge], "system")

    def test_truncation_is_diagnostic_not_quality_score(self):
        result=diagnostics({"text":"a b a b a b","stopped_at_eos":False})
        self.assertTrue(result["truncated_at_budget"])
        self.assertGreater(result["repeated_bigram_fraction"],.5)
        self.assertNotIn("safe",result)

    def test_saved_adapter_reload_matches_logits(self):
        import torch
        from transformers import AutoModelForCausalLM, Qwen3Config
        from peft import PeftModel, get_peft_model, LoraConfig
        torch.set_num_threads(2)
        config=Qwen3Config(vocab_size=64,hidden_size=32,intermediate_size=64,num_hidden_layers=1,
            num_attention_heads=2,num_key_value_heads=1,head_dim=16,max_position_embeddings=64)
        torch.manual_seed(17)
        base=AutoModelForCausalLM.from_config(config)
        state={k:v.clone() for k,v in base.state_dict().items()}
        model=get_peft_model(base,LoraConfig(task_type="CAUSAL_LM",r=2,lora_alpha=4,target_modules=["q_proj","v_proj"]))
        with torch.no_grad():
            for name,p in model.named_parameters():
                if ".lora_B." in name:
                    p.fill_(.04)
        model.eval()
        ids=torch.tensor([[1,7,8,9]])
        with torch.inference_mode():
            before=model(ids).logits
        temp_root = Path.home() / "Documents/Codex/2026-09-09/to/tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as temp:
            model.save_pretrained(temp,safe_serialization=True,save_embedding_layers=False)
            fresh=AutoModelForCausalLM.from_config(config)
            fresh.load_state_dict(state)
            restored=PeftModel.from_pretrained(fresh,temp,is_trainable=False,local_files_only=True)
            restored.eval()
            with torch.inference_mode():
                after=restored(ids).logits
            self.assertTrue(torch.equal(before,after))
            self.assertFalse(any(p.requires_grad for p in restored.parameters()))

    def test_critical_failure_has_priority_over_total(self):
        safe={"scores":{c:1 for c in CRITERIA},"critical_flags":[],"reason":"safe"}
        unsafe={"scores":{c:2 for c in CRITERIA},"critical_flags":["unsafe"],"reason":"unsafe"}
        self.assertEqual(preference({"original":safe,"adapted":unsafe}),"original")
        self.assertEqual(preference({"original":safe,"adapted":safe}),"tie")

    def test_review_must_cover_all_cases_and_only_registered_flags(self):
        score={"scores":{c:2 for c in CRITERIA},"critical_flags":[],"reason":"verified"}
        protocol={"review":{"critical_flags":["known"]}}
        reviews=[{"id":"a","original":score,"adapted":score}]
        self.assertEqual(len(validate_review([{"id":"a"}],reviews,protocol)),1)
        with self.assertRaises(ValueError):
            validate_review([{"id":"a"},{"id":"b"}],reviews,protocol)
        bad=[{"id":"a","original":score,"adapted":{**score,"critical_flags":["invented"]}}]
        with self.assertRaises(ValueError):
            validate_review([{"id":"a"}],bad,protocol)

    def test_review_rejects_out_of_range_or_boolean_scores(self):
        protocol={"review":{"critical_flags":[]}}
        for invalid in [3,True,-1]:
            score={"scores":{c:2 for c in CRITERIA},"critical_flags":[],"reason":"reason"}
            score["scores"][CRITERIA[0]]=invalid
            with self.assertRaises(ValueError):
                validate_review([{"id":"a"}],[{"id":"a","original":score,"adapted":score}],protocol)


if __name__ == "__main__":
    unittest.main()
