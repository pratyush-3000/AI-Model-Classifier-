# Human Response Dataset - Selection Criteria

## Project purpose (why this dataset exists)
We collect **1,200 human-written question/answer pairs** across three domains
(400 explanatory + 400 technical + 400 long-form). Each of the 1,200 questions
is later sent to **7 different AI models** (GPT, Gemini, Claude, etc.) with the
same standardized prompt. That gives 7 x 1,200 AI answers + the 1,200 human
answers = **9,600 answers total**. We then train a **classifier** that reads a
piece of text and predicts who wrote it (a human, or which AI model).

Because of that goal, the filters below all serve two aims:
1. **Every question must be answerable by any AI on its own** — no references to
   images, attachments, other posts, or hidden context.
2. **Human answers must not carry source-specific "tells"** (Reddit tags, edit
   notes, tokenization quirks). Otherwise the classifier could cheat by
   detecting the artifact instead of learning the actual writing style.

## General
- **Output:** `human_responses_1200.csv`, 3 categories x 400 = **1,200 rows**.
- **seed=42**; reproducible random sampling per category / task / site.
- `answer_len`: character count including spaces and line breaks. `answer_words`: `len(answer.split())`.
- No summarizing, truncating, or grammar-fixing of the original text. Only technical answers are converted from HTML to plain text.
- `human` is a source-based label; it does not individually certify that each item was written by a non-AI author.

## Shared Quality Gates (applied to every domain)
Every candidate must pass these rules, so the text is clean enough to send straight to an AI model via the Batch API.

| Gate | Function | What it drops |
| --- | --- | --- |
| Completeness | `is_low_quality` | Answers that don't start with a capital/quote or don't end with sentence punctuation (`. ! ? " ' ) ] : ...`) — i.e. cut off mid-thought. |
| Artifacts | `ARTIFACTS` | URLs/links, `_URL_` tokens, `[deleted]`/`[removed]`, `Edit:`/`Update:` markers, strikethrough (`~~`), code fences, replacement char. |
| Forum noise | `ANSWER_FORUM_NOISE` | Answers referencing other posts/threads/users: `@OP`, `@Username` mentions, `/u/name`, `/r/sub`, "other answers", "this thread", "top comment", "as others mentioned". |
| CSV safety | `LEADING_BAD_CHAR` | Any question/answer starting with `=` `+` `-` `@` `#` (spreadsheets treat these as formulas — this is what created the `#NAME?` cells). |
| Duplicates | - | No duplicate ID and no duplicate answer (normalized); explanatory/technical also forbid duplicate questions. |

---

## Explanatory - ELI5 (400 rows)
**Source:** https://huggingface.co/datasets/sentence-transformers/eli5 (pair/train)

**Example row:**
> **Q:** How long does salt put down on roads damage your vehicle?
> **A:** Yes, and yes. The salt will start to corrode the car immediately but will continue to corrode it as long as it stays on or gets saturated. Eventually the brine will drip off the vehicle and the process stops...

### Selection funnel
| Step | Remaining | Removed at this step |
| --- | ---: | ---: |
| Raw ELI5 pairs (pair/train) | 325,475 | - |
| After answer length filter (300-500 chars) | 87,553 | 237,922 |
| After answer quality gates (artifacts, completeness, forum-noise, CSV-safety) | 64,168 | 23,385 |
| After clear-question gate on the question | 61,042 | 3,126 |
| After removing duplicate questions and answers | 60,876 | 166 |
| Final random sample (seed=42) | 400 | 60,476 |

### Filter details
- Answers pass all shared quality gates (completeness, artifacts, forum-noise, CSV-safety).
- **Clear-question gate** (`is_clear_question`): the question must read as a real question or an explicit request, so it works as a standalone AI prompt. It must contain a `?` **or** start with one of: `explain, describe, tell, give, list, compare, contrast, define, clarify, walk, break down, how, why, what, when, where, who, which, whose, whom, can, could, would, should, does, do, is, are, was, were, if, eli5`.
  - Rejected: bare topic titles (`"space, radio and speed"`), thread/podcast titles (`"AskHistorians Podcast Episode 007"`), and context-missing prompts (`"...more details inside"`, `"help me convince"`, personal-heritage threads).
- **Self-contained gate** (`is_self_contained`): drops questions that point to context an AI cannot see (a quoted paper/passage, an attached file, or an inline ASCII diagram), so every prompt can be answered on its own.
- Excluded questions under 15 characters and duplicate questions (by case/whitespace); selected 400 with seed=42.
- IDs are assigned sequentially (`eli5_0000` ...) after the seeded draw.

