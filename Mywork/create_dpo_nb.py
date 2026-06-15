import nbformat as nbf
import os

nb = nbf.v4.new_notebook()

nb.cells.append(nbf.v4.new_markdown_cell("# 🎯 Direct Preference Optimization (DPO) with Unsloth\nThis notebook fine-tunes your existing SFT LoRA adapter using DPO. It loads the `dpo_dataset.jsonl` which contains `{prompt, chosen, rejected}` pairs, and trains the model to prefer the `chosen` logic trace over the `rejected` one."))

nb.cells.append(nbf.v4.new_markdown_cell("## 📦 Step 1: Install Dependencies"))
code1 = '''import subprocess
import os

subprocess.run(
    "pip install -q --no-index --find-links /kaggle/input/datasets/mayukh18/nemotron-packages/packages "
    "unsloth trl peft transformers datasets accelerate bitsandbytes",
    shell=True,
    check=True,
)
subprocess.run(
    "pip install -q /kaggle/input/datasets/mayukh18/nemotron-packages/causal_conv1d-1.6.1+cu12torch2.10cxx11abiTRUE-cp312-cp312-linux_x86_64.whl",
    shell=True,
    check=True,
)
subprocess.run(
    "pip install -q /kaggle/input/datasets/mayukh18/nemotron-packages/mamba_ssm-2.3.1+cu12torch2.10cxx11abiTRUE-cp312-cp312-linux_x86_64.whl",
    shell=True,
    check=True,
)
for _wd in ["/kaggle/input/datasets/llkh0a/rtx-wheels/wheels"]:
    if os.path.isdir(_wd):
        subprocess.run(
            [
                "pip",
                "install",
                "-q",
                "--no-index",
                "--find-links",
                _wd,
                "protobuf==6.33.5",
                "sentencepiece",
                "safetensors",
                "huggingface_hub",
            ],
            check=False,
        )
subprocess.run("rm -rf /kaggle/tmp/*", shell=True, check=False)
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

nb.cells.append(nbf.v4.new_markdown_cell("## 🔧 Step 3: Hardware Sanity Checks\nEnsure the GPU is correctly detected and that custom CUDA kernels (like `causal_conv1d`) are functioning as expected."))
code_sanity = '''import causal_conv1d
import mamba_ssm
import torch

cc = torch.cuda.get_device_capability(0)
print(f"GPU: {torch.cuda.get_device_name(0)}, sm_{cc[0] * 10 + cc[1]}")
print(f"torch={torch.__version__}, cuda={torch.version.cuda}")
print(f"mamba_ssm={mamba_ssm.__version__}, causal_conv1d={causal_conv1d.__version__}")
print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

from causal_conv1d import causal_conv1d_fn

_x = torch.randn(1, 512, 32, device="cuda", dtype=torch.bfloat16)+4e-3
_w = torch.randn(512, 4, device="cuda", dtype=torch.bfloat16)
causal_conv1d_fn(_x, _w, None, activation="silu")
print("causal_conv1d CUDA kernel: OK")
'''
nb.cells.append(nbf.v4.new_code_cell(code_sanity))

nb.cells.append(nbf.v4.new_markdown_cell("## 🧠 Step 4: Load Model & SFT Adapter\nWe load the base model, but point Unsloth directly to your SFT adapter. Unsloth will automatically load the base model and apply the PEFT adapter."))
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

nb.cells.append(nbf.v4.new_markdown_cell("## 📊 Step 5: Load and Format DPO Dataset\nDPO requires `prompt`, `chosen`, and `rejected` keys. We must apply the chat template to the prompt, and add EOS tokens to the chosen/rejected responses."))
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

nb.cells.append(nbf.v4.new_markdown_cell("## 🏋️‍♂️ Step 6: Configure DPOTrainer and Train\nDPO learning rates should be substantially lower than SFT (e.g., 5e-6)."))
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

nb.cells.append(nbf.v4.new_markdown_cell("## 📈 Step 7: Observability (Loss Plot)\nLet's plot the training loss from the `DPOTrainer` state."))
code_obs = '''import pandas as pd
import matplotlib.pyplot as plt

try:
    log_history = dpo_trainer.state.log_history
    df = pd.DataFrame(log_history)
    if 'loss' in df.columns:
        df_loss = df.dropna(subset=['loss'])
        plt.figure(figsize=(10,5))
        plt.plot(df_loss['step'], df_loss['loss'], label="Training Loss")
        if 'eval_loss' in df.columns:
            df_eval = df.dropna(subset=['eval_loss'])
            if not df_eval.empty:
                plt.plot(df_eval['step'], df_eval['eval_loss'], label="Eval Loss", marker='o')
        plt.title("DPO Training Loss")
        plt.xlabel("Steps")
        plt.ylabel("Loss")
        plt.legend()
        plt.grid(True)
        plt.show()
    else:
        print("No loss data found in log history.")
except Exception as e:
    print(f"Could not plot logs: {e}")
'''
nb.cells.append(nbf.v4.new_code_cell(code_obs))

nb.cells.append(nbf.v4.new_markdown_cell("## 💾 Step 8: Save & Package Adapter Weights\nSave the adapter outputs directly and bundle them into `submission.zip` so you can use it in your inference notebook."))
code7 = '''import os
import zipfile

OUTPUT_DIR = "."
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

adapter_files = [f for f in os.listdir(OUTPUT_DIR) if f.startswith("adapter")]
SUBMISSION_ZIP = "submission.zip"
with zipfile.ZipFile(SUBMISSION_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
    for fname in adapter_files:
        zf.write(os.path.join(OUTPUT_DIR, fname), fname)
        os.remove(os.path.join(OUTPUT_DIR, fname)) # Clean up unzipped files to save disk space

print(f"DPO adapter saved and zipped to {SUBMISSION_ZIP}!")
'''
nb.cells.append(nbf.v4.new_code_cell(code7))

# Write the notebook
output_path = 'c:/Users/barad/Desktop/Kaggle/nvidia-nemotron-model-reasoning-challenge/Mywork/create_dpo_nb.py'
with open('c:/Users/barad/Desktop/Kaggle/nvidia-nemotron-model-reasoning-challenge/Mywork/kaggle-dpo-finetuning.ipynb', 'w', encoding='utf-8') as f:
    nbf.write(nb, f)
print('DPO Notebook generated successfully!')
