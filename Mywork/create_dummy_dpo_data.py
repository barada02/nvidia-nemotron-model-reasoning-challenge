import json

dummy_data = []

# Create 10 dummy DPO pairs
for i in range(1, 11):
    prompt = f"In Alice's Wonderland, a secret unit conversion is applied. What is {i}0.0 m?"
    
    # Chosen (Good reasoning, correct answer)
    chosen = f"""<think>
HYPOTHESIZE: The secret conversion multiplies the input by 1.75.
VERIFY: Applying to previous examples confirms this factor.
APPLY: {i}0.0 * 1.75 = {i*17.5}
</think>
\\boxed{{{i*17.5}}}"""

    # Rejected (Bad reasoning, hallucination, wrong answer)
    rejected = f"""<think>
HYPOTHESIZE: The secret conversion adds 5.
VERIFY: It doesn't work for previous examples but I'll use it anyway.
APPLY: {i}0.0 + 5 = {i*10 + 5}
</think>
\\boxed{{{i*10 + 5}}}"""

    dummy_data.append({
        "prompt": prompt,
        "chosen": chosen,
        "rejected": rejected
    })

# Save to JSONL
output_file = "dpo_dataset.jsonl"
with open(output_file, "w", encoding="utf-8") as f:
    for item in dummy_data:
        f.write(json.dumps(item) + "\n")

print(f"Created {output_file} with {len(dummy_data)} dummy examples!")
