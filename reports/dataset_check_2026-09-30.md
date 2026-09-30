# Dataset sanity report

## Flags
- ⚠️ qwen3.8-27b-q4_k_m: mixed `max_tokens` values (8192:1199; 16384:1)
- ⚠️ gpt-5.5 / technical: 25% of responses outside the word band
- ⚠️ gpt-5.6-terra / technical: 36% of responses outside the word band
- ⚠️ llama-3.1-8b-q4_k_m / explanatory: 15% of responses outside the word band
- ⚠️ llama-3.3-70b-q4_k_m / explanatory: 50% of responses outside the word band
- ⚠️ qwen3-14b-q4_k_m / explanatory: 60% of responses outside the word band
- ⚠️ qwen3-14b-q4_k_m / technical: 34% of responses outside the word band
- ⚠️ 4 AI rows match refusal patterns: {'gpt-5.5': 2, 'gpt-5.6-terra': 1, 'qwen3.8-27b-q4_k_m': 1}
- ⚠️ length/format-only baseline macro-F1 0.39 vs chance 0.09

## 1. Rows and prompt coverage

| class | explanatory | long-form | technical |
|---|---|---|---|
| claude-haiku-4-5 | 400 | 400 | 400 |
| claude-opus-4-6 | 400 | 400 | 400 |
| gemini-3.1-pro-preview | 400 | 400 | 400 |
| gemini-3.8-flash | 400 | 400 | 400 |
| gpt-5.5 | 400 | 400 | 400 |
| gpt-5.6-terra | 400 | 400 | 400 |
| human | 400 | 400 | 400 |
| llama-3.1-8b-q4_k_m | 400 | 400 | 400 |
| llama-3.3-70b-q4_k_m | 400 | 400 | 400 |
| qwen3-14b-q4_k_m | 400 | 400 | 400 |
| qwen3.8-27b-q4_k_m | 400 | 400 | 400 |

- Classes: 11; unique prompt_ids: 1200
- Prompts not covered by every class exactly once: **0**

## 2. Generation config per model (should be ONE value per cell)

| model | effort | temperature | max_tokens | system_prompt_version | is_reasoning | vendor |
|---|---|---|---|---|---|---|
| claude-haiku-4-5 |  |  | 1500:1200 | final-2026-09-20:1200 | False:1200 | anthropic:1200 |
| claude-opus-4-6 | low:1200 |  | 4000:1200 | final-2026-09-20:1200 | True:1200 | anthropic:1200 |
| gemini-3.1-pro-preview | high:1200 | 1.0:1200 | 8192:1200 | final-2026-09-23:1200 | True:1200 | google:1200 |
| gemini-3.8-flash | low:1200 | 1.0:1200 | 8192:1200 | final-2026-09-23:1200 | True:1200 | google:1200 |
| gpt-5.5 | none:1200 |  | 1500:1200 | final-2026-09-22:1200 | False:1200 | openai:1200 |
| gpt-5.6-terra | medium:1200 |  | 4000:1200 | final-2026-09-22:1200 | True:1200 | openai:1200 |
| llama-3.1-8b-q4_k_m | none:1200 |  | 8192:1200 | final-2026-09-20:1200 | False:1200 | meta:1200 |
| llama-3.3-70b-q4_k_m | none:1200 |  | 8192:1200 | final-2026-09-20:1200 | False:1200 | meta:1200 |
| qwen3-14b-q4_k_m | none:1200 |  | 8192:1200 | final-2026-09-20:1200 | False:1200 | alibaba:1200 |
| qwen3.8-27b-q4_k_m | medium:1200 |  | 8192:1199; 16384:1 | final-2026-09-20:1200 | True:1200 | alibaba:1200 |

## 3. Truncation and length-band violations

| model | end_turn |
|---|---|
| claude-haiku-4-5 | 1200 |
| claude-opus-4-6 | 1200 |
| gemini-3.1-pro-preview | 1200 |
| gemini-3.8-flash | 1200 |
| gpt-5.5 | 1200 |
| gpt-5.6-terra | 1200 |
| llama-3.1-8b-q4_k_m | 1200 |
| llama-3.3-70b-q4_k_m | 1200 |
| qwen3-14b-q4_k_m | 1200 |
| qwen3.8-27b-q4_k_m | 1200 |

