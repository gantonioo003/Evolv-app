"""Left-padded greedy inference with separate contexts and per-batch timing."""
import time


def answer_batch(model,tokenizer,messages,settings,device="cuda"):
    import torch
    tokenizer.padding_side="left"
    tokenizer.pad_token_id=tokenizer.eos_token_id
    inputs=tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,
        return_tensors="pt",return_dict=True,padding=True).to(device)
    lengths=inputs["attention_mask"].sum(dim=1).tolist()
    if any(length > settings["max_input_tokens"] for length in lengths):
        raise ValueError("Conversa excedeu o limite; não truncar silenciosamente.")
    padded_length=inputs["input_ids"].shape[-1]
    if str(device).startswith("cuda"):
        torch.cuda.synchronize()
    start=time.perf_counter()
    with torch.inference_mode():
        output=model.generate(**inputs,max_new_tokens=settings["max_new_tokens"],do_sample=False,
            pad_token_id=tokenizer.eos_token_id,eos_token_id=tokenizer.eos_token_id)
    if str(device).startswith("cuda"):
        torch.cuda.synchronize()
    elapsed=time.perf_counter()-start
    rows=[]
    for index,raw in enumerate(output[:,padded_length:].tolist()):
        # generate pads already-finished rows. Do not count these pads as output.
        stopped=tokenizer.eos_token_id in raw
        ids=raw[:raw.index(tokenizer.eos_token_id)+1] if stopped else raw
        rows.append({"text":tokenizer.decode(ids,skip_special_tokens=True),"input_tokens":int(lengths[index]),
            "generated_tokens":len(ids),"seconds":elapsed,"tokens_per_second":len(ids)/max(elapsed,1e-9),
            "stopped_at_eos":stopped,"batch_seconds":elapsed,"batch_size":len(messages)})
    return rows


def generate_cases_batched(model,tokenizer,cases,settings,destination,progress,variant,batch_size):
    import json,os
    from pathlib import Path
    from .sft_data import read_jsonl
    from .training import atomic_json
    from .comparison import diagnostics
    destination=Path(destination)
    previous=read_jsonl(destination) if destination.exists() else []
    if [r["id"] for r in previous] != [r["id"] for r in cases[:len(previous)]]:
        raise ValueError("Saída parcial diferente do protocolo.")
    if len(previous) != len(cases) and len(previous) % batch_size:
        raise ValueError("Lote parcial em arquivo; preservar para auditoria, não retomar silenciosamente.")
    for start in range(len(previous),len(cases),batch_size):
        batch=cases[start:start+batch_size]
        results=answer_batch(model,tokenizer,[c["messages"] for c in batch],settings)
        # One fsynced append for a complete batch. A killed write is rejected by JSONL parsing.
        serialized=[]
        for case,result in zip(batch,results):
            row={"id":case["id"],"suite":case["suite"],"category":case["category"],"variant":variant,
                "batch_id":f"{variant}:{start//batch_size}",**result,"diagnostics":diagnostics(result)}
            serialized.append(json.dumps(row,ensure_ascii=False)+"\n")
        with destination.open("a",encoding="utf-8",newline="\n") as stream:
            stream.write("".join(serialized));stream.flush();os.fsync(stream.fileno())
        atomic_json(progress,{"status":"generating","variant":variant,"completed":start+len(batch),
            "total_per_variant":len(cases),"batch_size":batch_size,"last_batch_seconds":results[0]["batch_seconds"]})
        print(f"{variant}: {start+len(batch)}/{len(cases)} ({results[0]['batch_seconds']:.1f}s por lote de {len(batch)})",flush=True)
