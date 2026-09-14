"""Build a 1,200-row dataset of real human answers for the CSCI 544 project.

What this script produces
--------------------------
human_responses_1200.csv: 400 answers from each of three domains
  - explanatory : ELI5 "explain like I'm five" answers
  - long-form   : WritingPrompts creative-writing stories (r/WritingPrompts)
  - technical   : StackExchange answers (HuggingFace H4 distribution)

These 1,200 human answers are the baseline. Later, each question is sent to
several AI models via a Batch API, and the AI answers are compared against
these human ones.

How to run
----------
    pip install pandas pyarrow
    python Select_1200_data.py

The first run downloads the source files into ./data and caches them, so
later runs are fast. Everything is reproducible: same seed -> same 1,200 rows.

Design rules
------------
- We never rewrite, summarize, or trim the human text. We only SELECT answers
  that already meet our rules. That keeps the "human" baseline authentic.
- All three domains share the same quality filters (see is_low_quality).
- Selection is seeded (SEED = 42) so the output is reproducible.
"""

from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
import hashlib
import json
import random
import re
import shutil

import pandas as pd
import pyarrow.parquet as pq


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Folders and output files. Everything lives next to this script.
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"                       # cached downloads + provenance
OUTPUT_CSV = BASE_DIR / "human_responses_1200.csv"  # the final dataset
NOTES_MD_PATH = BASE_DIR / "dataset_selection_notes.md"  # human-readable notes (Markdown)

# Sampling settings.
SEED = 42            # fixed seed -> reproducible random draws
SAMPLE_SIZE = 400    # rows per domain (400 x 3 = 1,200)

# Length limits (inclusive). Character counts include spaces and line breaks.
# Short domains (explanatory, technical) are measured in CHARACTERS.
# The long-form domain is measured in WORDS instead.
MIN_CHARS, MAX_CHARS = 300, 500
MIN_WORDS, MAX_WORDS = 300, 500

# CSV columns. CORE_COLUMNS are the essentials; COLUMNS adds bookkeeping fields.
CORE_COLUMNS = ["id", "domain", "source", "label", "question", "answer", "answer_len"]
COLUMNS = CORE_COLUMNS + ["answer_words", "prompt_group", "source_url"]

# --- Source: ELI5 (explanatory) -------------------------------------------
ELI5_URL = (
    "https://huggingface.co/api/datasets/sentence-transformers/eli5/"
    "parquet/pair/train/0.parquet"
)
ELI5_PARQUET = DATA_DIR / "eli5_pair_train_0.parquet"
ELI5_MIN_QUESTION_CHARS = 15  # skip near-empty ELI5 titles

# --- Source: WritingPrompts (long-form) -----------------------------------
# r/WritingPrompts data: each row is a creative-writing prompt + a human-written
# short story responding to it. We use this instead of PERSUADE 2.0 because
# PERSUADE only had 15 distinct prompts (essays repeated), while WritingPrompts
# has tens of thousands of unique prompts, letting us keep all 400 questions
# distinct. Genre = creative fiction, cleanly different from ELI5/StackExchange.
WRITINGPROMPTS_SHARDS = [
    "https://huggingface.co/api/datasets/euclaise/writingprompts/parquet/default/train/0.parquet",
    "https://huggingface.co/api/datasets/euclaise/writingprompts/parquet/default/train/1.parquet",
]
WRITINGPROMPTS_FILES = [
    DATA_DIR / "writingprompts_train_0.parquet",
    DATA_DIR / "writingprompts_train_1.parquet",
]
WP_MIN_PROMPT_CHARS = 40  # skip ultra-short/vague prompts

# --- Source: StackExchange (technical) ------------------------------------
# We use the H4 distribution because it keeps questions and answers separate.
STACK_REPO = "HuggingFaceH4/stack-exchange-preferences"
STACK_REVISION = "c7bda74048748f55749cd663c3d8d1025a841fd9"  # pinned for reproducibility
# The 4 technical sites we read, and how many parquet shards each has.
STACK_SITES = {
    "cs.stackexchange.com": 1,
    "dba.stackexchange.com": 2,
    "networkengineering.stackexchange.com": 1,
    "softwareengineering.stackexchange.com": 3,
}
# Human-readable name for each StackExchange site, for the notes file.
STACK_SITE_NAMES = {
    "cs.stackexchange.com": "Computer Science (theory, algorithms, complexity)",
    "dba.stackexchange.com": "Database Administrators (SQL, DB design, tuning)",
    "networkengineering.stackexchange.com": "Network Engineering (routing, switching, protocols)",
    "softwareengineering.stackexchange.com": "Software Engineering (design, architecture, practices)",
}
STACK_CUTOFF_DATE = "2022/11/30"   # keep questions posted before this date
STACK_MIN_Q, STACK_MAX_Q = 40, 2000  # question length window (characters)
STACK_MIN_SCORE = 2                 # minimum H4 preference score for an answer

# ---------------------------------------------------------------------------
# Text quality filters
# ---------------------------------------------------------------------------
# We reject an answer rather than editing it. These patterns catch text that
# would confuse an AI model or a reader when shown out of its original context.

# Formatting/markup artifacts that shouldn't appear in a clean plain-text answer.
ARTIFACTS = re.compile(
    r"https?://|www\.|_URL_\d*_|\[deleted\]|\[removed\]|"
    r"\b(?:edit|update)\s*[:\-]|~~|```|\ufffd",
    re.IGNORECASE,
)

