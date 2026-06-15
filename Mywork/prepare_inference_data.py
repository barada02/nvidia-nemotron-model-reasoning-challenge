import pandas as pd
import json
import os
from pathlib import Path

def main():
    base_dir = Path("c:/Users/barad/Desktop/Kaggle/nvidia-nemotron-model-reasoning-challenge")
    train_csv_path = base_dir / "nemotron" / "train.csv"
    problems_jsonl_path = base_dir / "nemotron" / "problems.jsonl"
    output_csv_path = base_dir / "Mywork" / "inference_dataset.csv"

    print(f"Loading organizer's training data from {train_csv_path}...")
    try:
        df_train = pd.read_csv(train_csv_path)
    except FileNotFoundError:
        print(f"Error: Could not find {train_csv_path}")
        return

    print(f"Loading metadata from {problems_jsonl_path}...")
    problem_status = {}
    try:
        with open(problems_jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    pid = data.get("id")
                    status = data.get("status")
                    # If status is rule_found, it means it was solved and is in training data
                    problem_status[pid] = (status == "rule_found")
    except FileNotFoundError:
        print(f"Error: Could not find {problems_jsonl_path}")
        return

    # Map the status back to the dataframe
    df_train['was_solved_in_training'] = df_train['id'].map(lambda x: problem_status.get(x, False))
    
    # Rename answer to original_answer to prevent confusion during inference
    df_train.rename(columns={'answer': 'original_answer'}, inplace=True)
    
    # Select columns we care about
    df_out = df_train[['id', 'prompt', 'original_answer', 'was_solved_in_training']]
    
    # Save the dataset
    print(f"Saving inference dataset to {output_csv_path}...")
    os.makedirs(output_csv_path.parent, exist_ok=True)
    df_out.to_csv(output_csv_path, index=False)
    
    # Print stats
    total = len(df_out)
    solved = df_out['was_solved_in_training'].sum()
    unsolved = total - solved
    
    print("\nDataset generation complete!")
    print("=" * 40)
    print(f"Total problems:    {total}")
    print(f"Solved (in SFT):   {solved}")
    print(f"Unsolved:          {unsolved}")
    print("=" * 40)

if __name__ == "__main__":
    main()
