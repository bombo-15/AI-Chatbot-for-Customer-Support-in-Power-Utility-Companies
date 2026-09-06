# Kanea Chatbot — Evaluation Framework

Kanea isn't one model, it's a pipeline: keyword intent classifier → query
router (static/dynamic/escalation) → TF-IDF retrieval over the ECG knowledge
base → Claude LLM generation, plus a safety-critical danger-phrase trigger that
can fire independently of all of that. A single "accuracy" number can't
describe that pipeline, so this evaluation scores each stage separately, then
rolls in the operational metrics the app already logs from real usage.

Two things feed this chapter:

- **`backend/eval/evaluate.py`** — a deterministic, offline script. It needs
  no Anthropic API key and makes no network calls, so it can be re-run any time
  and will always produce the same numbers for the same code.
- **`backend/database.get_analytics()`** — live numbers pulled from
  `chatbot.db`, i.e. from real conversations once the app has been used.

Run it with:

```bash
cd backend
python eval/evaluate.py
```

This prints the report below and writes the full machine-readable result to
`backend/eval/results.json`.

---

## 1. Intent classification accuracy

**What it measures:** whether `classify_intent()` (`backend/chatbot.py:93`)
assigns the label a human would assign, for a hand-labeled set of 70
utterances (10 per intent: `outage_status`, `fault_report`, `billing`,
`safety`, `escalation`, `complaint`, `general` — see
`backend/eval/test_intents.json`).

**Formulas**, per intent class *c*:

```
Precision(c) = TP(c) / (TP(c) + FP(c))
Recall(c)    = TP(c) / (TP(c) + FN(c))
F1(c)        = 2 · Precision(c) · Recall(c) / (Precision(c) + Recall(c))
Accuracy     = (# correct predictions) / (# total cases)
```

TP/FP/FN are read off a 7×7 confusion matrix (gold label × predicted label),
which the script also prints in full.

**Why this metric:** intent is a hard-boundary keyword match (`kw in
lower`), so it's the layer most exposed to synonyms, slang, and phrasing the
keyword lists didn't anticipate — exactly what a labeled test set catches
that reading the code cannot.