# Phrases that only make sense with context we are not keeping (images, other
# answers, "the code above", etc.). Common in StackExchange answers.
MISSING_CONTEXT = re.compile(
    r"\b(?:as (?:in|per) (?:the )?title|(?:see|shown|given|pictured) (?:above|below)|"
    r"(?:following|attached) (?:code|image|diagram|screenshot)|"
    r"(?:other|previous|accepted) answer|as others (?:mentioned|said|noted)|as @\w+)",
    re.IGNORECASE,
)

# Reddit/forum references inside an ANSWER that point at other posts or the
# thread itself. These make the answer read oddly on its own.
ANSWER_FORUM_NOISE = re.compile(
    r"@op\b|/u/|/r/|\bu/\w+|@[A-Za-z][A-Za-z0-9_]{2,}|"  # @Username mentions
    r"other (?:responses|comments|answer)s?|"
    r"this thread|the thread|top comment|as (?:someone|others) (?:said|mentioned|noted)",
    re.IGNORECASE,
)

# A cell that begins with one of these characters is either a spreadsheet
# formula-injection risk (= + - @) or already corrupted (#NAME? etc.). We skip
# such rows entirely so the exported CSV opens cleanly in any tool.
LEADING_BAD_CHAR = re.compile(r"^\s*[=+\-@#]")

# What counts as a usable QUESTION prompt for the explanatory domain. We want
# either a real question mark, or an imperative/explanation request. This keeps
# "Explain X", "What is Y", "Why does Z" and rejects bare topic titles like
# "space, radio and speed".
CLEAR_QUESTION = re.compile(
    r"\?"                                              # contains a question mark, OR
    r"|^\s*(?:eli5|explain|describe|tell|give|list|compare|contrast|define|"
    r"clarify|walk|break\s+down|how|why|what|when|where|who|which|whose|whom|"
    r"can|could|would|should|does|do|is|are|was|were|if)\b",
    re.IGNORECASE,
)

# Reddit/forum thread noise inside a QUESTION that makes it unusable as a
# standalone prompt (missing context, personal threads, podcast/episode titles).
QUESTION_FORUM_NOISE = re.compile(
    r"(?:details|explanation|context|info|more|question)s?\s+inside|"
    r"discussion thread|\bpodcast\b|"
    r"episode\s*\d+|askscience|askhistorians|help me convince|"
    r"\bmy (?:heritage|friend told me)",
    re.IGNORECASE,
)

# A QUESTION that points to context an AI cannot see: a quoted paper/passage,
# an attached file, "the following grammar/code/proof", etc. We drop these so
# every prompt is self-contained and any model can answer it on its own. This
# matters because the questions are sent to several AI models later, and the
# human/AI answers must be comparable for the classifier.
QUESTION_EXTERNAL_REF = re.compile(
    r"\bit says\b|\bthe following\b|\bas follows\b|\bprovided (?:in|below|above)\b|"
    r"\bthis (?:paper|passage|proof|article|book|document|pdf|text file|attachment|grammar)\b|"
    r"\breading (?:a|this|the) (?:paper|article|book)\b|"
    r"\bfollowing (?:grammar|code|query|table|error|example|proof)\b|"
    r"\bin a text file\b|\battached\b|\bscreenshot\b|\bimage below\b|\bpicture below\b",
    re.IGNORECASE,
)

# A QUESTION that leans on an inline ASCII diagram/table (rows of dashes/pipes,
# "X-----Y" graph edges, single-letter lines). The layout is lost once we
# flatten HTML, so the question no longer makes sense on its own.
QUESTION_ASCII_ART = re.compile(r"[-|>=]{4,}|\b[A-Z]-{2,}[A-Z]\b|\n\s*[A-Z]\s*\n")

# --- WritingPrompts-specific filters (long-form) ---------------------------
# A leading tag on the raw prompt, e.g. "[ WP ]", "[IP]", "[EU]". We only keep
# "WP" (plain writing prompts) and strip the tag from the question text.
WP_TAG = re.compile(r"^\s*\[\s*([A-Z]{2,4})\s*\]\s*")

# Reddit meta-text that authors leave in their STORY: continuation pointers
# ("Part 2 on my profile"), edit notes, self-promo, links, feedback requests.
# We drop stories containing these so the human answer is a clean, standalone
# story. Leaving them in would let the classifier cheat by detecting Reddit
# artifacts (which no AI answer would ever contain) instead of writing style.
REDDIT_NOISE = re.compile(
    r"\bedit\s*:|"                                   # "Edit:" note
    r"to be continued|continued in the comment|"
    r"\bpart\s*(?:2|two|ii)\b\s*(?:on|in|coming|incoming|soon|below)|"
    r"(?:on|in) my profile|link in (?:my )?bio|check (?:out )?my (?:profile|other)|"
    r"more of my (?:work|stories|writing)|"
    r"first (?:time )?post(?:ing)?|feedback (?:is )?(?:welcome|appreciated)|"
    r"constructive criticism|thanks for the (?:gold|silver|upvotes|karma)|"
    r"sorry for (?:the )?format|(?:i'?m |am )on mobile|"
    r"/?r/\w+|/?u/\w+|https?://|www\.|\.(?:com|net|org|blogspot)\b|"
    r"my first (?:ever )?(?:piece|story|attempt|post|writing)|"
    r"hope you (?:enjoy|like)(?:ed)? (?:it|the story|this)|"
    r"~~~~|\[wp\]",
    re.IGNORECASE,
)

