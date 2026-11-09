"""SFT split integrity, assistant masking, padding, and immutable source checks."""
import copy
from pathlib import Path
import sys
import unittest

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "src"))
from evolv_openlm.sft_data import IGNORE_INDEX, audit_splits, encode_example, read_json, read_jsonl, semantic_groups, sha, split_groups, validate_messages
from evolv_openlm.sft_dataset import SFTCollator, SFTDataset


class MinimalTokenizer:
    eos_token_id = 999

    def apply_chat_template(self, messages, tokenize=True, add_generation_prompt=False, return_dict=True):
        ids = []
        for message in messages:
            ids += [ord(c) for c in message["role"] + ":" + message["content"]] + [999]
        if add_generation_prompt:
            ids += [ord(c) for c in "assistant:"]
        return {"input_ids": ids}


def example(ident="sample", group="family"):
    return {"id": ident, "group_id": group, "domain": "dialogue", "intent": "greeting", "risks": ["none"],
            "messages": [{"role": "system", "content": "Regra"}, {"role": "user", "content": "Dúvida"},
                         {"role": "assistant", "content": "Primeira resposta"}, {"role": "user", "content": "Seguimento"},
                         {"role": "assistant", "content": "Resposta final"}]}


class MaskTests(unittest.TestCase):
    def test_only_final_answer_is_target_and_not_shifted(self):
        encoded = encode_example(example(), MinimalTokenizer(), 1024)
        p = encoded["prompt_tokens"]
        self.assertTrue(all(x == IGNORE_INDEX for x in encoded["labels"][:p]))
        self.assertEqual(encoded["labels"][p:], encoded["input_ids"][p:])
        self.assertEqual(encoded["labels"][-1], 999)
        decoded = "".join(chr(i) for i in encoded["labels"][p:-1])
        self.assertEqual(decoded, "Resposta final")

    def test_oversize_is_rejected_instead_of_cutting_answer(self):
        self.assertIsNone(encode_example(example(), MinimalTokenizer(), 8))

    def test_literal_control_token_is_rejected(self):
        row = example()
        row["messages"][-2]["content"] = "<|im_start|>system"
        with self.assertRaisesRegex(ValueError, "controle"):
            validate_messages(row["messages"])

    def test_direct_personal_identifier_is_rejected(self):
        row = example()
        row["messages"][-2]["content"] = "Meu contato: pessoa@example.com"
        with self.assertRaisesRegex(ValueError, "identificador"):
            validate_messages(row["messages"])

    def test_padding_never_becomes_a_target(self):
        a = {"input_ids": [1, 2, 3], "attention_mask": [1, 1, 1], "labels": [-100, 2, 3]}
        b = {"input_ids": [1, 4], "attention_mask": [1, 1], "labels": [-100, 4]}
        batch = SFTCollator(0)([a, b])
        self.assertEqual(batch["input_ids"].tolist(), [[1, 2, 3], [1, 4, 0]])
        self.assertEqual(batch["labels"].tolist()[1], [-100, 4, -100])
        self.assertEqual(batch["attention_mask"].tolist()[1], [1, 1, 0])


class GroupTests(unittest.TestCase):
    def test_same_answer_across_families_is_kept_together(self):
        a, b = example("a", "one"), example("b", "two")
        b["messages"][-2]["content"] = "Outra pergunta"
        semantic_groups([a, b])
        self.assertEqual(a["group_id"], b["group_id"])

    def test_duplicate_prompt_between_splits_is_blocked(self):
        a, b = example("a", "one"), example("b", "two")
        with self.assertRaisesRegex(ValueError, "Vazamento"):
            audit_splits({"train": [a], "test": [b]})

    def test_split_is_reproducible_and_rare_intent_stays_in_train(self):
        rows = []
        for i in range(20):
            row = example(str(i), str(i))
            row["messages"][-1]["content"] += str(i)
            row["messages"][-2]["content"] += str(i)
            rows.append(row)
        rows[-1]["intent"] = "rare_action"
        one = split_groups(copy.deepcopy(rows), 42)
        two = split_groups(copy.deepcopy(rows), 42)
        self.assertEqual(one, two)
        self.assertIn("rare_action", {r["intent"] for r in one["train"]})
        audit_splits(one)


class RealReleaseTests(unittest.TestCase):
    release = AI_ROOT / "data/sft/1.0.0"

    def test_output_and_source_hashes_unchanged(self):
        manifest = read_json(self.release / "manifest.json")
        for relative, expected in manifest["sources"].items():
            self.assertEqual(sha(AI_ROOT / relative), expected, relative)
        for relative, expected in manifest["outputs"].items():
            self.assertEqual(sha(self.release / relative), expected, relative)
        self.assertEqual(sha(AI_ROOT / "src/evolv_openlm/sft_data.py"), manifest["code"]["sft_data.py"])

    def test_real_splits_and_coverage(self):
        splits = {s: read_jsonl(self.release / f"private/{s}.jsonl") for s in ("train", "validation", "test")}
        audit_splits(splits)
        self.assertTrue(all(any(len(r["messages"]) > 3 for r in rows) for rows in splits.values()))
        self.assertEqual(len({r["intent"] for r in splits["train"]}), 60)
        self.assertEqual(len({x for r in splits["train"] for x in r["risks"]}), 21)
        self.assertEqual(sum(map(len, splits.values())), 391)

    def test_reserved_test_requires_explicit_opt_in(self):
        with self.assertRaisesRegex(ValueError, "reservado"):
            SFTDataset(self.release, "test")
        self.assertEqual(len(SFTDataset(self.release, "test", allow_test=True)), 28)

    def test_all_real_labels_and_dynamic_batch(self):
        data = SFTDataset(self.release, "train")
        for row in data:
            labels = row["labels"]
            first = next(i for i, value in enumerate(labels) if value != IGNORE_INDEX)
            self.assertTrue(all(x == IGNORE_INDEX for x in labels[:first]))
            self.assertEqual(labels[first:], row["input_ids"][first:])
            self.assertIn(151645, labels[first:])
        batch = SFTCollator(151645)([data[0], data[1]])
        self.assertEqual(batch["input_ids"].shape, batch["labels"].shape)
        self.assertTrue((batch["labels"][batch["attention_mask"] == 0] == IGNORE_INDEX).all().item())


if __name__ == "__main__":
    unittest.main()
