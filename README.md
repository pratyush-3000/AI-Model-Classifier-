# AI-Model-Classifier

CSCI 544 (Applied NLP, USC), Team 10. The project classifies a text as **human**, as a **specific AI model** (with a vendor roll-up), or as **AI but unattributable** (an open-set class for models that weren't in training). It tests whether attribution lowers false positives on human text compared with a plain binary AI detector.

## Start here

| What you need | File |
|---|---|
| Train / val / test data (13,200 rows: 10 models + human, 1,200 prompts) | `data/4_final_dataset/dataset_13200_ai12000_human1200.csv` |
| Unseen-model test set (8 models × 127 test prompts, 1,016 rows) | `data/4_final_dataset/ai_responses_unseen_test_8x127_2026-09-28_1928.csv` |
| Column descriptions and split counts | `data/4_final_dataset/README.md` |
| Latest sanity-check report | `reports/dataset_check_2026-09-30.md` |

```python
import pandas as pd
df = pd.read_csv("data/4_final_dataset/dataset_13200_ai12000_human1200.csv")
unseen = pd.read_csv("data/4_final_dataset/ai_responses_unseen_test_8x127_2026-09-28_1928.csv")
train, val, test = (df[df.split == s] for s in ("train", "val", "test"))
```

Splits are per prompt: all 11 answers to a prompt are in the same split. Keep it that way in any cross-validation (use `GroupKFold` on `prompt_id`).

## Classes

- **Training models (10):** claude-haiku-4-5, claude-opus-4-6, gpt-5.5, gpt-5.6-terra, gemini-3.1-pro-preview, gemini-3.8-flash, llama-3.1-8b, llama-3.3-70b, qwen3-14b, qwen3.8-27b, plus `human`.
- **Unseen test models (8):** claude-opus-5-5, gpt-6-astra, gemini-2.5-pro, gemma-4-12b, gemma-4-31b, muse-spark-1.3, muse-glimmer-30b, mistral-small-3.2-24b.
- **Test-set scoring has two levels.** At the model level, every unseen model's correct label is "AI, unattributable". At the vendor level, Opus 5.5 → anthropic, GPT-6 Astra → openai, Gemini 2.5 Pro and Gemma → google, Muse → meta, and Mistral → unknown (no Mistral model in training).

## Things to know before modeling

- **Formatting leaks the label.** Some human sources lost their newlines, Claude uses em-dashes heavily, and Opus 5.5 almost never does. Use `answer_strict` (or `answer_wordsonly`) for the main runs, and `answer_clean` only as the "with formatting" comparison.
- **Length leaks the label.** Local models run shorter than frontier models; Opus 5.5 runs longer than Opus 4.6. Fixed-size windows or truncation keep the classifier from learning length.
- **AI:human is 10:1.** Use class weights or balanced sampling for the human-vs-AI decision.
- **Trivial baseline to beat:** a length + formatting-count classifier gets macro-F1 0.39 on the 11 classes (chance 0.09). See the report.

## Repo layout

```
data/
  4_final_dataset/        final files (use these)
  3_ai_outputs/           per-model generations and earlier merged versions
  1_human_data/           human answer versions, selection notes
    archived/             archived by the dataset team
    candidates_no_length_filter/   full candidate pools before the length cut (two are .csv.gz)
  MANIFEST.csv            every data file, its original Drive path and SHA-256
scripts/dataset_checks.py sanity checks (coverage, config, truncation, splits, trivial baseline)
reports/                  check reports
```

`data/` mirrors the team Google Drive folder ("CSCI 544 Project - Group 10") as of 2026-09-30. The Drive folder "2. AI Generated Prompts & Instructions" was empty and isn't included. Two candidate-pool files were over GitHub's 100 MB limit, so they're stored gzipped; `pd.read_csv` reads `.csv.gz` directly. `MANIFEST.csv` has the SHA-256 of every original file so you can confirm nothing changed.

`Select_1200_data.py`, `dataset_selection_notes.md` and `human_responses_1200.csv` at the repo root are from the repo's first upload and weren't changed.
