import nbformat as nbf

nb = nbf.v4.new_notebook()

nb.cells.append(nbf.v4.new_markdown_cell("# 🚀 vLLM Inference with LoRA Adapter for Iterative SFT\nThis notebook loads the Nemotron base model alongside your fine-tuned LoRA adapter. It evaluates the model on the full 9,500 problems and generates a comprehensive output CSV containing the model's reasoning, answers, and correctness."))

nb.cells.append(nbf.v4.new_markdown_cell('## 📥 Step 1: Environment Setup & Load Model with LoRA Support'))

code1 = '''import os
import zipfile
import kagglehub
from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest

# Set Triton and Transformers flags for offline execution
os.environ["TRANSFORMERS_NO_TF"] = "1"
os.environ["TRANSFORMERS_NO_FLAX"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
os.environ["TRITON_PTXAS_PATH"] = "/tmp/triton/backends/nvidia/bin/ptxas"

MODEL_PATH = kagglehub.model_download("metric/nemotron-3-nano-30b-a3b-bf16/transformers/default")

# --- ADAPTER CONFIGURATION ---
# Set to True if loading from a .zip file (e.g., notebook output)
# Set to False if loading from a direct folder (e.g., Kaggle Dataset)
LOAD_FROM_ZIP = True

if LOAD_FROM_ZIP:
    ADAPTER_ZIP_PATH = "/kaggle/input/notebooks/huikang/tinker-submission-notebook/submission.zip" # <--- UPDATE THIS
    ADAPTER_PATH = "/tmp/lora_adapter"
    os.makedirs(ADAPTER_PATH, exist_ok=True)
    print(f"Extracting adapter from {ADAPTER_ZIP_PATH}...")
    with zipfile.ZipFile(ADAPTER_ZIP_PATH, "r") as zf:
        zf.extractall(ADAPTER_PATH)
else:
    # Path to the directory containing adapter_config.json and adapter_model.safetensors
    ADAPTER_PATH = "/kaggle/input/your-lora-adapter-dataset" # <--- UPDATE THIS

print(f"Using Base Model: {MODEL_PATH}")
print(f"Using extracted LoRA Adapter: {ADAPTER_PATH}")

# Initialize vLLM Engine WITH LoRA enabled
llm = LLM(
    model=str(MODEL_PATH),
    tensor_parallel_size=1,
    max_num_seqs=64,
    gpu_memory_utilization=0.85,
    dtype="auto",
    max_model_len=8192,
    trust_remote_code=True,
    enable_lora=True,     # <--- ENABLED
    max_lora_rank=32      # <--- LoRA rank
)
'''
nb.cells.append(nbf.v4.new_code_cell(code1))

nb.cells.append(nbf.v4.new_markdown_cell('## 💬 Step 2: Define Prompts and Chat Formatting'))

code2 = '''SYSTEM_PROMPT = """You are an expert pattern recognition solver competing in a reasoning challenge.

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

def build_prompt(puzzle_text: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": puzzle_text}
    ]
'''
nb.cells.append(nbf.v4.new_code_cell(code2))

nb.cells.append(nbf.v4.new_markdown_cell('## 📁 Step 3: Load the inference_dataset.csv'))

code3 = '''import pandas as pd

# --- CONFIGURATION: Set to an integer (e.g. 10) for testing, or None for full dataset ---
MAX_SAMPLES = 10

# Load the dataset we prepared locally
data_path = "inference_dataset.csv"
print(f"Loading dataset from: {data_path}")
df = pd.read_csv(data_path, dtype=str)

if MAX_SAMPLES is not None:
    df = df.head(MAX_SAMPLES).copy()
    print(f"Sampling {MAX_SAMPLES} rows for testing...")

# Cast the boolean column properly
df['was_solved_in_training'] = df['was_solved_in_training'] == 'True'

print(f"Loaded {len(df)} problems.")
print(f"Solved in training: {df['was_solved_in_training'].sum()}")
print(f"Unsolved in training: {len(df) - df['was_solved_in_training'].sum()}")
'''
nb.cells.append(nbf.v4.new_code_cell(code3))

nb.cells.append(nbf.v4.new_markdown_cell('## 🧪 Step 4: Test Single Inference (Raw Output)'))

code_single = '''# Grab the first prompt from the dataset
test_prompt = df.iloc[0]["prompt"]
print("--- TEST PROMPT ---")
print(test_prompt)
print("\\n--- GENERATING ---")

messages = build_prompt(test_prompt)
tokenizer = llm.get_tokenizer()
input_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

sampling_params = SamplingParams(
    temperature=0.0,
    top_p=1.0,
    max_tokens=7680
)

# Run a single generation
test_output = llm.generate(
    [input_text], 
    sampling_params,
    lora_request=LoRARequest("adapter", 1, ADAPTER_PATH)
)

print("\\n--- RAW MODEL OUTPUT ---")
print(test_output[0].outputs[0].text)
'''
nb.cells.append(nbf.v4.new_code_cell(code_single))

