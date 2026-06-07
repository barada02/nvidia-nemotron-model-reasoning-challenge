from vllm import LLM, SamplingParams
import pandas as pd
import re
import json

# ── config ──────────────────────────────────────────────
MODEL_PATH = "nvidia/Nemotron-3-Nano-30B"   # or local path
CSV_PATH   = "train.csv"
OUT_PATH   = "baseline_results.jsonl"

# ── load ─────────────────────────────────────────────────
df = pd.read_csv(CSV_PATH)

llm = LLM(
    model=MODEL_PATH,
    tensor_parallel_size=4,   # adjust to your GPU count
    max_model_len=4096,
    gpu_memory_utilization=0.90,
)

sampling = SamplingParams(
    temperature=0.0,           # greedy — we want deterministic baseline
    max_tokens=1024,
    stop=["</think>\\n\\boxed{"]   # don't stop here, just a safety net
)

# ── build prompts ─────────────────────────────────────────
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)

def build_prompt(puzzle_text: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": puzzle_text}
    ]
    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

prompts = [build_prompt(row["prompt"]) for _, row in df.iterrows()]

# ── inference ─────────────────────────────────────────────
outputs = llm.generate(prompts, sampling)

# ── parse + compare ───────────────────────────────────────
def extract_boxed(text: str) -> str | None:
    """Extract content from \\boxed{...} — handles nested braces"""
    match = re.search(r"\\boxed\{([^}]*)\}", text)
    return match.group(1).strip() if match else None

def extract_think(text: str) -> str | None:
    match = re.search(r"<think>(.*?)</think>", text, re.DOTALL)
    return match.group(1).strip() if match else None

results = []
for i, (_, row) in enumerate(df.iterrows()):
    raw_output   = outputs[i].outputs[0].text
    model_answer = extract_boxed(raw_output)
    ground_truth = str(row["answer"]).strip()
    correct      = (model_answer == ground_truth)

    results.append({
        "id":           row["id"],
        "prompt":       row["prompt"],
        "ground_truth": ground_truth,
        "model_answer": model_answer,
        "correct":      correct,
        "raw_output":   raw_output,
        "think_block":  extract_think(raw_output),
    })

# ── save ──────────────────────────────────────────────────
with open(OUT_PATH, "w") as f:
    for r in results:
        f.write(json.dumps(r) + "\n")

# ── quick summary ─────────────────────────────────────────
total   = len(results)
correct = sum(r["correct"] for r in results)
no_box  = sum(r["model_answer"] is None for r in results)

print(f"Total:        {total}")
print(f"Correct:      {correct} ({correct/total*100:.1f}%)")
print(f"Wrong:        {total - correct - no_box}")
print(f"No \\boxed{{}}:  {no_box}")