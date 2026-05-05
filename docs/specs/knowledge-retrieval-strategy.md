# Knowledge Retrieval Strategy — E2-B Spike Design

**Date:** 2026-05-05
**Epic:** E2-B
**Status:** spike — 1-day time-box
**Scope:** Should `_query_wiki` be replaced or augmented? What retrieval approach fits the constraints?
**Informed by:** E2-A (`docs/specs/session-knowledge-extraction.md`)

---

## 1. What E2-A Established

The wiki pipeline is live and structurally sound:

- Transcripts → `_ingest_session()` → `wiki/pages/*.md` written via LLM
- Per-turn whisper → `_query_wiki(history)` → LLM reads `index.md`, selects filenames → pages injected into whisper prompt
- Wiki is agent-local, filesystem-resident, no DB

The current `_query_wiki` makes one LLM call to scan `index.md` and return up to 5 filenames. It fires on every whisper turn with the raw history string as context.

E2-A trigger condition for this spike: **if retrieval recall < 50% on the Day 2 test, the index-lookup approach needs replacement or augmentation.**

The known failure mode: `_query_wiki` asks an LLM to select pages by scanning `index.md`; if the index is sparse or the LLM doesn't infer a connection between current goals and past decisions, retrieval silently returns nothing.

---

## 2. Constraints

- No new services — Python only, changes confined to `expert_agent_base/base.py` (and optionally `wiki.py`)
- No vector DB, no external embedding API in the critical path
- Retrieval must complete within a ~500ms whisper round-trip budget
- Wiki is small: < 50 pages per agent for a single developer over months of sessions
- Pattern is agent-local: DevCoach has its own wiki; a future Researcher would have its own

---

## 3. Approaches Evaluated

### 3.1 Current: LLM Index Lookup

The LLM receives `index.md` (one-line summaries per page) and the conversation context, returns up to 5 filenames.

**Latency:** 200–400ms (one LLM call, small inputs).

**Strengths:**
- Understands semantic relationships — can surface `decisions-router-architecture.md` when the user mentions "Kai" without using the word "router".
- Handles novel phrasing, synonyms, and inferential leaps without configuration.
- Already deployed; no new code if it works.

**Weaknesses:**
- Depends entirely on index quality. Vague index entries (`- [[patterns-tdd.md]] — TDD notes`) produce poor retrieval.
- Silent failure: returns `NONE` when uncertain. No partial retrieval.
- Extra LLM call on every whisper turn even when the wiki has nothing useful.
- Index is the only signal — page body content is not consulted.

---

### 3.2 BM25 / TF-IDF Full-Text Keyword Scoring

Score all pages by keyword overlap against the query. Return top-N by score.

**Latency:** < 5ms for < 50 pages. Pure Python, no network call.

**Strengths:**
- No LLM call — zero added latency, zero added API cost.
- Scores against full page body, not just index summaries.
- At < 50 pages, the entire corpus fits in memory and scoring is instant.
- Deterministic and auditable — a failing retrieval can be diagnosed by inspecting token frequencies.
- Standard-library TF-IDF (using `collections.Counter`) needs zero new dependencies.

**Weaknesses:**
- Keyword-only: misses semantic relationships. "Kai" won't match `decisions-router-architecture.md` unless that page contains "Kai".
- Requires a score threshold; wrong threshold produces noise or silence.

**Dependency note:** `rank_bm25` is not in the current `pyproject.toml`. A hand-rolled TF-IDF using `collections.Counter` is sufficient at this scale and avoids a new dependency.

---

### 3.3 Full-Text Scan (All Pages → LLM)

Read all pages, pass complete content to an LLM, ask it to select the most relevant subset.

**Verdict:** At 50 pages × 500 tokens average = 25,000 input tokens per whisper turn. Exceeds the 500ms budget and adds significant token cost. Unsuitable as a runtime strategy. Useful as a one-shot offline evaluation tool only.

---

### 3.4 Hybrid: BM25 Pre-filter + LLM Re-rank

BM25 selects top 5–10 candidates; LLM re-ranks or filters the subset.

**Strengths:** Gets the best of both — BM25 for recall, LLM for semantic precision.