# Markdown formatting left inside a story: heading lines ("# Title #"), horizontal
# rules ("---", "-- -"), or bullet markers. These are layout artifacts that make
# the human text look different from a plain AI answer, so we drop such stories.
STORY_MARKDOWN = re.compile(
    r"^\s*#{1,6}\s|^\s*[-*=]{2,}\s*$|^\s*[-*]\s+\S|-{2,}\s+-",
    re.MULTILINE,
)

# Prompts with content AI models may refuse or heavily sanitize (explicit
# violence, sexual abuse, self-harm, terrorism, hate). We skip these so every
# AI in the batch actually answers instead of returning a refusal, which would
# pollute the style data.
UNSAFE_PROMPT = re.compile(
    r"\b(rape|molest|pedophil|incest|bestialit|necrophil|"
    r"suicide|self[- ]harm|behead|torture|gore|genocide|"
    r"nazi|hitler|isis|terrorist|school shoot|mass shoot|"
    r"child (?:abuse|porn)|underage)\w*",
    re.IGNORECASE,
)


def detokenize(text):
    """Undo the WritingPrompts tokenization so text reads like normal writing.

    The source stores text tokenized: quotes as `` and '', contractions split
    ("do n't"), and spaces before punctuation. If we left these in, the human
    stories would carry a tell-tale artifact that no AI answer has, letting the
    classifier cheat. This restores the original surface form (it does NOT
    change wording).
    """
    # Reddit dump uses `` and '' for opening/closing double quotes.
    text = text.replace("``", '"').replace("''", '"')
    # Collapse the literal "\n \n" paragraph tokens into real blank lines.
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    # Rejoin split contractions and possessives: "do n't" -> "don't", "cat 's".
    text = re.sub(r"\s+n't\b", "n't", text)
    text = re.sub(r"\s+'(ll|re|ve|s|m|d)\b", r"'\1", text)
    # Remove spaces before punctuation and inside quotes/parens.
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    # Collapse repeated spaces (keep newlines).
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def clean_prompt(prompt):
    """Normalize a raw WritingPrompts prompt into a clean question string.

    Removes the leading "[WP]" tag and list markers, then detokenizes.
    """
    text = WP_TAG.sub("", prompt)                     # drop leading tag
    text = re.sub(r"^\s*[-*>#\u2022]+\s*", "", text)  # drop leading list/markdown markers
    text = detokenize(text)
    return re.sub(r"\s+", " ", text).strip()          # prompts are single-line


def is_self_contained(question):
    """Return True if a question can be answered without hidden context.

    Drops questions that quote/point to an external paper, attachment, or
    inline ASCII diagram we cannot show to an AI model.
    """
    return not (QUESTION_EXTERNAL_REF.search(question)
                or QUESTION_ASCII_ART.search(question))

# Characters we accept as a proper sentence ending. If an answer ends on a bare
# letter or digit, it usually got cut off mid-thought and reads as incomplete.
SENTENCE_ENDINGS = ('.', '!', '?', '"', "'", ')', ']', '}', ':', '\u2026')


def is_clear_question(question):
    """Return True if a question is a clean, standalone prompt.

    Strict gate for explanatory questions: it must be long enough, not start
    with a corrupt/injection character, contain no forum-thread noise, and read
    as an actual question or an explanation request (not a bare topic title).
    """
    q = question.strip()
    if len(q) < ELI5_MIN_QUESTION_CHARS:
        return False
    if LEADING_BAD_CHAR.match(q):
        return False
    if QUESTION_FORUM_NOISE.search(q):
        return False
    if not is_self_contained(q):
        return False
    return bool(CLEAR_QUESTION.search(q))


def is_low_quality(text):
    """Return True if an answer looks incomplete and should be skipped.

    This is the shared quality gate for all three domains. It flags the two
    "weird answer" problems we saw in the data:
      1) starts mid-sentence (first letter is lowercase), and
      2) ends mid-thought (no terminal punctuation on the last character).
    We reject such answers instead of editing them, so the human baseline
    stays authentic.
    """
    stripped = text.strip()
    if not stripped:
        return True
    # (1) A proper answer starts with a capital letter, a digit, or a quote.
    first = stripped[0]
    if first.isalpha() and not first.isupper():
        return True
    # (2) A proper answer ends with sentence-ending punctuation.
    if not stripped.endswith(SENTENCE_ENDINGS):
        return True
    return False


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def normalized(text):
    """Lowercase + collapse whitespace. Used only for duplicate detection."""
    return re.sub(r"\s+", " ", text.strip().lower())


def pick(rows, count):
    """Pick `count` rows reproducibly (seeded) while keeping source order."""
    if len(rows) < count:
        raise ValueError(f"Only {len(rows)} eligible rows; need {count}.")
    indices = sorted(random.Random(SEED).sample(range(len(rows)), count))
    return [rows[i] for i in indices]


def download(url, destination):
    """Download `url` to `destination`, caching it. Partial files are discarded."""
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".download")
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=180) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def make_row(row_id, domain, source, question, answer, group, url):
    """Build one CSV row as a dict, computing the length/word-count fields."""
    return {
        "id": row_id,
        "domain": domain,
        "source": source,
        "label": "human",
        "question": question,
        "answer": answer,
        "answer_len": len(answer),
        "answer_words": len(answer.split()),
        "prompt_group": group,
        "source_url": url,
    }


# ---------------------------------------------------------------------------
# Domain 1: Explanatory (ELI5)
# ---------------------------------------------------------------------------