---

## Technical - StackExchange / H4 structured distribution (400 rows)
**Source:** https://huggingface.co/datasets/HuggingFaceH4/stack-exchange-preferences
- **What "H4 structured distribution" means:** this is a version of StackExchange
  released by HuggingFace's H4 team. Instead of one merged text blob, it stores
  each item as **1 question + several candidate answers, each with a preference
  score (`pm_score`)**. We use it because the questions and answers are already
  cleanly separated (the Common Pile version merges question/comments/answers
  together, which is hard to split back into clean Q&A).
- Pinned revision: `c7bda74048748f55749cd663c3d8d1025a841fd9`
- The H4 dataset has 344 site folders total (including `.meta` communities and non-technical topics like cooking/gaming); we picked 4 technical sites relevant to our domain.
- Inspects all 7 shards of these 4 sites; this is not a full-StackExchange aggregation.

**Example row:**
> **Q:** I spoke with a guy who claimed that he's working on a GPS-system that is going to be accurate to the centimeter. Is this even possible? What is the limiting factor...?
> **A:** You can use software to compare the readings from 2 (or more) matched GPS receivers which are looking at the same set of satellites to cancel out any differences in (the many sources of) absolute errors...

### Selection funnel (summed over the 4 sites)
| Step | Remaining | Removed at this step |
| --- | ---: | ---: |
| Raw questions across the 4 sites (all shards) | 87,032 | - |
| After keeping questions dated before the cutoff | 86,449 | 583 |
| After question HTML-clean + length filter (unique questions) | 33,188 | 53,261 |
| Questions with >=1 usable answer (answer gates applied) | 4,942 | 28,246 |
| Final sample: 100 pairs x 4 sites (seed=42) | 400 | 4,542 |

### Per-site breakdown
| Site | Topic | Raw questions | Eligible Q&A | Sampled |
| --- | --- | ---: | ---: | ---: |
| `cs.stackexchange.com` | Computer Science (theory, algorithms, complexity) | 11,314 | 228 | 100 |
| `dba.stackexchange.com` | Database Administrators (SQL, DB design, tuning) | 31,109 | 639 | 100 |
| `networkengineering.stackexchange.com` | Network Engineering (routing, switching, protocols) | 6,648 | 566 | 100 |
| `softwareengineering.stackexchange.com` | Software Engineering (design, architecture, practices) | 37,961 | 3,509 | 100 |

### Filter details
- Question posted before 2022-11-30; answer/edit dates are unavailable, so we cannot guarantee the same timeframe.
- Question 40-2,000 characters; individual answers 300-500 characters after HTML conversion.
- **HTML conversion** (`clean_technical`) rejects Q&A with links, images, code blocks, tables, quote blocks, or scripts, and answers with math markup (`$`, `\(`, `\[`).
- **Missing-context gate** (`MISSING_CONTEXT`): drops answers needing context we do not keep, e.g. "as in the title", "see above/below", "following code/image", "other/previous/accepted answer", "as others mentioned".
- **Self-contained gate** (`is_self_contained`): drops questions that quote/point to an external paper, attachment, or inline ASCII diagram the AI cannot see.
- Answers also pass all shared quality gates.
- Preserves inline code / emphasis text; two line breaks between paragraphs, internal whitespace normalized.
- Among eligible answers with `pm_score >= 2`: accepted first -> higher pm_score -> smaller answer ID.
- `pm_score` is H4's converted preference score, not the original upvote count.
- One answer per question; after excluding duplicate IDs/questions/answers, 100 selected per site.
- Original URLs are kept in the CSV; authors/profiles/original IDs are kept in `data/technical_provenance.jsonl`.
- License: CC BY-SA 4.0 (H4 dataset card); for question authors, only the provided metadata is preserved.

---

## Long-form - WritingPrompts (400 rows)
**Source:** https://huggingface.co/datasets/euclaise/writingprompts (r/WritingPrompts)
- Each row is a creative-writing **prompt** (question) + a human-written **story** (answer).
- WritingPrompts has tens of thousands of unique prompts, so all **400 long-form questions are distinct**.
- Genre is creative fiction, clearly different from ELI5 (explanatory) and StackExchange (technical).

**Example row:**
> **Q (prompt):** You decide to go off the grid, to disappear, to cut ties with everyone. How would you do it?
> **A (story):** I looked up at the house, one last time. A sense of sadness threatened to overwhelm me. No. I couldn't beat myself up about it. This was the only option. This, or death...