**Weaknesses:** Two-stage complexity. At < 50 pages, BM25 alone is fast enough that adding an LLM re-rank re-introduces the latency cost with marginal precision gain at this scale. Revisit if the corpus grows past 100 pages.

---

### 3.5 Embedding-Based Retrieval

Embed each page and the query; return pages by cosine similarity.

**Verdict:** Requires an external embedding API call (100–300ms, new dependency in critical path) or a local model (~500MB image change, 200–500ms per query). Disproportionate for a < 50 page wiki. Defer if BM25 + LLM fallback proves insufficient.

---

## 4. Recommendation

**Augment the current LLM index lookup with a TF-IDF keyword fast path. Do not replace the LLM — replace the index as the sole signal.**

### Strategy

1. **TF-IDF scores all pages against the history tail** (< 5ms, no LLM call).
2. **If any pages score above threshold, return them directly.** Hot path — no LLM cost.
3. **If no pages score above threshold, fall back to the current LLM index lookup.** Preserves semantic inference for cases where keyword overlap is genuinely zero.

### Why not replace the LLM entirely with TF-IDF?

TF-IDF will miss pages where the terminology differs from the query. The developer says "whisper pipeline issue" and the relevant page uses "Kai" and "behavioral contract" — TF-IDF scores near zero. The LLM fallback covers this. For a cross-session recall system, silent misses are the most costly failure mode.

### Why not the full hybrid (TF-IDF + LLM re-rank)?

At < 50 pages, TF-IDF alone is fast enough that adding an LLM re-rank on every hit reintroduces the current approach's cost in the common case, with marginal precision gain. Revisit at scale.

---

## 5. Implementation Design

### 5.1 `wiki.py` — Add `score_pages_tfidf`

```python
def score_pages_tfidf(self, query: str, top_n: int = 5) -> list[tuple[str, float]]:
    import math
    import re
    from collections import Counter

    def tokenize(text: str) -> list[str]:
        return re.findall(r"\b[a-z]{2,}\b", text.lower())

    page_names = self.list_pages()
    if not page_names:
        return []

    corpus: dict[str, list[str]] = {}
    for name in page_names:
        try:
            corpus[name] = tokenize(self.read_page(name))
        except (FileNotFoundError, OSError):
            pass

    if not corpus:
        return []

    query_tokens = set(tokenize(query))
    if not query_tokens:
        return []

    n_docs = len(corpus)
    df: Counter = Counter()
    for tokens in corpus.values():
        for token in set(tokens):
            if token in query_tokens:
                df[token] += 1

    scores: list[tuple[str, float]] = []
    for name, tokens in corpus.items():
        tf = Counter(tokens)
        doc_len = len(tokens)
        if doc_len == 0:
            scores.append((name, 0.0))
            continue
        score = sum(
            (tf[t] / doc_len) * (math.log((n_docs + 1) / (df[t] + 1)) + 1.0)
            for t in query_tokens
            if tf[t] > 0
        )
        scores.append((name, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_n]
```

No new dependencies — `math`, `re`, `collections.Counter` are all standard library.

### 5.2 `base.py` — Rewrite `_query_wiki`

```python
_TFIDF_THRESHOLD = 0.01  # tunable; calibrate in Phase 2 of the spike

async def _query_wiki(self, context: str) -> str:
    try:
        # Fast path: TF-IDF scoring against full page content
        candidates = self._wiki.score_pages_tfidf(context, top_n=5)
        above_threshold = [(n, s) for n, s in candidates if s >= _TFIDF_THRESHOLD]

        if above_threshold:
            parts = []
            for name, _score in above_threshold:
                try:
                    parts.append(f"### {name}\n{self._wiki.read_page(name)}")
                except (FileNotFoundError, OSError):
                    pass
            return "\n\n".join(parts)

        # Fallback: LLM index lookup (current behaviour)
        index = self._wiki.read_index()
        if not index.strip() or index.strip() == "# Wiki Index":
            return ""
        prompt = _QUERY_WIKI_PROMPT.format(index=index, context=context)
        raw = (await self._generate(prompt)).strip()
        if not raw or raw == "NONE":
            return ""
        page_names = [line.strip() for line in raw.splitlines() if line.strip()]
        parts = []
        for name in page_names[:5]:
            try:
                parts.append(f"### {name}\n{self._wiki.read_page(name)}")
            except (FileNotFoundError, OSError):
                pass
        return "\n\n".join(parts)

    except Exception as exc:
        logger.warning("_query_wiki failed: %s", exc)
        return ""
```

