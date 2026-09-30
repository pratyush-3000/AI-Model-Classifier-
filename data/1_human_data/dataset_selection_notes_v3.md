# Human Response Dataset - Selection Criteria

How we collected **400 human answers from each of three domains**:
- 400 explanatory + 400 technical + 400 long-form = **1,200 rows** (`human_responses_1200.csv`)

## Basics
- **Answer length is unified across all domains: 100-300 words.** This range is the sweet spot: ELI5 answers are short (max ~230 words) and WritingPrompts stories are long (min ~100 words), so 100-300 is the only window where all three still yield 400 each.
- **seed=42** for reproducible sampling. Original text is never edited (only technical HTML is converted to plain text).
- Every answer is de-duplicated and all 1,200 questions are unique.

## Shared quality gates (every domain)
Each candidate answer/question must pass these, so the text is clean enough to send straight to an AI model:

| Gate | Drops |
| --- | --- |
| Completeness | Answers cut off mid-thought (don't start with a capital/quote or end with sentence punctuation). |
| Artifacts | URLs, `[deleted]`/`[removed]`, `Edit:` markers, code fences, etc. |
| Forum noise | References to other posts/users: `@OP`, `@name`, `/u/`, `/r/`, "other answers", "this thread". |
| CSV safety | Cells starting with `= + - @ #` (spreadsheets read these as formulas). |
| Duplicates | No duplicate id, question, or answer. |

Each section below shows the **selection funnel** (rows left after each filter) and the domain-specific gates.

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
| After answer length filter (100-300 words) | 94,979 | 230,496 |
| After answer quality gates (artifacts, completeness, forum-noise, CSV-safety) | 64,923 | 30,056 |
| After clear-question gate on the question | 60,566 | 4,357 |
| After removing duplicate questions and answers | 60,360 | 206 |
| Final random sample (seed=42) | 400 | 59,960 |

### Filter details
- All shared quality gates apply.
- **Clear-question gate:** the question must be a real question or request (has a `?` or starts with how/why/what/explain/describe/etc.). Rejects bare topic titles and thread/podcast titles.
- **Self-contained gate:** drops questions that point to something the AI can't see (a quoted paper, attachment, or ASCII diagram).
- IDs: `explanatory_0000` ... `explanatory_0399`.

---

## Technical - StackExchange (400 rows)
**Source:** https://huggingface.co/datasets/HuggingFaceH4/stack-exchange-preferences (HuggingFace H4 version)
- We use the **H4 version** because it keeps each item as 1 question + several scored answers, already cleanly separated into Q&A (the raw StackExchange dump merges questions/comments/answers together).
- Pinned revision `c7bda74048748f55749cd663c3d8d1025a841fd9` for reproducibility.
- We pull from **8 technical sites and take 50 each (8 x 50 = 400)**. At 100-300 words a single site wasn't enough, so we spread across 8 sites instead of 4.

**Example row:**
> **Q:** I spoke with a guy who claimed that he's working on a GPS-system that is going to be accurate to the centimeter. Is this even possible? What is the limiting factor...?
> **A:** You can use software to compare the readings from 2 (or more) matched GPS receivers which are looking at the same set of satellites to cancel out any differences in (the many sources of) absolute errors...

### Selection funnel (summed over the 8 sites)
| Step | Remaining | Removed at this step |
| --- | ---: | ---: |
| Raw questions across the 8 sites (all shards) | 212,151 | - |
| After keeping questions dated before the cutoff | 210,646 | 1,505 |
| After question HTML-clean + length filter (unique questions) | 74,770 | 135,876 |
| Questions with >=1 usable answer (answer gates applied) | 18,351 | 56,419 |
| Final sample: 50 pairs x 8 sites (seed=42) | 400 | 17,951 |

### Per-site breakdown
| Site | Topic | Raw questions | Eligible Q&A | Sampled |
| --- | --- | ---: | ---: | ---: |
| `cs.stackexchange.com` | Computer Science (theory, algorithms, complexity) | 11,314 | 508 | 50 |
| `dba.stackexchange.com` | Database Administrators (SQL, DB design, tuning) | 31,109 | 1,232 | 50 |
| `networkengineering.stackexchange.com` | Network Engineering (routing, switching, protocols) | 6,648 | 1,038 | 50 |
| `softwareengineering.stackexchange.com` | Software Engineering (design, architecture, practices) | 37,961 | 8,186 | 50 |
| `security.stackexchange.com` | Information Security (appsec, crypto, network security) | 29,088 | 4,775 | 50 |
| `datascience.stackexchange.com` | Data Science (ML, statistics, data processing) | 8,432 | 537 | 50 |
| `unix.stackexchange.com` | Unix & Linux (shell, system administration) | 79,819 | 1,713 | 50 |
| `dsp.stackexchange.com` | Signal Processing (DSP, filtering, transforms) | 7,780 | 362 | 50 |

### Filter details
- Question dated before 2022-11-30, 40-2,000 chars; answer 100-300 words after HTML->plain-text conversion.
- **HTML conversion** drops Q&A with links, images, code blocks, tables, quotes, or scripts (and math markup), keeping only clean prose.
- **Self-contained + missing-context gates:** drops answers that reference things we don't keep ("see above", "the following code", "accepted answer") and questions that point to an external paper/attachment/diagram.
- One answer per question, chosen by: accepted first, then higher `pm_score` (>= 2), then smaller id. Plus all shared gates.
- IDs: `technical_0000` ... `technical_0399`. Original site/question/answer IDs are kept in `source_url` and `data/technical_provenance.jsonl`.
- License: CC BY-SA 4.0.

---

## Long-form - WritingPrompts (400 rows)
**Source:** https://huggingface.co/datasets/euclaise/writingprompts (r/WritingPrompts)
- Each row is a creative-writing **prompt** (question) + a human-written **story** (answer). Genre is creative fiction, distinct from the other two domains.
- Tens of thousands of unique prompts, so all **400 questions are distinct**.

**Example row:**
> **Q (prompt):** You decide to go off the grid, to disappear, to cut ties with everyone. How would you do it?
> **A (story):** I looked up at the house, one last time. A sense of sadness threatened to overwhelm me. No. I couldn't beat myself up about it. This was the only option. This, or death...

### Selection funnel
| Step | Remaining | Removed at this step |
| --- | ---: | ---: |
| Raw WritingPrompts rows (train shards) | 272,600 | - |
| After keeping only [WP] plain writing prompts | 230,785 | 41,815 |
| After story length filter (100-300 words) | 65,344 | 165,441 |
| After story quality gates (artifacts, completeness, Reddit-noise) | 52,287 | 13,057 |
| After prompt gates (min length, unsafe-content filter) | 47,004 | 5,283 |
| After removing duplicate prompts and stories | 28,310 | 18,694 |
| Final random sample (seed=42) | 400 | 27,910 |

### Filter details
- `question` = writing prompt (`[WP]` tag removed); `answer` = the human story, 100-300 words.
- **WP-tag gate:** keep only plain `[WP]` prompts; drop image/established-universe prompts that need context the AI can't see.
- **Detokenization:** the raw dump is tokenized (quotes as `` `` ``/`''`, split contractions like "do n't"); we restore normal text so the human stories don't carry a tell-tale artifact the AI answers lack (surface only, not content).
- **Reddit-noise gate:** drops stories with meta-text ("Part 2 on my profile", "Edit:", "/r/sub", "feedback welcome", links) — otherwise the classifier could cheat on those instead of style.
- **Markdown + unsafe-content gates:** drops stories with headings/rules/bullets, and prompts about violence/abuse/self-harm/terrorism (so every AI actually answers instead of refusing).
- Plus all shared gates. IDs: `longform_0000` ... `longform_0399`.
- License: Reddit user content (r/WritingPrompts) - cite as academic use.

---

## Validation
`validate()` blocks writing the CSV unless everything holds: 400 per domain, all 1,200 ids/questions/answers unique, no empty cells, every answer 100-300 words, and all gates above pass. These are rule-based filters (not a manual factuality review).