### Selection funnel
| Step | Remaining | Removed at this step |
| --- | ---: | ---: |
| Raw WritingPrompts rows (train shards) | 272,600 | - |
| After keeping only [WP] plain writing prompts | 230,785 | 41,815 |
| After story length filter (300-500 words) | 60,414 | 170,371 |
| After story quality gates (artifacts, completeness, Reddit-noise) | 45,682 | 14,732 |
| After prompt gates (min length, unsafe-content filter) | 41,933 | 3,749 |
| After removing duplicate prompts and stories | 27,543 | 14,390 |
| Final random sample (seed=42) | 400 | 27,143 |

### Filter details
- `question` = the writing prompt (with the `[WP]` tag removed); `answer` = the human story.
- **Detokenization** (`detokenize`): the raw dump is tokenized (quotes as `` `` `` / `''`, split contractions like "do n't", spaces before punctuation). We restore the normal surface form so the human text does not carry a tell-tale artifact the AI answers lack (this fixes wording surface only, not content).
- **WP-tag gate:** keep only plain `[WP]` prompts; drop `[IP]` (image), `[EU]` (established universe), etc. that need context an AI cannot see.
- Story length filtered to 300-500 words (matches the length we ask the AI models for).
- **Reddit-noise gate** (`REDDIT_NOISE`): drops stories containing Reddit meta-text such as "Part 2 on my profile", "link in bio", "Edit:", "/r/sub", "feedback welcome", or self-promo/links. Leaving these in would let the classifier cheat by spotting Reddit artifacts instead of writing style.
- **Markdown-layout gate** (`STORY_MARKDOWN`): drops stories with heading lines ("# Title #"), horizontal rules ("---"), or bullet markers, since that layout is an artifact no plain AI answer would have.
- **Unsafe-content gate** (`UNSAFE_PROMPT`): drops prompts about explicit violence, sexual abuse, self-harm, terrorism, or hate, so the AI models actually answer instead of refusing.
- Stories also pass the shared quality gates (artifacts, completeness); prompts must be >= 40 characters.
- Every prompt is unique (`prompt_group` = the row id).
- License: Reddit user-generated content (r/WritingPrompts) - cite as academic use.

---

## AI Generation Protocol (for the team - please follow exactly)
Every teammate sends the **same** prompt for their model, so the classifier
learns *model style*, not prompt differences. The only things that change
between teammates are (a) which model answers and (b) the `{question}` text.
**Do not** paraphrase these prompts, add a persona, or tweak wording per model.

**Prompt templates (one per domain, identical for every model):**

Explanatory (domain = `explanatory`):
```
Answer the following question in about 300-500 characters (roughly 3-6 sentences).
Write a single clear explanation in plain prose. Do not use lists, headings, bullet points, or markdown.

Question: {question}
```

Technical (domain = `technical`):
```
Answer the following technical question in about 300-500 characters (roughly 3-6 sentences).
Write a single clear answer in plain prose. Do not use lists, headings, bullet points, code blocks, or markdown.

Question: {question}
```

Long-form (domain = `long-form`):
```
Write a short story of about 300-500 words based on the following prompt.
Write plain prose only. Do not add a title, headings, bullet points, or markdown.

Prompt: {question}
```

**Keep these identical across all models and teammates:**
- **System message:** empty (or the same minimal text everywhere). No personas.
- **Generation params:** one shared setting for every model - `temperature = 0.9`, `max_tokens` ~800 (fits 500 words). If a reasoning model does not accept `temperature`, note the exception.
- **Only send the question.** Never show the model a human answer.

**After you get the answers:**
- Keep the question `id` with each answer so all sources line up (every question is unique, one answer per question).
- Record the model name/version (e.g. `gpt-5.5-non-reasoning`) and any retries.
- Check the length is in range and strip any leftover markdown; regenerate anything empty, refused, or out of range.
- Reuse each question's train/validation/test split (`prompt_group`) so the same question never crosses splits.

---

## Validation (of this human dataset)
- Before writing the CSV, `validate()` fails loudly if anything is wrong: 400 per category, correct columns, all 1,200 IDs/questions/answers unique, no missing/empty cells, stored length/word counts match the text, every answer passes the completeness gate, no cell starts with `= + - @ #`, and the domain-specific gates above all hold.
- These are rule-based filters; the set was not manually reviewed for factuality/relevance.
- This script only builds the human data. It does NOT call any AI API - see the "AI Generation Protocol" section for that step.
