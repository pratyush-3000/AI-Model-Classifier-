"""
CSCI 544 Team 10 — dataset sanity checks (run before any modeling).

Usage (from the repo root):
    python scripts/dataset_checks.py \
        --ai data/3_ai_outputs/ai_responses_merged_12000_latexfree_sysprompt_2026-09-27_2307.csv \
        --human data/1_human_data/human_responses_1200_v5_split_2026-09-26_1847.csv \
        --out reports/dataset_check.md

Checks
  1. Row counts + prompt coverage (every prompt_id present exactly once per class)
  2. Generation-config consistency per model (effort, temperature, max_tokens, system prompt)
  3. Truncation (stop_reason) and length-band violations per model x domain
  4. Length distributions vs. human per domain
  5. Split integrity (each prompt_id in exactly one split)
  6. Refusal / preamble / markdown rates per class
  7. Length-and-format-only baseline (how much can trivial features predict the class?)
  8. Long-form prompt diversity + near-duplicate rate within class
"""
import argparse
import re
import sys

import numpy as np
import pandas as pd

TEXT_COL_PREF = ["answer_clean", "answer_raw", "answer"]

REFUSAL_RE = re.compile(
    r"\b(?:I can(?:'|’)?t (?:help|assist|provide)|I cannot (?:help|assist|provide)|"
    r"I(?:'|’)m (?:not able|unable) to|I won(?:'|’)t be able to|As an AI\b|I must decline)",
    re.I,
)
PREAMBLE_RE = re.compile(
    r"^\s*(?:Sure|Certainly|Of course|Great question|Absolutely|Here(?:'|’)s|Good question)\b", re.I
)
CLOSING_RE = re.compile(
    r"(?:In summary|To summarize|In conclusion|Hope this helps|Let me know if)[^\n]*\s*$", re.I
)


def pick_text_col(df):
    for c in TEXT_COL_PREF:
        if c in df.columns:
            return c
    sys.exit(f"No text column found; have {list(df.columns)}")