def build_explanatory(excluded_questions):
    """Select 400 ELI5 answers: 300-500 chars, clean, complete, unique.

    We read the raw ELI5 parquet and apply the same quality gate as the other
    domains, so incomplete/low-quality answers are dropped and replaced.
    """
    download(ELI5_URL, ELI5_PARQUET)

    pool = []
    seen_questions = set(excluded_questions)
    seen_answers = set()
    # funnel counts how many rows survive after each filter, in order. This is
    # what the notes file turns into the "raw -> ... -> 400" breakdown.
    funnel = Counter()
    for batch in pq.ParquetFile(ELI5_PARQUET).iter_batches(batch_size=4096):
        for item in batch.to_pylist():
            funnel["raw"] += 1
            question = (item["question"] or "").strip()
            answer = (item["answer"] or "").strip()

            # Step 1: keep answers within the 300-500 character window.
            if not MIN_CHARS <= len(answer) <= MAX_CHARS:
                continue
            funnel["after_length"] += 1

            # Step 2: drop markup artifacts, incomplete-looking answers, forum
            # noise, and answers starting with a spreadsheet-corrupting char.
            if (ARTIFACTS.search(answer) or is_low_quality(answer)
                    or ANSWER_FORUM_NOISE.search(answer)
                    or LEADING_BAD_CHAR.match(answer)):
                continue
            funnel["after_answer_quality"] += 1

            # Step 3: the question must be a clean, standalone question or
            # "explain X" request (no bare topic titles or corrupt cells).
            if not is_clear_question(question):
                continue
            funnel["after_clear_question"] += 1

            # Step 4: drop duplicate questions and duplicate answers.
            qkey, akey = normalized(question), normalized(answer)
            if qkey in seen_questions or akey in seen_answers:
                continue
            funnel["after_dedup"] += 1

            seen_questions.add(qkey)
            seen_answers.add(akey)
            pool.append((question, answer))

    # Step 5: seeded random sample down to the final SAMPLE_SIZE.
    chosen = pick(pool, SAMPLE_SIZE)
    funnel["sampled"] = len(chosen)

    # Assign stable sequential IDs after the seeded draw.
    rows = []
    for index, (question, answer) in enumerate(chosen):
        row_id = f"eli5_{index:04d}"
        rows.append(make_row(
            row_id, "explanatory", "eli5", question, answer,
            row_id, "https://huggingface.co/datasets/sentence-transformers/eli5",
        ))

    # Ordered funnel steps: (label, count remaining) for the notes file.
    stats = {
        "funnel": [
            ("Raw ELI5 pairs (pair/train)", funnel["raw"]),
            ("After answer length filter (300-500 chars)", funnel["after_length"]),
            ("After answer quality gates (artifacts, completeness, forum-noise, CSV-safety)", funnel["after_answer_quality"]),
            ("After clear-question gate on the question", funnel["after_clear_question"]),
            ("After removing duplicate questions and answers", funnel["after_dedup"]),
            ("Final random sample (seed=42)", funnel["sampled"]),
        ],
    }
    return rows, stats


# ---------------------------------------------------------------------------
# Domain 2: Long-form (WritingPrompts)
# ---------------------------------------------------------------------------

def load_writingprompts():
    """Download (once) and load the WritingPrompts train shards as rows."""
    rows = []
    for url, path in zip(WRITINGPROMPTS_SHARDS, WRITINGPROMPTS_FILES):
        download(url, path)
        for batch in pq.ParquetFile(path).iter_batches(batch_size=8192):
            rows.extend(batch.to_pylist())
    return rows


def build_long_form(excluded_answers, excluded_questions):
    """Select 400 creative-writing pairs: unique prompts, 300-500-word stories.

    Each row is a writing prompt (question) + a human-written story (answer).
    Every one of the 400 questions is a DISTINCT prompt, unlike the old
    PERSUADE source which only had a handful of repeated prompts.
    """
    raw = load_writingprompts()

    pool = []
    seen_questions = set(excluded_questions)
    seen_answers = set(excluded_answers)
    funnel = Counter()
    for item in raw:
        funnel["raw"] += 1
        tag_match = WP_TAG.match(item["prompt"] or "")
        question = clean_prompt(item["prompt"] or "")
        answer = detokenize(item["story"] or "")

        # Step 1: keep only plain "[WP]" prompts (self-contained writing tasks;
        # drop image prompts [IP], established-universe [EU], etc.).
        if not tag_match or tag_match.group(1) != "WP":
            continue
        funnel["after_wp_tag"] += 1

        # Step 2: keep stories within the 300-500 word window.
        if not MIN_WORDS <= len(answer.split()) <= MAX_WORDS:
            continue
        funnel["after_length"] += 1

        # Step 3: story quality - artifacts, incomplete text, Reddit meta-noise
        # (continuation pointers, edit notes, self-promo, links), markdown
        # layout (headings/rules/bullets), and CSV-unsafe leading characters.
        if (ARTIFACTS.search(answer) or is_low_quality(answer)
                or REDDIT_NOISE.search(answer)
                or STORY_MARKDOWN.search(answer)
                or LEADING_BAD_CHAR.match(answer)):
            continue
        funnel["after_story_quality"] += 1

        # Step 4: prompt must be long enough and not point to unsafe content
        # that an AI model would refuse to write about.
        if len(question) < WP_MIN_PROMPT_CHARS or UNSAFE_PROMPT.search(question):
            continue
        funnel["after_prompt_gates"] += 1

        # Step 5: keep every prompt distinct (and no duplicate stories).
        qkey, akey = normalized(question), normalized(answer)
        if qkey in seen_questions or akey in seen_answers:
            continue
        funnel["after_dedup"] += 1

        seen_questions.add(qkey)
        seen_answers.add(akey)
        pool.append((question, answer))

    # Step 6: seeded random sample of 400 distinct-prompt pairs.
    chosen = pick(pool, SAMPLE_SIZE)
    funnel["sampled"] = len(chosen)

    rows = []
    for index, (question, answer) in enumerate(chosen):
        row_id = f"writingprompts_{index:04d}"
        rows.append(make_row(
            row_id, "long-form", "writingprompts", question, answer,
            row_id,  # prompt_group = id: every long-form question is unique now
            "https://huggingface.co/datasets/euclaise/writingprompts",
        ))

    stats = {
        "funnel": [
            ("Raw WritingPrompts rows (train shards)", funnel["raw"]),
            ("After keeping only [WP] plain writing prompts", funnel["after_wp_tag"]),
            ("After story length filter (300-500 words)", funnel["after_length"]),
            ("After story quality gates (artifacts, completeness, Reddit-noise)", funnel["after_story_quality"]),
            ("After prompt gates (min length, unsafe-content filter)", funnel["after_prompt_gates"]),
            ("After removing duplicate prompts and stories", funnel["after_dedup"]),
            ("Final random sample (seed=42)", funnel["sampled"]),
        ],
    }
    return rows, stats