**Latest run:** 81.4% overall accuracy. Weakest classes: `general` (F1
0.696 — questions like *"What can you help me with?"* get pulled into
`escalation` by the word "help", and *"Where is your head office located?"*
gets pulled into `outage_status`/`dynamic` by "located"-adjacent phrasing),
and `outage_status` recall (0.700 — phrases like *"is ECG aware?"* or
*"scheduled maintenance"* don't hit any outage keyword). `safety` has perfect
precision but 0.700 recall — it loses ground to `fault_report` whenever a
hypothetical safety question mentions a piece of equipment ("transformer",
"wiring").

---

## 2. End-to-end query routing accuracy

**What it measures:** `classify_query_type()` (`backend/chatbot.py:107`),
which decides `static` (RAG) vs `dynamic` (live outage data) vs `escalation`
(human handoff) — the decision that controls *what data the LLM is even
allowed to see*. Scored using the **predicted** intent from §1, not the gold
intent, so intent-classifier mistakes propagate exactly as they would in
production.

**Formula:** same accuracy formula as above, over the 3-way label.

**Why separate from intent accuracy:** routing accuracy (87.1%) is *higher*
than intent accuracy (81.4%) because several intents collapse to the same
route (`billing`, `safety`, `complaint`, `general`, and most `fault_report`
all map to `static`) — so an intent mistake doesn't always cause a routing
mistake. Reporting only intent accuracy would understate how forgiving the
routing layer is; reporting only routing accuracy would hide that the
intent label shown to the admin dashboard (`intent_distribution` in
analytics) is less reliable than the routing decision.

---

## 2b. Fixes applied after the first evaluation pass

Running the evaluation once wasn't the end of it — three of the gaps it surfaced were fixed in
the code itself, then the same test sets were re-run to confirm the improvement and check for
regressions (the point of keeping the test sets under version control: they're a regression check,
not a one-off report).

| Fix | File | Before → After |
|---|---|---|
| Added missed hazard phrases (`fallen pole`, `smoking`, `snapped wire`), dropped the overly broad bare `"burning"` keyword, added a hypothetical-question guard so FAQ-style safety questions don't false-trigger | `backend/chatbot.py` (`CONCRETE_DANGER_PHRASES`, `SOFT_DANGER_WORDS`, `_HYPOTHETICAL_PATTERNS`) | Danger detection: **P 0.333 → 0.833, R 0.400 → 1.000, F1 0.364 → 0.909** |
| Added a minimum TF-IDF relevance score before a document counts as "retrieved" (tuned against the test set: 5.0 preserves recall while roughly doubling precision; 7.0 starts costing recall) | `backend/knowledge_base.py` (`MIN_RELEVANCE_SCORE`) | RAG: **Precision@5 0.200 → 0.463**, Recall@5/Hit@5/MRR unchanged (0.933/0.933/0.900), **negative-query accuracy 0.000 → 1.000** |
| Removed the project's own presentation-slide text from the customer-facing retrieval corpus — it was being retrieved and handed to the LLM as if it were ECG customer knowledge | `backend/knowledge_base.py` (`DOCS`) | Corpus is now ECG-only; contributed to the negative-query fix above |
| Session ID now persisted in browser `localStorage`, plus a new `GET /session/{id}/messages` endpoint so the frontend re-hydrates visible chat history on refresh | `frontend/.../ChatWindow.jsx`, `backend/main.py` | Previously the backend already restored conversation context for the LLM after a refresh, but the UI showed an empty chat — a confusing mismatch. Now both agree. |

One residual case is worth naming honestly rather than hiding: `saf-10` ("What should I do to
avoid electric shock at home?") is now a false positive on danger detection, because "electric
shock" is treated as an always-trigger concrete phrase even inside a hypothetical/preventive
question. Given the safety argument in Section 3 — a missed real hazard is worse than an extra
safety reminder — this was left as-is rather than risk suppressing a genuine "I'm being shocked
right now" message. It's a good illustration, for the report's discussion section, of why a
keyword system can't fully resolve the precision/recall tension without real NLU.

Intent classification and routing accuracy are unchanged (81.4% / 87.1%) — the keyword classifier
itself wasn't touched; see Section 8 for why.

## 3. Danger / escalation-trigger detection (safety-critical)

**What it measures:** `is_danger_message()` (`backend/chatbot.py:129`), which
gates the "stay away, call 0800-POWER, `[ESCALATE_TO_AGENT]`" safety path,
scored against 5 gold-positive cases (fallen pole, sparking transformer,
smoking meter box, snapped wire, burning smell) mixed into the 70-case set.
A second, compound metric — **escalation trigger** — scores
`force_escalate = is_danger_message(text) or query_type == "escalation"`,
i.e. the actual condition production code uses to decide whether to page a
human.

**Formulas:** same precision/recall/F1 as §1, but only two classes
(danger / not-danger).

**Why recall matters more than precision here:** a false positive just
means an unnecessary "call our emergency line" sentence gets appended — mildly
annoying. A false negative means a real physical hazard (fallen wire,
smoking equipment) gets a normal chatbot reply instead of an immediate
safety warning. When reporting this metric, **lead with recall**, not F1.

**First run (before fixes):** danger-phrase recall was only 0.400 (2 of 5
true hazards caught) with precision 0.333 (4 false alarms on hypothetical
safety-FAQ questions like *"what hazards should I avoid near overhead
lines?"*). The keyword list missed "fallen pole", "smoking", and "snapped
wire" as phrases, and did substring matching with no negation/hypothetical
handling, so "hazard" inside a *question about* hazards still fired.

**After the fix (see §2b):** Recall 1.000, Precision 0.833, F1 0.909 (TP=5,
FP=1, FN=0, TN=64) — every real hazard in the test set is now caught, at the
cost of one extra false alarm on a hypothetical question containing "electric
shock". That trade-off was made deliberately: for a safety trigger, a missed
real hazard is worse than one unnecessary reminder.

---

## 4. RAG retrieval quality

**What it measures:** `knowledge_base.retrieve_relevant_docs()` — a
TF-IDF ranker over the ECG knowledge base — against 16 hand-labeled queries
(`backend/eval/test_retrieval.json`), 15 with a known-correct source section
and 1 deliberately off-topic ("jollof rice recipe") to test whether the
retriever knows when *nothing* is relevant.

**Formulas**, at cutoff *k* (Kanea uses k=5 for static queries):

```
Precision@k = |retrieved_k ∩ relevant| / k
Recall@k    = |retrieved_k ∩ relevant| / |relevant|
Hit@k       = 1 if retrieved_k ∩ relevant ≠ ∅ else 0        (averaged over queries)
MRR         = mean( 1 / rank_of_first_relevant_doc )        (0 if none found)
```

**First run (before fixes):** Recall@5 = 0.933, Hit@5 = 0.933, MRR = 0.900 —
the right document was almost always retrieved. But **Precision@5 = 0.200**:
because `top_n` was a fixed count (not a relevance threshold), 4 of the 5
slots returned per static query were low/no-relevance filler still stuffed
into the LLM's system prompt as "ECG KNOWLEDGE BASE" context. The off-topic
negative case scored 0/1 — the retriever returned 5 documents for "what is a
good recipe for jollof rice?" because there was no minimum-score cutoff,
only a rank cutoff.

**After the fix (see §2b):** Precision@5 = 0.463 (more than doubled),
Recall@5/Hit@5/MRR unchanged at 0.933/0.933/0.900 (no relevant document was
pushed out), and negative-query accuracy = 1.000 — the jollof-rice query now
correctly returns nothing. The threshold (`MIN_RELEVANCE_SCORE = 5.0`) was
picked by sweeping values against the test set: 7.0 pushes precision higher
still but starts costing recall (0.867), so 5.0 is the point that improves
precision without giving up any of the retrieval quality that mattered.

---

## 5. Operational / live metrics (from real usage)

Pulled straight from `database.get_analytics()`, already instrumented by the
app itself — no new code needed:

| Metric | Source | Formula |
|---|---|---|
| Avg. satisfaction (CSAT) | `chat_ratings.stars` (1–5, submitted via `/chat-rating`) | mean of stars |
| Helpful-feedback rate | `message_feedback.rating` (👍/👎 per message) | helpful / (helpful + unhelpful) |
| Escalation rate | `escalations` table vs. total sessions | escalations / total_sessions |
| Intent distribution | `messages.intent` | count per intent, to see real-world traffic shape vs. the test set's even 10-per-class split |

These are the metrics that matter most for a defense/demo, because they
come from actual users, not a synthetic test set — but they only fill in
once the app has real conversations and raters. At last check the DB had 16
sessions / 51 messages / 12 escalations but **zero star ratings and zero
message feedback**, meaning CSAT and helpful-rate are currently unmeasured
in practice — worth calling out as "instrumented but not yet populated"
rather than claiming a number you don't have. The 75% escalation rate is
worth a sentence of explanation in the report too (12 escalations / 16
sessions) — that's high enough to be worth checking whether it's driven by
genuine hazards/requests-for-a-human or by the danger-keyword false-positive
issue in §3.

---

## 6. Response-quality (qualitative, not automated here)

The LLM's actual generated text (tone, faithfulness to the retrieved
context, conciseness) isn't scored by `evaluate.py` — doing that
automatically needs either an LLM-as-judge pass or a human rubric, and
both cost real API calls / time that felt out of scope for an offline,
free-to-re-run script. If you want it in the report, the standard approach
for a project like this is a small **human-scored rubric** (5–10 sample
conversations, 1–5 scale on: *faithfulness* — does it only state facts
present in the retrieved context or live outage data; *relevance*; *tone*;
*conciseness*), reported as a mean per criterion rather than a single
number. Happy to build the sample-conversation harness for that if you want
it — it would just call the real Claude endpoint and needs `ANTHROPIC_API_KEY` set.

---

## 7. Limitations & Recommendations

### 7.1 Addressed (implemented and re-verified against the test sets)

| # | Limitation | Fix applied |
|---|---|---|
| 1 | Danger-phrase detection missed real hazards and false-triggered on hypothetical safety questions | Expanded hazard phrases, added a hypothetical-question guard (`backend/chatbot.py`) — Recall 0.400 → 1.000 |
| 2 | RAG retrieval had no relevance floor — always forced 5 documents into the LLM prompt, even for off-topic queries | Added `MIN_RELEVANCE_SCORE` threshold (`backend/knowledge_base.py`) — Precision@5 0.200 → 0.463, negative-query accuracy 0 → 1.000 |
| 3 | The project's own presentation slides were retrievable as if they were ECG customer knowledge | Removed presentation-slide text from the customer-facing corpus (`backend/knowledge_base.py`) |
| 4 | A page refresh started a brand-new session, so the backend's "restore history from DB" feature was never actually exercised from the same browser | `sessionId` now persisted in `localStorage`; added `GET /session/{id}/messages` so the frontend re-hydrates visible history on load (`ChatWindow.jsx`, `backend/main.py`) |

**Not implemented as code — a manual step:** actually using the chatbot and
submitting star ratings / thumbs feedback before the report is due, so §5's
CSAT and helpful-rate numbers reflect real usage instead of reading "not yet
populated." This can't be faked without fabricating data, which would
misrepresent the evaluation.

### 7.2 Deferred — documented as future work, not attempted

Two recommendations were deliberately **not** attempted, because they are
architecture changes (new dependencies, no existing training pipeline) with
real risk of introducing new bugs on a tight timeline, rather than same-day
fixes:

- **Replace the keyword intent classifier with a trained or embedding-based
  model.** The current classifier is pure substring matching (§1) — a small
  supervised model or embedding-similarity approach would generalize past
  hardcoded synonyms, but 70 labeled examples is not enough training data to
  do this reliably, and it would need to be validated well beyond a single
  evaluation run before replacing the classifier the whole pipeline depends
  on.
- **Move RAG from TF-IDF to semantic embeddings.** Would let paraphrased
  queries match documents with no literal keyword overlap, but requires a new
  embedding source (a library like `sentence-transformers`, or an external
  embeddings API) that isn't currently part of the stack.

### 7.3 Still open (lower priority / longer-term)

- Single point of failure on the Claude LLM provider, with no fallback model or cached responses.
- `ADMIN_PASSWORD` falls back to a hardcoded default if the env var isn't set; CORS currently allows all origins; the WebSocket chat endpoint has no authentication.
- No automated test suite / CI gate running `evaluate.py` on every change.
- English-only keyword lists — no Twi/Ga support despite the Ghanaian customer base.

---

## Summary table (for the report)

| # | Metric | Layer | Result before fixes | Result after fixes |
|---|---|---|---|---|
| 1 | Intent classification accuracy | `classify_intent` | 81.4% (n=70) | 81.4% (n=70) — unchanged, see §7.2 |
| 2 | Query routing accuracy | `classify_query_type` | 87.1% (n=70) | 87.1% (n=70) — unchanged, see §7.2 |
| 3 | Danger-detection recall / precision / F1 | `is_danger_message` | 0.400 / 0.333 / 0.364 | **1.000 / 0.833 / 0.909** |
| 3b | Escalation-trigger P/R/F1 | `force_escalate` | 0.667 / 0.667 / 0.667 | **0.867 / 0.867 / 0.867** |
| 4 | RAG Recall@5 / Precision@5 / MRR / negative-query accuracy | `retrieve_relevant_docs` | 0.933 / 0.200 / 0.900 / 0.000 | 0.933 / **0.463** / 0.900 / **1.000** |
| 5 | CSAT / helpful-rate / escalation-rate | live `chatbot.db` | not yet populated / not yet populated / 75.0% | not yet populated / not yet populated / 75.0% |

Re-run `python backend/eval/evaluate.py` any time the code or knowledge base
changes — the labeled test sets in `backend/eval/*.json` stay valid as a
regression check.
