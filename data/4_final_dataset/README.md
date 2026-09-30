# Final Dataset (NLP544, Team 10)

## Files
- `dataset_13200_ai12000_human1200.csv`: main dataset, 13,200 rows
  - 12,000 AI answers (10 models × 1,200 prompts) + 1,200 human answers
  - one row per answer; every prompt has 11 rows (10 models + 1 human)
- `ai_responses_unseen_test_8x127_2026-09-28_1928.csv`: unseen-model test set, 1,016 rows (8 models × 127 test prompts)
- `answer_issues_by_prompt_2026-09-28_1933.csv`: known answer issues, listed per prompt
- `pmi_top_terms_2026-09-28_2010.csv` / `.txt`: PMI top terms per class (train split only)

## Main dataset columns
- `answer_id`: `<prompt_id>__<model>` or `<prompt_id>__human`
- `prompt_id`, `domain` (explanatory / technical / long-form), `question`
- `split`: train / val / test, set per prompt (all 11 answers to a prompt are in the same split, so no leakage)
- `label`: model name or `human`
- `is_human`: 1 = human, 0 = AI
- `vendor`: anthropic, openai, google, meta, alibaba, or `human`
- `source`: `ai` for model rows; dataset name for human rows (eli5, stackexchange_h4, writingprompts), with `source_url`
- Answer text, least to most processed:
  - `answer_raw`: as generated / as collected
  - `answer_clean`: LaTeX removed, whitespace fixed
  - `answer_clean_nodash`: + dashes normalized
  - `answer_clean_nonl`: + newlines removed
  - `answer_strict`: nodash + nonl + extra formatting stripped
  - `answer_wordsonly`: lowercase words only, no punctuation
- `answer_words`, `answer_len`: word and character counts
- Remaining columns are generation metadata (system prompt, max tokens, stop reason, batch id, local model settings). Blank for human rows.

## Counts
| split | AI | human |
|---|---|---|
| train | 9,580 | 958 |
| val | 1,150 | 115 |
| test | 1,270 | 127 |

- Each domain has 4,000 AI + 400 human rows.
- AI:human is 10:1. We should use balanced sampling or class weights for human-vs-AI training.

