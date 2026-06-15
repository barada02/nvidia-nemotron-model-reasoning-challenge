import nbformat as nbf
import os

nb = nbf.v4.new_notebook()

nb.cells.append(nbf.v4.new_markdown_cell("# 🎯 Direct Preference Optimization (DPO) with Unsloth\nThis notebook fine-tunes your existing SFT LoRA adapter using DPO. It loads the `dpo_dataset.jsonl` which contains `{prompt, chosen, rejected}` pairs, and trains the model to prefer the `chosen` logic trace over the `rejected` one."))

nb.cells.append(nbf.v4.new_markdown_cell("## 📦 Step 1: Install Dependencies"))
code1 = '''!pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
!pip install --no-deps trl peft accelerate bitsandbytes xformers
'''
nb.cells.append(nbf.v4.new_code_cell(code1))

nb.cells.append(nbf.v4.new_markdown_cell("## 🔧 Step 2: Initialize Unsloth DPOTrainer Patch"))
code2 = '''from unsloth import FastLanguageModel, PatchDPOTrainer
from unsloth import is_bfloat16_supported
import torch

# This MUST be called before importing DPOTrainer
PatchDPOTrainer()
'''
nb.cells.append(nbf.v4.new_code_cell(code2))

nb.cells.append(nbf.v4.new_markdown_cell("## 🧠 Step 3: Load Model & SFT Adapter\nWe load the base model, but point Unsloth directly to your SFT adapter. Unsloth will automatically load the base model and apply the PEFT adapter."))
code3 = '''# --- CONFIGURATION ---
SFT_ADAPTER_PATH = "/kaggle/input/your-sft-adapter-dataset" # Update this to your SFT adapter path

max_seq_length = 8192

# Load the SFT adapter (which automatically loads the Nemotron base model)
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = SFT_ADAPTER_PATH,
    max_seq_length = max_seq_length,
    dtype = None, # Auto detection
    load_in_4bit = False, # Set to True if you run out of VRAM, but competition prefers BF16
)
'''
nb.cells.append(nbf.v4.new_code_cell(code3))

nb.cells.append(nbf.v4.new_markdown_cell("## 📊 Step 4: Load and Format DPO Dataset\nDPO requires `prompt`, `chosen`, and `rejected` keys. We must apply the chat template to the prompt, and add EOS tokens to the chosen/rejected responses."))
code4 = '''from datasets import load_dataset

# Load your prepared DPO dataset
DPO_DATASET_PATH = "/kaggle/input/your-dpo-dataset/dpo_dataset.jsonl"
dataset = load_dataset("json", data_files=DPO_DATASET_PATH, split="train")

SYSTEM_PROMPT = """You are an expert pattern recognition solver competing in a reasoning challenge.

You will be given a puzzle from Alice's Wonderland where a secret transformation rule converts inputs to outputs.

Your approach MUST follow these steps inside <think> tags:
1. HYPOTHESIZE: Study each input-output example and state the rule clearly
2. VERIFY: Apply your rule to every example to confirm it holds
3. APPLY: Use the confirmed rule on the test input

Your final answer MUST be inside \\boxed{} and nothing after it.

Format:
<think>
HYPOTHESIZE: ...
VERIFY: ...
APPLY: ...
</think>
\\boxed{your_answer}"""

def format_dpo_pair(example):
    # Format the prompt using the Chat Template
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": example["prompt"]}
    ]
    prompt_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    
    # Append EOS token to responses
    chosen_text = example["chosen"] + tokenizer.eos_token
    rejected_text = example["rejected"] + tokenizer.eos_token
    
    return {
        "prompt": prompt_text,
        "chosen": chosen_text,
        "rejected": rejected_text,
    }

print(f"Loaded {len(dataset)} DPO pairs.")
dataset = dataset.map(format_dpo_pair)
print("Formatting complete!")
'''
nb.cells.append(nbf.v4.new_code_cell(code4))

nb.cells.append(nbf.v4.new_markdown_cell("## 🏋️‍♂️ Step 5: Configure DPOTrainer and Train\nDPO learning rates should be substantially lower than SFT (e.g., 5e-6)."))
code5 = '''from trl import DPOTrainer
from transformers import TrainingArguments

dpo_trainer = DPOTrainer(
    model = model,
    ref_model = None, # Unsloth automatically handles reference model for PEFT
    args = TrainingArguments(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        warmup_ratio = 0.1,
        num_train_epochs = 1,
        learning_rate = 5e-6, # Very low learning rate for DPO
        fp16 = not is_bfloat16_supported(),
        bf16 = is_bfloat16_supported(),
        logging_steps = 10,
        optim = "adamw_8bit",
        weight_decay = 0.0,
        lr_scheduler_type = "linear",
        seed = 42,
        output_dir = "dpo_outputs",
        report_to = "none",
    ),
    beta = 0.1, # DPO beta parameter (temperature for the KL penalty)
    train_dataset = dataset,
    tokenizer = tokenizer,
    max_length = max_seq_length,
    max_prompt_length = 4096,
)

print("Starting DPO Training...")
dpo_trainer.train()
'''
nb.cells.append(nbf.v4.new_code_cell(code5))

nb.cells.append(nbf.v4.new_markdown_cell("## 💾 Step 6: Save the DPO-Optimized LoRA Adapter"))
code6 = '''# Save the adapter
OUTPUT_DIR = "dpo_adapter_output"
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print(f"DPO adapter saved to {OUTPUT_DIR}")
'''
nb.cells.append(nbf.v4.new_code_cell(code6))

# Write the notebook
output_path = 'c:/Users/barad/Desktop/Kaggle/nvidia-nemotron-model-reasoning-challenge/Mywork/create_dpo_nb.py'
with open('c:/Users/barad/Desktop/Kaggle/nvidia-nemotron-model-reasoning-challenge/Mywork/kaggle-dpo-finetuning.ipynb', 'w', encoding='utf-8') as f:
    nbf.write(nb, f)
print('DPO Notebook generated successfully!')