### 5.3 Unchanged

`WikiManager` (except new method), `_ingest_session`, `_synthesize`, `_handle_whisper`, all endpoints, `WhisperContext`, `WhisperResponse`.

---

## 6. Tests

Add to `expert-agents/base/tests/`:

- `test_score_pages_tfidf_returns_relevant_pages` — pre-populate wiki with 3 pages; assert the page whose content overlaps the query scores highest.
- `test_score_pages_tfidf_empty_wiki_returns_empty_list` — empty wiki dir; assert `[]`.
- `test_query_wiki_uses_tfidf_fast_path_when_above_threshold` — stub `score_pages_tfidf` to return one page above threshold; assert `_generate` is never called.
- `test_query_wiki_falls_back_to_llm_when_tfidf_empty` — stub `score_pages_tfidf` to return `[]`; assert `_generate` is called with the index prompt.

Follow the `tmp_path`-based pattern already established in `test_base.py` and `test_wiki.py`.

---

## 7. Evaluation Plan

### Pre-work (30 min)

Confirm `expert-agents/dev-coach/wiki/pages/` has ≥ 5 pages from E2-A ingest runs. If not, run ingest against 3 recent transcripts first. The spike cannot produce meaningful recall numbers on an empty wiki.

### Phase 1 — Implement (2–3 hours)

1. Add `score_pages_tfidf` to `WikiManager`.
2. Rewrite `_query_wiki` with TF-IDF fast path + LLM fallback.
3. Write and pass the four unit tests above.

### Phase 2 — Evaluate (1–2 hours)

4. Assemble 3–5 test queries from past session context (goal strings, project_map entries, or history tails from real sessions).
5. Manually identify 2–4 ground-truth pages for each query.
6. Measure recall for three approaches:

| Query | GT count | LLM-only | TF-IDF-only | TF-IDF+fallback |
|---|---|---|---|---|
| … | … | … | … | … |

7. Calibrate `_TFIDF_THRESHOLD`: score all ground-truth pages, set threshold just below the lowest true-positive score.

### Pass Threshold

- Average recall ≥ 50% across all test queries
- Average recall ≥ LLM-only baseline (no regression)
- TF-IDF fast path latency < 10ms (expected < 5ms at < 50 pages)

If TF-IDF-only recall matches or exceeds TF-IDF+fallback on all queries, drop the LLM fallback to simplify the code.

---

## 8. Decision Criteria

| Condition | Action |
|---|---|
| TF-IDF+fallback recall ≥ 50% AND ≥ LLM-only baseline | Accept; merge implementation |
| TF-IDF+fallback recall ≥ 50% but TF-IDF-only equals it | Drop LLM fallback; simplify |
| Recall < 50%, root cause: poor page vocabulary | Enrich ingest prompt / wiki_schema; re-test |
| Recall < 50%, root cause: sparse wiki | Not a retrieval problem; need more sessions; defer |
| Recall < 50%, root cause: semantic mismatch | Add LLM re-rank on TF-IDF subset (full hybrid); 1-day follow-on spike |

---

## 9. Out of Scope

- Embedding-based retrieval — defer if TF-IDF + LLM fallback proves insufficient
- `/prime` endpoint (session-start priming) — E2-A decision
- SQLite, vector DB — future spike
- Multi-agent knowledge aggregation — DevCoach only
- Okapi BM25 proper (k1/b parameters) — hand-rolled TF-IDF is sufficient at < 50 pages

---

## 10. Key Risk

**Vocabulary mismatch between page content and conversation history.** TF-IDF will miss semantically related but terminologically distinct pages. The LLM fallback covers this, but if the fallback fires on every query, the fast path provides no benefit. That outcome is acceptable (no regression) — the next step would be enriching page content or index entries with keywords during ingest (an ingest prompt change, not a retrieval change).