# ---------------------------------------------------------------------------
# Domain 3: Technical (StackExchange via HuggingFace H4)
# ---------------------------------------------------------------------------

class PlainText(HTMLParser):
    """Convert StackExchange HTML into plain text.

    - Paragraph/list/heading boundaries become a marker ("\\0") we later turn
      into blank lines.
    - Inline emphasis and inline code become plain text.
    - If we hit anything we can't fairly flatten (links, images, code blocks,
      quotes, tables, scripts), we mark the whole answer as `unsuitable`.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.unsuitable = False

    def handle_starttag(self, tag, attrs):
        if tag in {"a", "img", "pre", "blockquote", "table", "script", "style", "iframe"}:
            self.unsuitable = True
        if tag in {"p", "div", "li", "br", "h1", "h2", "h3"}:
            self.parts.append("\0")

    def handle_endtag(self, tag):
        if tag in {"p", "div", "li", "h1", "h2", "h3"}:
            self.parts.append("\0")

    def handle_data(self, data):
        self.parts.append(data)


def clean_technical(html):
    """Return clean plain text for a StackExchange field, or None to reject it."""
    parser = PlainText()
    parser.feed(html or "")
    parser.close()
    if parser.unsuitable:
        return None
    # A single newline in the source HTML is just wrapping, not a new paragraph.
    lines = [re.sub(r"\s+", " ", line).strip()
             for line in "".join(parser.parts).split("\0")]
    text = "\n\n".join(line for line in lines if line)
    # Reject artifacts, missing-context phrases, forum references, math markup,
    # and text that begins with a spreadsheet-corrupting character.
    if (ARTIFACTS.search(text) or MISSING_CONTEXT.search(text)
            or ANSWER_FORUM_NOISE.search(text)
            or LEADING_BAD_CHAR.match(text)
            or re.search(r"\$|\\\(|\\\[", text)):
        return None
    return text


def stack_paths(site, shards):
    """Yield local paths to each downloaded parquet shard for one site."""
    for number in range(shards):
        name = f"train-{number:05d}-of-{shards:05d}.parquet"
        path = DATA_DIR / "stackexchange" / f"{site}_{name}"
        url = (f"https://huggingface.co/datasets/{STACK_REPO}/resolve/"
               f"{STACK_REVISION}/data/{site}/{name}")
        download(url, path)
        yield path


def build_technical(excluded_answers, excluded_questions):
    """Select 400 Q&A pairs: 100 from each of the 4 technical sites.

    For each question we keep at most one answer, chosen by:
      accepted first -> higher preference score -> smaller answer id.
    Provenance (author, ids, dates) is recorded separately for attribution.
    """
    selected, attribution, stats = [], [], {}
    seen_answers = set(excluded_answers)
    seen_questions = set(excluded_questions)
    # Running total across all sites, for the overall funnel in the notes.
    totals = Counter()

    for site, shards in STACK_SITES.items():
        pool, counters, seen_ids = [], Counter(), set()
        for path in stack_paths(site, shards):
            for batch in pq.ParquetFile(path).iter_batches(batch_size=1024):
                for item in batch.to_pylist():
                    counters["source_questions"] += 1
                    # The date belongs to the question; keep older questions only.
                    if not item["date"] or item["date"] >= STACK_CUTOFF_DATE:
                        continue
                    counters["after_date"] += 1
                    # Clean and length-check the question.
                    question = clean_technical(item["question"])
                    if not question or not STACK_MIN_Q <= len(question) <= STACK_MAX_Q:
                        continue
                    # The question must be answerable without hidden context
                    # (no quoted paper/attachment/ASCII diagram references, and
                    # no "explanation inside"-style pointers to missing text).
                    if (not is_self_contained(question)
                            or QUESTION_FORUM_NOISE.search(question)):
                        continue
                    counters["after_question_clean"] += 1
                    qkey = normalized(question)
                    if qkey in seen_questions or item["qid"] in seen_ids:
                        continue
                    counters["clean_questions"] += 1

                    # Collect this question's usable answers.
                    candidates = []
                    for answer in item["answers"]:
                        text = clean_technical(answer["text"])
                        if not text or not MIN_CHARS <= len(text) <= MAX_CHARS:
                            continue
                        counters["clean_length_answers"] += 1
                        # Require a decent preference score, no duplicate answer,
                        # and a complete-looking answer.
                        if (answer["pm_score"] is None or answer["pm_score"] < STACK_MIN_SCORE
                                or normalized(text) in seen_answers
                                or is_low_quality(text)):
                            continue
                        candidates.append((answer, text))
                    if not candidates:
                        continue

                    # Rank: accepted, then highest score, then smallest id.
                    answer, text = sorted(candidates, key=lambda pair: (
                        -int(bool(pair[0]["selected"])),
                        -pair[0]["pm_score"],
                        pair[0]["answer_id"],
                    ))[0]

                    seen_questions.add(qkey)
                    seen_answers.add(normalized(text))
                    seen_ids.add(item["qid"])
                    row = make_row(
                        f"stackexchange_{site}_{item['qid']}_{answer['answer_id']}",
                        "technical", "stackexchange_h4", question, text,
                        f"stackexchange:{site}:{item['qid']}",
                        f"https://{site}/questions/{item['qid']}#answer-{answer['answer_id']}",
                    )
                    provenance = {
                        "id": row["id"], "dataset": STACK_REPO, "revision": STACK_REVISION,
                        "shard": path.name, "site": site, "question_id": item["qid"],
                        "answer_id": answer["answer_id"], "question_date": item["date"],
                        "answer_author": answer["author"],
                        "answer_author_profile": answer["author_profile"],
                        "question_metadata": item["metadata"], "pm_score": answer["pm_score"],
                        "accepted": answer["selected"], "license": "CC BY-SA 4.0 (H4 dataset card)",
                    }
                    pool.append((row, provenance))

        counters["eligible_unique_pairs"] = len(pool)
        print(f"Technical {site}: {dict(counters)}", flush=True)
        # 100 pairs from this site.
        for row, provenance in pick(pool, 100):
            selected.append(row)
            attribution.append(provenance)
        counters["sampled"] = 100
        stats[site] = dict(counters)
        # Accumulate the site's per-step numbers into the overall funnel.
        for step in ("source_questions", "after_date", "after_question_clean",
                     "clean_questions", "eligible_unique_pairs", "sampled"):
            totals[step] += counters[step]

    # Overall funnel across all four sites, in filter order.
    stats["funnel"] = [
        ("Raw questions across the 4 sites (all shards)", totals["source_questions"]),
        ("After keeping questions dated before the cutoff", totals["after_date"]),
        ("After question HTML-clean + length filter (unique questions)", totals["after_question_clean"]),
        ("Questions with >=1 usable answer (answer gates applied)", totals["eligible_unique_pairs"]),
        ("Final sample: 100 pairs x 4 sites (seed=42)", totals["sampled"]),
    ]
    return selected, attribution, stats


# ---------------------------------------------------------------------------
# Validation (runs before we ever write the CSV)
# ---------------------------------------------------------------------------

def validate(df):
    """Raise if anything about the dataset is wrong. Fail loud, fail early."""
    if list(df.columns) != COLUMNS or len(df) != 1200:
        raise ValueError("Expected the defined columns and exactly 1,200 rows.")
    if df["domain"].value_counts().to_dict() != {
            "explanatory": 400, "long-form": 400, "technical": 400}:
        raise ValueError("Each domain must contain exactly 400 rows.")
    if not df["id"].is_unique or not df["answer"].map(normalized).is_unique:
        raise ValueError("Duplicate IDs or answer texts found.")
    if not df["label"].eq("human").all() or df.isna().any().any():
        raise ValueError("Missing values or unexpected labels found.")
    if any(df[column].str.strip().eq("").any()
           for column in COLUMNS if column not in {"answer_len", "answer_words"}):
        raise ValueError("Empty text fields found.")
    # Stored counts must match the actual text.
    if not df["answer_len"].eq(df["answer"].str.len()).all():
        raise ValueError("Character counts do not match.")
    if not df["answer_words"].eq(df["answer"].str.split().str.len()).all():
        raise ValueError("Word counts do not match.")
    # Every answer must pass the quality gate.
    if df["answer"].apply(is_low_quality).any():
        raise ValueError("Low-quality (incomplete-looking) answers found.")
    # No question or answer may start with a spreadsheet-corrupting character.
    if (df["question"].str.match(LEADING_BAD_CHAR).any()
            or df["answer"].str.match(LEADING_BAD_CHAR).any()):
        raise ValueError("Cells starting with = + - @ # found (CSV-corruption risk).")
    # Short-domain answers (explanatory/technical) must have no forum/thread
    # references. Long-form (creative fiction) is checked with REDDIT_NOISE
    # instead, since words like "thread" appear naturally in stories.
    if df.loc[df["domain"].ne("long-form"), "answer"].str.contains(ANSWER_FORUM_NOISE).any():
        raise ValueError("Forum/thread references found in short-domain answers.")
    # Explanatory questions must be clean, standalone questions or requests.
    explanatory = df.loc[df["domain"].eq("explanatory")]
    if not explanatory["question"].apply(is_clear_question).all():
        raise ValueError("Explanatory questions must be clear questions or requests.")
    # Short-domain questions (explanatory + technical) must be self-contained,
    # so any AI model can answer them without hidden context.
    short_q = df.loc[df["domain"].ne("long-form"), "question"]
    if not short_q.apply(is_self_contained).all():
        raise ValueError("Questions referencing external/unseen context found.")
    if short_q.str.contains(QUESTION_FORUM_NOISE).any():
        raise ValueError("Questions with forum-thread pointers found.")

    short = df.loc[df["domain"].ne("long-form")]
    long = df.loc[df["domain"].eq("long-form")]
    if not short["answer_len"].between(MIN_CHARS, MAX_CHARS).all():
        raise ValueError("Short responses must have 300-500 characters.")
    if not long["answer_words"].between(MIN_WORDS, MAX_WORDS).all():
        raise ValueError("Essays must have 300-500 words.")
    # Every question across all 1,200 rows must now be distinct (the new
    # long-form source gives us 400 unique writing prompts).
    if not df["question"].map(normalized).is_unique:
        raise ValueError("All 1,200 questions must be distinct.")
    # Long-form stories must be free of Reddit meta-noise, markdown layout,
    # and unsafe prompts.
    if long["answer"].str.contains(REDDIT_NOISE).any():
        raise ValueError("Reddit meta-noise found in long-form stories.")
    if long["answer"].str.contains(STORY_MARKDOWN).any():
        raise ValueError("Markdown formatting found in long-form stories.")
    if long["question"].str.contains(UNSAFE_PROMPT).any():
        raise ValueError("Unsafe-content prompts found in long-form questions.")


# ---------------------------------------------------------------------------
# Writing output files
# ---------------------------------------------------------------------------

def write_text_if_changed(path, text):
    """Write only when content changed, so reruns don't touch unchanged files."""
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")