|  | % below band | % above band |
|---|---|---|
| claude-haiku-4-5 / explanatory | 0.00 | 0.80 |
| claude-haiku-4-5 / long-form | 0.00 | 0.00 |
| claude-haiku-4-5 / technical | 0.00 | 0.20 |
| claude-opus-4-6 / explanatory | 0.00 | 0.20 |
| claude-opus-4-6 / long-form | 0.00 | 0.00 |
| claude-opus-4-6 / technical | 0.00 | 0.20 |
| gemini-3.1-pro-preview / explanatory | 0.00 | 0.00 |
| gemini-3.1-pro-preview / long-form | 0.00 | 2.80 |
| gemini-3.1-pro-preview / technical | 0.00 | 2.00 |
| gemini-3.8-flash / explanatory | 0.00 | 0.00 |
| gemini-3.8-flash / long-form | 0.00 | 0.20 |
| gemini-3.8-flash / technical | 0.00 | 1.00 |
| gpt-5.5 / explanatory | 0.00 | 1.20 |
| gpt-5.5 / long-form | 0.00 | 0.50 |
| gpt-5.5 / technical | 0.00 | 24.80 |
| gpt-5.6-terra / explanatory | 0.20 | 1.20 |
| gpt-5.6-terra / long-form | 1.00 | 3.00 |
| gpt-5.6-terra / technical | 0.00 | 36.20 |
| llama-3.1-8b-q4_k_m / explanatory | 14.80 | 0.50 |
| llama-3.1-8b-q4_k_m / long-form | 0.80 | 0.50 |
| llama-3.1-8b-q4_k_m / technical | 9.80 | 0.00 |
| llama-3.3-70b-q4_k_m / explanatory | 49.80 | 0.00 |
| llama-3.3-70b-q4_k_m / long-form | 0.80 | 0.00 |
| llama-3.3-70b-q4_k_m / technical | 1.20 | 0.00 |
| qwen3-14b-q4_k_m / explanatory | 60.00 | 0.00 |
| qwen3-14b-q4_k_m / long-form | 1.50 | 1.20 |
| qwen3-14b-q4_k_m / technical | 34.00 | 0.00 |
| qwen3.8-27b-q4_k_m / explanatory | 0.00 | 7.00 |
| qwen3.8-27b-q4_k_m / long-form | 0.00 | 1.50 |
| qwen3.8-27b-q4_k_m / technical | 0.00 | 8.50 |

| class | % not ending in punctuation |
|---|---|
| claude-haiku-4-5 | 0.10 |
| claude-opus-4-6 | 0.70 |
| gemini-3.1-pro-preview | 0.00 |
| gemini-3.8-flash | 0.00 |
| gpt-5.5 | 0.20 |
| gpt-5.6-terra | 0.20 |
| human | 0.00 |
| llama-3.1-8b-q4_k_m | 0.00 |
| llama-3.3-70b-q4_k_m | 0.00 |
| qwen3-14b-q4_k_m | 0.10 |
| qwen3.8-27b-q4_k_m | 0.10 |

## 4. Word counts per class x domain (median [IQR])

| class | explanatory | long-form | technical |
|---|---|---|---|
| claude-haiku-4-5 | 124 [120–129] | 184 [177–191] | 140 [135–145] |
| claude-opus-4-6 | 126 [123–130] | 183 [180–187] | 140 [135–145] |
| gemini-3.1-pro-preview | 132 [130–134] | 210 [204–214] | 162 [158–165] |
| gemini-3.8-flash | 129 [126–131] | 197 [193–202] | 159 [155–162] |
| gpt-5.5 | 129 [125–132] | 194 [187–201] | 163 [156–169] |
| gpt-5.6-terra | 128 [123–131] | 191 [180–200] | 165 [156–175] |
| human | 131 [113–150] | 210 [155–262] | 157 [123–205] |
| llama-3.1-8b-q4_k_m | 109 [104–117] | 175 [167–185] | 128 [119–137] |
| llama-3.3-70b-q4_k_m | 100 [97–103] | 175 [167–182] | 129 [125–134] |
| qwen3-14b-q4_k_m | 97 [90–103] | 182 [170–194] | 114 [107–120] |
| qwen3.8-27b-q4_k_m | 128 [121–134] | 192 [180–202] | 153 [145–163] |

## 5. Train/test split

- prompt_ids appearing in more than one split: **0**
- Split sizes (AI rows): train=9580, test=1270, val=1150
- Human file has no split column: assign human rows the split of their prompt_id.

## 6. Refusals, preambles, closings, markdown (% of rows)

| class | refusal | preamble | closing | md_header | md_bullet | md_bold | code_fence |
|---|---|---|---|---|---|---|---|
| claude-haiku-4-5 | 0.00 | 0.00 | 0.20 | 0.00 | 0.00 | 0.00 | 0.00 |
| claude-opus-4-6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| gemini-3.1-pro-preview | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| gemini-3.8-flash | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| gpt-5.5 | 0.20 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| gpt-5.6-terra | 0.10 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| human | 0.20 | 0.30 | 0.80 | 0.00 | 0.00 | 0.00 | 0.00 |
| llama-3.1-8b-q4_k_m | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| llama-3.3-70b-q4_k_m | 0.00 | 0.00 | 0.20 | 0.00 | 0.00 | 0.00 | 0.00 |
| qwen3-14b-q4_k_m | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| qwen3.8-27b-q4_k_m | 0.10 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

## 7. Length/format-only baseline

- Macro-F1 using only length + formatting features (5-fold, grouped by prompt): **0.392** (chance ≈ 0.091)
- Human rows misclassified as some model: 35.2%
- This is the floor every real classifier must beat. If it is far above chance, report it — length/format is carrying signal and the formatting-stripped condition matters.

## 8. Long-form prompt diversity and near-duplicates

- Unique long-form question texts: **400** across 400 prompt_ids
- Within-class similarity to the nearest other essay on the same question (TF-IDF cosine):

| class |
|---|