def md_table(df, floatfmt="{:.2f}"):
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_float_dtype(df[c]):
            df[c] = df[c].map(lambda v: "" if pd.isna(v) else floatfmt.format(v))
    cols = [str(df.index.name or "")] + [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for idx, row in df.iterrows():
        idx = idx if not isinstance(idx, tuple) else " / ".join(map(str, idx))
        lines.append("| " + " | ".join([str(idx)] + [str(v) for v in row.values]) + " |")
    return "\n".join(lines)


def load(ai_path, human_path):
    ai = pd.read_csv(ai_path)
    hu = pd.read_csv(human_path)

    ai_text = pick_text_col(ai)
    ai = ai.rename(columns={ai_text: "text"})
    ai["cls"] = ai["model_version"].astype(str) if "model_version" in ai else ai["label"].astype(str)

    hu_text = pick_text_col(hu)
    hu = hu.rename(columns={hu_text: "text"})
    if "prompt_id" not in hu.columns:
        hu["prompt_id"] = hu["prompt_group"] if "prompt_group" in hu else hu["id"]
    hu["cls"] = "human"

    keep = ["prompt_id", "domain", "question", "text", "cls"]
    both = pd.concat([ai[[c for c in keep if c in ai]], hu[[c for c in keep if c in hu]]], ignore_index=True)
    both["text"] = both["text"].fillna("").astype(str)
    both["words"] = both["text"].str.split().str.len()
    both["chars"] = both["text"].str.len()
    return ai, hu, both


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ai", required=True)
    ap.add_argument("--human", required=True)
    ap.add_argument("--out", default="report.md")
    a = ap.parse_args()

    ai, hu, both = load(a.ai, a.human)
    R = ["# Dataset sanity report\n"]
    flags = []

    # 1. Counts + coverage
    R.append("## 1. Rows and prompt coverage\n")
    counts = both.groupby(["cls", "domain"]).size().unstack(fill_value=0)
    counts.index.name = "class"
    R.append(md_table(counts) + "\n")
    cov = both.groupby(["prompt_id", "cls"]).size().unstack(fill_value=0)
    n_cls = cov.shape[1]
    missing = (cov == 0).sum()
    dupes = (cov > 1).sum()
    incomplete = cov[(cov != 1).any(axis=1)]
    R.append(f"- Classes: {n_cls}; unique prompt_ids: {len(cov)}")
    R.append(f"- Prompts not covered by every class exactly once: **{len(incomplete)}**")
    if len(incomplete):
        flags.append(f"{len(incomplete)} prompt_ids lack exactly-one coverage across classes")
        R.append("- Missing per class: " + ", ".join(f"{k}={v}" for k, v in missing.items() if v))
        R.append("- Duplicated per class: " + ", ".join(f"{k}={v}" for k, v in dupes.items() if v))
        R.append("- First 15 problem prompt_ids: " + ", ".join(map(str, incomplete.index[:15])))
    R.append("")

    # 2. Config consistency
    R.append("## 2. Generation config per model (should be ONE value per cell)\n")
    cfg_cols = [c for c in ["effort", "temperature", "max_tokens", "system_prompt_version", "is_reasoning", "vendor"] if c in ai]
    rows = {}
    for m, g in ai.groupby("cls"):
        rows[m] = {c: "; ".join(f"{k}:{v}" for k, v in g[c].astype(str).value_counts().items()) for c in cfg_cols}
        for c in cfg_cols:
            if c in ("vendor",):
                continue
            if g[c].astype(str).nunique() > 1:
                flags.append(f"{m}: mixed `{c}` values ({rows[m][c]})")
    cfg = pd.DataFrame(rows).T
    cfg.index.name = "model"
    R.append(md_table(cfg) + "\n")
    tcfg = ai.groupby("cls")["temperature"].first() if "temperature" in ai else None
    if tcfg is not None and tcfg.astype(str).nunique() > 1:
        flags.append("temperature differs ACROSS models: " + ", ".join(f"{k}={v}" for k, v in tcfg.items()))

    # 3. Truncation + bands
    R.append("## 3. Truncation and length-band violations\n")
    if "stop_reason" in ai:
        sr = ai.groupby("cls")["stop_reason"].value_counts().unstack(fill_value=0)
        sr.index.name = "model"
        R.append(md_table(sr) + "\n")
        normal = {"end_turn", "stop", "STOP", "stop_sequence", "completed", "end"}
        bad = ai[~ai["stop_reason"].astype(str).isin(normal)]
        if len(bad):
            flags.append(f"{len(bad)} rows with non-normal stop_reason: {bad['stop_reason'].value_counts().to_dict()}")
    if {"band_lo", "band_hi", "answer_words"} <= set(ai.columns):
        ai["_below"] = ai["answer_words"] < ai["band_lo"]
        ai["_above"] = ai["answer_words"] > ai["band_hi"]
        bv = ai.groupby(["cls", "domain"])[["_below", "_above"]].mean().mul(100).round(1)
        bv.columns = ["% below band", "% above band"]
        bv.index.names = ["model / domain", None]
        R.append(md_table(bv) + "\n")
        worst = bv.max(axis=1)
        for idx, v in worst[worst > 10].items():
            flags.append(f"{idx[0]} / {idx[1]}: {v:.0f}% of responses outside the word band")
    # mid-sentence ending heuristic
    ends_bad = ~both["text"].str.rstrip().str[-1:].isin(list(".!?\"')]*`:|"))
    eb = both.assign(_bad=ends_bad).groupby("cls")["_bad"].mean().mul(100).round(1).to_frame("% not ending in punctuation")
    eb.index.name = "class"
    R.append(md_table(eb) + "\n")

    # 4. Length distributions
    R.append("## 4. Word counts per class x domain (median [IQR])\n")
    def iqr(s):
        return f"{int(s.median())} [{int(s.quantile(.25))}–{int(s.quantile(.75))}]"
    ld = both.groupby(["domain", "cls"])["words"].apply(iqr).unstack()
    ld.index.name = "domain"
    R.append(md_table(ld.T.rename_axis("class")) + "\n")
    for d, g in both.groupby("domain"):
        hmed = g.loc[g.cls == "human", "words"].median()
        for m, gm in g[g.cls != "human"].groupby("cls"):
            ratio = gm["words"].median() / hmed if hmed else np.nan
            if ratio > 1.3 or ratio < 0.7:
                flags.append(f"{m} / {d}: median length {ratio:.2f}x human")

    # 5. Split integrity
    R.append("## 5. Train/test split\n")
    if "split" in ai:
        sp = ai.groupby("prompt_id")["split"].nunique()
        leak = (sp > 1).sum()
        R.append(f"- prompt_ids appearing in more than one split: **{leak}**")
        R.append("- Split sizes (AI rows): " + ", ".join(f"{k}={v}" for k, v in ai["split"].value_counts().items()))
        if leak:
            flags.append(f"{leak} prompt_ids appear in multiple splits (leakage)")
        R.append("- Human file has no split column: assign human rows the split of their prompt_id.\n")
    else:
        R.append("- No split column in AI file.\n")

    # 6. Refusals, preambles, markdown
    R.append("## 6. Refusals, preambles, closings, markdown (% of rows)\n")
    t = both["text"]
    feats = pd.DataFrame({
        "cls": both["cls"],
        "refusal": t.str.contains(REFUSAL_RE),
        "preamble": t.str.contains(PREAMBLE_RE),
        "closing": t.str.contains(CLOSING_RE),
        "md_header": t.str.contains(r"(?m)^#{1,6} "),
        "md_bullet": t.str.contains(r"(?m)^\s*(?:[-*•]|\d+\.) "),
        "md_bold": t.str.contains(r"\*\*[^*]+\*\*"),
        "code_fence": t.str.contains("```"),
    })
    fr = feats.groupby("cls").mean().mul(100).round(1)
    fr.index.name = "class"
    R.append(md_table(fr) + "\n")
    ref = feats[feats.refusal & (feats.cls != "human")]
    if len(ref):
        flags.append(f"{len(ref)} AI rows match refusal patterns: {ref['cls'].value_counts().to_dict()}")

    # 7. Trivial-feature baseline
    R.append("## 7. Length/format-only baseline\n")
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import f1_score
        from sklearn.model_selection import GroupKFold
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import make_pipeline

        X = pd.DataFrame({
            "words": both["words"], "chars": both["chars"],
            "avg_word": both["chars"] / both["words"].clip(lower=1),
            "newlines": t.str.count("\n"), "paras": t.str.count(r"\n\s*\n"),
            "commas": t.str.count(","), "dashes": t.str.count("—|–"),
            "caps_ratio": t.str.count(r"[A-Z]") / both["chars"].clip(lower=1),
        })
        X = pd.concat([X, feats.drop(columns="cls").astype(int)], axis=1).fillna(0)
        y = both["cls"].values
        groups = both["prompt_id"].values
        preds = np.empty(len(y), dtype=object)
        for tr, te in GroupKFold(n_splits=5).split(X, y, groups):
            clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
            clf.fit(X.iloc[tr], y[tr])
            preds[te] = clf.predict(X.iloc[te])
        f1 = f1_score(y, preds, average="macro")
        chance = 1 / len(set(y))
        R.append(f"- Macro-F1 using only length + formatting features (5-fold, grouped by prompt): **{f1:.3f}** (chance ≈ {chance:.3f})")
        hmask = y == "human"
        fpr = (preds[hmask] != "human").mean()
        R.append(f"- Human rows misclassified as some model: {fpr:.1%}")
        R.append("- This is the floor every real classifier must beat. If it is far above chance, report it — "
                 "length/format is carrying signal and the formatting-stripped condition matters.\n")
        if f1 > 2 * chance:
            flags.append(f"length/format-only baseline macro-F1 {f1:.2f} vs chance {chance:.2f}")
    except ImportError:
        R.append("- scikit-learn not installed; skipped.\n")

    # 8. Long-form diversity
    R.append("## 8. Long-form prompt diversity and near-duplicates\n")
    lf = both[both["domain"].str.contains("long", case=False, na=False)]
    if len(lf) and "question" in lf:
        R.append(f"- Unique long-form question texts: **{lf['question'].nunique()}** across {lf['prompt_id'].nunique()} prompt_ids")
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            out = {}
            for c, g in lf.groupby("cls"):
                sims = []
                for q, gq in g.groupby("question"):
                    if len(gq) < 2:
                        continue
                    M = TfidfVectorizer(ngram_range=(1, 2), min_df=1).fit_transform(gq["text"])
                    S = cosine_similarity(M)
                    np.fill_diagonal(S, 0)
                    sims.extend(S.max(axis=1))
                if sims:
                    sims = np.array(sims)
                    out[c] = {"mean max-sim": sims.mean(), "% > 0.8": (sims > 0.8).mean() * 100}
            nd = pd.DataFrame(out).T
            nd.index.name = "class"
            R.append("- Within-class similarity to the nearest other essay on the same question (TF-IDF cosine):\n")
            R.append(md_table(nd) + "\n")
            if "human" in nd.index:
                h = nd.loc["human", "mean max-sim"]
                for c, v in nd["mean max-sim"].items():
                    if c != "human" and v > h + 0.15:
                        flags.append(f"{c}: long-form essays much more self-similar than human ({v:.2f} vs {h:.2f})")
        except ImportError:
            pass
    R.append("")

    R.insert(1, "## Flags\n" + ("\n".join(f"- ⚠️ {f}" for f in flags) if flags else "- None") + "\n")
    with open(a.out, "w") as f:
        f.write("\n".join(R))
    print("\n".join(R[:2]))
    print(f"\nFull report written to {a.out}")


if __name__ == "__main__":
    main()
