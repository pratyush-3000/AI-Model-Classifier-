# Before_Length_Filter

Each domain's eligible pool with **all filters applied EXCEPT the 100-300 word length cut**.
Lets you see how many candidates exist per domain before narrowing by length.

Files: `explanatory_before_length.csv`, `technical_before_length.csv`, `long-form_before_length.csv`
(columns: `domain`, `question`, `answer`, `answer_words`; technical also has `site`)

| Domain | Rows | Words (min / median / max) |
| --- | ---: | --- |
| explanatory | 216,694 | 8 / 67 / 227 |
| technical | 31,322 | 2 / 116 / 1,663 |
| long-form | 63,267 | 99 / 441 / 4,327 |

## Filters applied

**All domains (shared):**
- Completeness: no answers cut off mid-thought (must start capital/quote, end with sentence punctuation)
- Artifacts: no URLs, `[deleted]`/`[removed]`, `Edit:` markers, code fences
- Forum noise: no references to other posts/users (`@OP`, `@name`, `/u/`, `/r/`, "other answers", "this thread")
- CSV safety: no cells starting with `= + - @ #`
- Deduplication: no duplicate question or answer

**Explanatory (ELI5):**
- Clear-question gate: must be a real question/request (has `?` or starts with how/why/what/explain/etc.); no bare topic or thread titles
- Self-contained: no questions referencing a quoted paper, attachment, or diagram

**Technical (StackExchange):**
- HTML -> plain text: no links, images, code blocks, tables, quotes, scripts, or math markup
- Self-contained + missing-context: no "see above" / "the following code" / "accepted answer"; no external references
- Question 40-2,000 chars, posted before 2022-11-30
- Answer `pm_score >= 2`; one answer per question (accepted first -> higher score -> smaller id)

**Long-form (WritingPrompts):**
- WP-tag: keep only plain `[WP]` prompts (drop image/established-universe prompts)
- Detokenization: restore normal text (`` `` ``/`''` quotes, "do n't" -> "don't", spacing)
- Reddit-noise: no meta-text ("Part 2 on my profile", "Edit:", "/r/sub", "feedback welcome", links)
- Markdown-layout: no headings/rules/bullets
- Unsafe-content: no prompts about violence/abuse/self-harm/terrorism
- Prompt must be >= 40 characters
