"""
Response-quality evaluation for the Kanea chatbot: ROUGE-1, ROUGE-2, and BERTScore.

Unlike evaluate.py (which scores the deterministic keyword/routing/retrieval
layers offline), this script scores the *generated text* of the final Groq
LLM response against a hand-written gold reference answer, for a set of 20
static (RAG-answerable) queries grounded in the ECG + PURC knowledge base
(backend/eval/test_response_quality.json).

Requires:
  - GROQ_API_KEY set in backend/.env (makes real network calls to Groq)
  - rouge-score and bert-score installed (pip install rouge-score bert-score)

Run from anywhere:
    python eval/evaluate_response_quality.py
    python backend/eval/evaluate_response_quality.py
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
os.chdir(BACKEND_DIR)          # so database.py's relative "chatbot.db" resolves correctly
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(BACKEND_DIR / ".env")  # chatbot.py reads GROQ_API_KEY at import time, so this must run first

import chatbot            # noqa: E402
import database as db      # noqa: E402

if not chatbot.GROQ_API_KEY:
    sys.exit(
        "GROQ_API_KEY is not set (checked backend/.env). Response-quality evaluation needs "
        "the real Groq-backed pipeline, not the no-key fallback message, so it cannot proceed."
    )

from rouge_score import rouge_scorer   # noqa: E402
from bert_score import score as bert_score_fn  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
BERT_MODEL = "roberta-large"   # bert-score's default English model


def load_cases(filename: str) -> list[dict]:
    return json.loads((EVAL_DIR / filename).read_text(encoding="utf-8"))


def mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


# ─── Step 1: generate live candidate responses from the real chatbot pipeline ─

async def generate_candidates(cases: list[dict]) -> list[dict]:
    db.init_db()
    try:
        outages = db.get_all_outages()
    except Exception:
        outages = []

    results = []
    for i, c in enumerate(cases, 1):
        session_id = f"eval-quality-{c['id']}"
        chatbot.clear_session(session_id)
        print(f"  [{i}/{len(cases)}] {c['id']}: \"{c['query'][:60]}...\"" if len(c["query"]) > 60
              else f"  [{i}/{len(cases)}] {c['id']}: \"{c['query']}\"")
        try:
            resp = await chatbot.get_bot_response(session_id, c["query"], outages)
            candidate = resp["reply"].strip()
            error = None
        except Exception as exc:
            candidate = ""
            error = str(exc)
        results.append({
            **c,
            "candidate_answer": candidate,
            "intent": resp.get("intent") if not error else None,
            "query_type": resp.get("query_type") if not error else None,
            "rag_sources": [d["id"] for d in resp.get("rag_sources", [])] if not error else [],
            "error": error,
        })
        chatbot.clear_session(session_id)
        time.sleep(0.5)  # be polite to the Groq API rate limit
    return results


# ─── Step 2: ROUGE-1 / ROUGE-2 ─────────────────────────────────────────────────

def evaluate_rouge(results: list[dict]) -> dict:
    scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2"], use_stemmer=True)
    per_case = []
    r1p, r1r, r1f = [], [], []
    r2p, r2r, r2f = [], [], []

    for r in results:
        if r["error"] or not r["candidate_answer"]:
            continue
        scores = scorer.score(r["reference_answer"], r["candidate_answer"])
        rouge1, rouge2 = scores["rouge1"], scores["rouge2"]
        per_case.append({
            "id": r["id"],
            "rouge1": {"precision": round(rouge1.precision, 4), "recall": round(rouge1.recall, 4), "f1": round(rouge1.fmeasure, 4)},
            "rouge2": {"precision": round(rouge2.precision, 4), "recall": round(rouge2.recall, 4), "f1": round(rouge2.fmeasure, 4)},
        })
        r1p.append(rouge1.precision); r1r.append(rouge1.recall); r1f.append(rouge1.fmeasure)
        r2p.append(rouge2.precision); r2r.append(rouge2.recall); r2f.append(rouge2.fmeasure)

    return {
        "per_case": per_case,
        "rouge1_avg": {"precision": mean(r1p), "recall": mean(r1r), "f1": mean(r1f)},
        "rouge2_avg": {"precision": mean(r2p), "recall": mean(r2r), "f1": mean(r2f)},
    }


# ─── Step 3: BERTScore ─────────────────────────────────────────────────────────

def evaluate_bertscore(results: list[dict]) -> dict:
    scored = [r for r in results if not r["error"] and r["candidate_answer"]]
    if not scored:
        return {"per_case": [], "bertscore_avg": {"precision": 0.0, "recall": 0.0, "f1": 0.0}, "model": BERT_MODEL}

    cands = [r["candidate_answer"] for r in scored]
    refs = [r["reference_answer"] for r in scored]

    P, R, F1 = bert_score_fn(cands, refs, lang="en", model_type=BERT_MODEL, verbose=False)

    per_case = []
    for r, p, rec, f1 in zip(scored, P.tolist(), R.tolist(), F1.tolist()):
        per_case.append({
            "id": r["id"],
            "precision": round(p, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        })

    return {
        "per_case": per_case,
        "bertscore_avg": {
            "precision": mean(P.tolist()),
            "recall": mean(R.tolist()),
            "f1": mean(F1.tolist()),
        },
        "model": BERT_MODEL,
    }


# ─── report printing ──────────────────────────────────────────────────────────

def print_report(results: list[dict], rouge_results: dict, bert_results: dict) -> None:
    n_ok = sum(1 for r in results if not r["error"] and r["candidate_answer"])
    n_err = len(results) - n_ok

    print("=" * 78)
    print("KANEA CHATBOT — RESPONSE-QUALITY EVALUATION (ROUGE-1 / ROUGE-2 / BERTScore)")
    print("=" * 78)
    print(f"\nCases: {len(results)}  |  Scored: {n_ok}  |  Failed/skipped: {n_err}")

    print(f"\n{'id':<6}{'ROUGE-1 F1':>12}{'ROUGE-2 F1':>12}{'BERTScore F1':>14}")
    rouge_by_id = {c["id"]: c for c in rouge_results["per_case"]}
    bert_by_id = {c["id"]: c for c in bert_results["per_case"]}
    for r in results:
        rid = r["id"]
        r1 = rouge_by_id.get(rid, {}).get("rouge1", {}).get("f1")
        r2 = rouge_by_id.get(rid, {}).get("rouge2", {}).get("f1")
        bf = bert_by_id.get(rid, {}).get("f1")
        if r1 is None:
            print(f"{rid:<6}{'FAILED':>12}")
            continue
        print(f"{rid:<6}{r1:>12.4f}{r2:>12.4f}{bf:>14.4f}")

    r1a, r2a, ba = rouge_results["rouge1_avg"], rouge_results["rouge2_avg"], bert_results["bertscore_avg"]
    print("\nAverages across all scored cases:")
    print(f"  ROUGE-1   Precision={r1a['precision']:.4f}  Recall={r1a['recall']:.4f}  F1={r1a['f1']:.4f}")
    print(f"  ROUGE-2   Precision={r2a['precision']:.4f}  Recall={r2a['recall']:.4f}  F1={r2a['f1']:.4f}")
    print(f"  BERTScore Precision={ba['precision']:.4f}  Recall={ba['recall']:.4f}  F1={ba['f1']:.4f}  (model={bert_results['model']})")
    print("\n" + "=" * 78)


def main() -> None:
    cases = load_cases("test_response_quality.json")

    print(f"Generating {len(cases)} live responses from the real Kanea/Groq pipeline...")
    results = asyncio.run(generate_candidates(cases))

    print("\nScoring with ROUGE-1 / ROUGE-2...")
    rouge_results = evaluate_rouge(results)

    print("Scoring with BERTScore (downloads/loads the scoring model on first run)...")
    bert_results = evaluate_bertscore(results)

    print_report(results, rouge_results, bert_results)

    out = {
        "cases": results,
        "rouge": rouge_results,
        "bertscore": bert_results,
    }
    out_path = EVAL_DIR / "results_response_quality.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Full results written to {out_path}")


if __name__ == "__main__":
    main()