def format_funnel_md(funnel):
    """Render a funnel as a Markdown table: Step | Remaining | Removed."""
    rows = ["| Step | Remaining | Removed at this step |",
            "| --- | ---: | ---: |"]
    previous = None
    for index, (label, count) in enumerate(funnel):
        removed = "-" if index == 0 else f"{previous - count:,}"
        rows.append(f"| {label} | {count:,} | {removed} |")
        previous = count
    return "\n".join(rows)


def build_markdown_notes(explanatory_stats, long_stats, technical_stats):
    """Return the selection notes as GitHub/Google-Docs-friendly Markdown."""
    technical_sites = "\n".join(
        f"| `{site}` | {STACK_SITE_NAMES[site]} | "
        f"{technical_stats[site]['source_questions']:,} | "
        f"{technical_stats[site]['eligible_unique_pairs']:,} | 100 |"
        for site in STACK_SITES
    )
    return f"""# Human Response Dataset - Selection Criteria

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
{format_funnel_md(explanatory_stats["funnel"])}

### Filter details
- Answers pass all shared quality gates (completeness, artifacts, forum-noise, CSV-safety).
- **Clear-question gate** (`is_clear_question`): the question must read as a real question or an explicit request, so it works as a standalone AI prompt. It must contain a `?` **or** start with one of: `explain, describe, tell, give, list, compare, contrast, define, clarify, walk, break down, how, why, what, when, where, who, which, whose, whom, can, could, would, should, does, do, is, are, was, were, if, eli5`.
  - Rejected: bare topic titles (`"space, radio and speed"`), thread/podcast titles (`"AskHistorians Podcast Episode 007"`), and context-missing prompts (`"...more details inside"`, `"help me convince"`, personal-heritage threads).
- **Self-contained gate** (`is_self_contained`): drops questions that point to context an AI cannot see (a quoted paper/passage, an attached file, or an inline ASCII diagram), so every prompt can be answered on its own.
- Excluded questions under {ELI5_MIN_QUESTION_CHARS} characters and duplicate questions (by case/whitespace); selected 400 with seed=42.
- IDs are assigned sequentially (`eli5_0000` ...) after the seeded draw.

---

## Technical - StackExchange / H4 structured distribution (400 rows)
**Source:** https://huggingface.co/datasets/{STACK_REPO}
- **What "H4 structured distribution" means:** this is a version of StackExchange
  released by HuggingFace's H4 team. Instead of one merged text blob, it stores
  each item as **1 question + several candidate answers, each with a preference
  score (`pm_score`)**. We use it because the questions and answers are already
  cleanly separated (the Common Pile version merges question/comments/answers
  together, which is hard to split back into clean Q&A).
- Pinned revision: `{STACK_REVISION}`
- The H4 dataset has 344 site folders total (including `.meta` communities and non-technical topics like cooking/gaming); we picked 4 technical sites relevant to our domain.
- Inspects all 7 shards of these 4 sites; this is not a full-StackExchange aggregation.

**Example row:**
> **Q:** I spoke with a guy who claimed that he's working on a GPS-system that is going to be accurate to the centimeter. Is this even possible? What is the limiting factor...?
> **A:** You can use software to compare the readings from 2 (or more) matched GPS receivers which are looking at the same set of satellites to cancel out any differences in (the many sources of) absolute errors...

### Selection funnel (summed over the 4 sites)
{format_funnel_md(technical_stats["funnel"])}

### Per-site breakdown
| Site | Topic | Raw questions | Eligible Q&A | Sampled |
| --- | --- | ---: | ---: | ---: |
{technical_sites}

### Filter details
- Question posted before {STACK_CUTOFF_DATE.replace('/', '-')}; answer/edit dates are unavailable, so we cannot guarantee the same timeframe.
- Question {STACK_MIN_Q}-{STACK_MAX_Q:,} characters; individual answers 300-500 characters after HTML conversion.
- **HTML conversion** (`clean_technical`) rejects Q&A with links, images, code blocks, tables, quote blocks, or scripts, and answers with math markup (`$`, `\\(`, `\\[`).
- **Missing-context gate** (`MISSING_CONTEXT`): drops answers needing context we do not keep, e.g. "as in the title", "see above/below", "following code/image", "other/previous/accepted answer", "as others mentioned".
- **Self-contained gate** (`is_self_contained`): drops questions that quote/point to an external paper, attachment, or inline ASCII diagram the AI cannot see.
- Answers also pass all shared quality gates.
- Preserves inline code / emphasis text; two line breaks between paragraphs, internal whitespace normalized.
- Among eligible answers with `pm_score >= {STACK_MIN_SCORE}`: accepted first -> higher pm_score -> smaller answer ID.
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
{format_funnel_md(long_stats["funnel"])}

### Filter details
- `question` = the writing prompt (with the `[WP]` tag removed); `answer` = the human story.
- **Detokenization** (`detokenize`): the raw dump is tokenized (quotes as `` `` `` / `''`, split contractions like "do n't", spaces before punctuation). We restore the normal surface form so the human text does not carry a tell-tale artifact the AI answers lack (this fixes wording surface only, not content).
- **WP-tag gate:** keep only plain `[WP]` prompts; drop `[IP]` (image), `[EU]` (established universe), etc. that need context an AI cannot see.
- Story length filtered to 300-500 words (matches the length we ask the AI models for).
- **Reddit-noise gate** (`REDDIT_NOISE`): drops stories containing Reddit meta-text such as "Part 2 on my profile", "link in bio", "Edit:", "/r/sub", "feedback welcome", or self-promo/links. Leaving these in would let the classifier cheat by spotting Reddit artifacts instead of writing style.
- **Markdown-layout gate** (`STORY_MARKDOWN`): drops stories with heading lines ("# Title #"), horizontal rules ("---"), or bullet markers, since that layout is an artifact no plain AI answer would have.
- **Unsafe-content gate** (`UNSAFE_PROMPT`): drops prompts about explicit violence, sexual abuse, self-harm, terrorism, or hate, so the AI models actually answer instead of refusing.
- Stories also pass the shared quality gates (artifacts, completeness); prompts must be >= {WP_MIN_PROMPT_CHARS} characters.
- Every prompt is unique (`prompt_group` = the row id).
- License: Reddit user-generated content (r/WritingPrompts) - cite as academic use.

---

## AI Generation Protocol (for the team - please follow exactly)
Every teammate sends the **same** prompt for their model, so the classifier
learns *model style*, not prompt differences. The only things that change
between teammates are (a) which model answers and (b) the `{{question}}` text.
**Do not** paraphrase these prompts, add a persona, or tweak wording per model.

**Prompt templates (one per domain, identical for every model):**

Explanatory (domain = `explanatory`):
```
Answer the following question in about 300-500 characters (roughly 3-6 sentences).
Write a single clear explanation in plain prose. Do not use lists, headings, bullet points, or markdown.

Question: {{question}}
```

Technical (domain = `technical`):
```
Answer the following technical question in about 300-500 characters (roughly 3-6 sentences).
Write a single clear answer in plain prose. Do not use lists, headings, bullet points, code blocks, or markdown.

Question: {{question}}
```

Long-form (domain = `long-form`):
```
Write a short story of about 300-500 words based on the following prompt.
Write plain prose only. Do not add a title, headings, bullet points, or markdown.

Prompt: {{question}}
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
"""