nb.cells.append(nbf.v4.new_markdown_cell('## 🚀 Step 5: Run Batch Inference with LoRA'))

code4_prep = '''# Print the very first generated prompt for verification
tokenizer = llm.get_tokenizer()
first_messages = build_prompt(df.iloc[0]["prompt"])
first_input_text = tokenizer.apply_chat_template(first_messages, tokenize=False, add_generation_prompt=True)
print("--- FIRST BATCH PROMPT (Raw Text) ---")
print(first_input_text)
'''
nb.cells.append(nbf.v4.new_code_cell(code4_prep))

code4 = '''print(f"Preparing prompts for {len(df)} examples...")
tokenizer = llm.get_tokenizer()
prompts = []
for idx, row in df.iterrows():
    messages = build_prompt(row["prompt"])
    input_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    prompts.append(input_text)

sampling_params = SamplingParams(
    temperature=0.0,
    top_p=1.0,
    max_tokens=7680
)

print(f"Running batch generation with LoRA...")
# Pass the LoRA request to the generate function
outputs = llm.generate(
    prompts, 
    sampling_params,
    lora_request=LoRARequest("adapter", 1, ADAPTER_PATH)
)
print("Batch inference complete!")
'''
nb.cells.append(nbf.v4.new_code_cell(code4))

nb.cells.append(nbf.v4.new_markdown_cell('## 📊 Step 6: Parse Outputs & Calculate Correctness'))

code5 = '''import re

def extract_boxed_content(text):
    if not text:
        return "NOT_FOUND"
    
    # Find 'boxed{' with optional backslashes and spaces
    match = re.search(r"boxed\s*\{", text)
    if not match:
        return "NOT_FOUND"
    
    start_idx = match.end()
    brace_count = 1
    end_idx = start_idx
    
    for i in range(start_idx, len(text)):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            
        if brace_count == 0:
            end_idx = i
            break
            
    if brace_count == 0:
        return text[start_idx:end_idx].strip()
    
    # If unclosed, just return everything after it
    return text[start_idx:].strip()

def parse_model_output(output_text):
    thought = ""
    answer_raw = output_text
    
    if "</think>" in output_text:
        parts = output_text.split("</think>", 1)
        if "<think>" in parts[0]:
            sub_parts = parts[0].split("<think>", 1)
            thought = sub_parts[1].strip() if len(sub_parts) > 1 else sub_parts[0].strip()
        else:
            thought = parts[0].strip()
        answer_raw = parts[1].strip()
    
    final_ans = extract_boxed_content(answer_raw)
    return thought, final_ans

results = []
for i, out in enumerate(outputs):
    raw_text = out.outputs[0].text
    thought, model_answer = parse_model_output(raw_text)
    
    original_answer = str(df.iloc[i]["original_answer"]).strip()
    is_correct = (model_answer == original_answer)
    
    results.append({
        "id": df.iloc[i]["id"],
        "category": df.iloc[i]["category"],
        "prompt": df.iloc[i]["prompt"],
        "model_thought": thought,
        "model_answer": model_answer,
        "original_answer": original_answer,
        "was_solved_in_training": df.iloc[i]["was_solved_in_training"],
        "is_correct_now": is_correct
    })

df_results = pd.DataFrame(results)

# Calculate summary stats
total_acc = df_results["is_correct_now"].mean() * 100
solved_acc = df_results[df_results["was_solved_in_training"]]["is_correct_now"].mean() * 100
unsolved_acc = df_results[~df_results["was_solved_in_training"]]["is_correct_now"].mean() * 100

print(f"\\n--- RESULTS ---")
print(f"Overall Accuracy: {total_acc:.2f}%")
print(f"Accuracy on PREVIOUSLY SOLVED problems: {solved_acc:.2f}%")
print(f"Accuracy on UNKNOWN/NEW problems: {unsolved_acc:.2f}%")

print(f"\\n--- ACCURACY BY CATEGORY ---")
cat_acc = df_results.groupby('category')['is_correct_now'].mean() * 100
for cat, acc in cat_acc.items():
    print(f"{cat}: {acc:.2f}%")

# Save detailed results
out_file = "inference_results.csv"
df_results.to_csv(out_file, index=False)
print(f"\\nDetailed results saved to {out_file}")
'''
nb.cells.append(nbf.v4.new_code_cell(code5))

# Write to file
with open('c:/Users/barad/Desktop/Kaggle/nvidia-nemotron-model-reasoning-challenge/Mywork/vllm_infer_lora.ipynb', 'w', encoding='utf-8') as f:
    nbf.write(nb, f)
print('Notebook created successfully!')