def write_notes(explanatory_stats, long_stats, technical_stats):
    """Write the selection notes as Markdown (easy to share / import to Docs)."""
    write_text_if_changed(
        NOTES_MD_PATH,
        build_markdown_notes(explanatory_stats, long_stats, technical_stats),
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    DATA_DIR.mkdir(exist_ok=True)

    # Build each domain in turn. We track already-used questions/answers so the
    # domains never overlap and we never produce duplicate text.
    explanatory, explanatory_stats = build_explanatory(excluded_questions=set())
    seen_questions = {normalized(row["question"]) for row in explanatory}
    seen_answers = {normalized(row["answer"]) for row in explanatory}

    long_form, long_stats = build_long_form(seen_answers, seen_questions)
    seen_answers.update(normalized(row["answer"]) for row in long_form)
    seen_questions.update(normalized(row["question"]) for row in long_form)

    technical, provenance, technical_stats = build_technical(seen_answers, seen_questions)

    # CSV row order follows the standard domain order: explanatory, technical,
    # long-form (matches the notes). Build order differs only for dedup deps.
    combined = pd.DataFrame(explanatory + technical + long_form, columns=COLUMNS)
    validate(combined)  # never write an invalid dataset

    # Write the CSV atomically: build a temp file, then swap it in. Reruns that
    # produce identical bytes leave the existing file untouched.
    temporary = OUTPUT_CSV.with_suffix(".tmp")
    try:
        combined.to_csv(temporary, index=False, encoding="utf-8-sig")
        if OUTPUT_CSV.exists() and OUTPUT_CSV.read_bytes() == temporary.read_bytes():
            temporary.unlink()
        else:
            temporary.replace(OUTPUT_CSV)
    finally:
        temporary.unlink(missing_ok=True)

    # Provenance for the technical rows (authors, ids, dates) for attribution.
    write_text_if_changed(DATA_DIR / "technical_provenance.jsonl", "".join(
        json.dumps(item, ensure_ascii=False) + "\n" for item in provenance
    ))

    # A small machine-readable report of this run.
    report = {
        "seed": SEED,
        "explanatory": explanatory_stats,
        "long_form": long_stats,
        "technical": technical_stats,
        "output_sha256": hashlib.sha256(OUTPUT_CSV.read_bytes()).hexdigest(),
    }
    write_text_if_changed(DATA_DIR / "selection_report.json", json.dumps(report, indent=2))

    write_notes(explanatory_stats, long_stats, technical_stats)

    print(f"Saved {len(combined):,} rows: {OUTPUT_CSV.name}")
    print(combined.groupby("domain")[["answer_len", "answer_words"]].agg(["min", "max"]))


if __name__ == "__main__":
    main()
