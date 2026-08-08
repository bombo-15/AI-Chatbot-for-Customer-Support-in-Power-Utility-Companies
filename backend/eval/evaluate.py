"""
Offline evaluation harness for the Kanea chatbot.

Measures the pieces of the pipeline that can be scored without calling the
Groq API:
  1. Intent classification (classify_intent)          -> accuracy, per-class P/R/F1, confusion matrix
  2. End-to-end query routing (classify_query_type)     -> routing accuracy (using the *predicted* intent, so
                                                            intent-classifier mistakes propagate, same as production)
  3. Danger / escalation detection (is_danger_message)  -> precision, recall, F1 on the safety-critical path
  4. RAG retrieval (knowledge_base.retrieve_relevant_docs) -> Precision@k, Recall@k, Hit@k, MRR
  5. Live operational metrics already logged in chatbot.db (satisfaction, feedback, escalation rate)

Run from anywhere:
    python eval/evaluate.py
    python backend/eval/evaluate.py
"""

import json
import os
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
os.chdir(BACKEND_DIR)          # so database.py's relative "chatbot.db" resolves correctly
sys.path.insert(0, str(BACKEND_DIR))

import chatbot            # noqa: E402
import knowledge_base      # noqa: E402
import database as db      # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent


# ─── helpers ──────────────────────────────────────────────────────────────────

def load_cases(filename: str) -> list[dict]:
    return json.loads((EVAL_DIR / filename).read_text(encoding="utf-8"))


def prf1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return round(precision, 3), round(recall, 3), round(f1, 3)


# ─── 1 & 2: intent classification + routing ──────────────────────────────────

def evaluate_intents(cases: list[dict]) -> dict:
    labels = sorted({c["expected_intent"] for c in cases})
    confusion = {gold: {pred: 0 for pred in labels} for gold in labels}

    intent_correct = 0
    routing_correct = 0
    danger_tp = danger_fp = danger_fn = danger_tn = 0
    escalate_tp = escalate_fp = escalate_fn = escalate_tn = 0
    per_case = []

    for c in cases:
        text = c["text"]
        gold_intent = c["expected_intent"]
        gold_query_type = c["expected_query_type"]
        gold_danger = c.get("expected_danger", False)
        gold_escalate = gold_danger or gold_query_type == "escalation"

        pred_intent = chatbot.classify_intent(text)
        pred_query_type = chatbot.classify_query_type(pred_intent, text)
        pred_danger = chatbot.is_danger_message(text)
        pred_escalate = pred_danger or pred_query_type == "escalation"

        confusion[gold_intent][pred_intent] = confusion[gold_intent].get(pred_intent, 0) + 1
        if pred_intent == gold_intent:
            intent_correct += 1
        if pred_query_type == gold_query_type:
            routing_correct += 1

        if gold_danger and pred_danger:
            danger_tp += 1
        elif not gold_danger and pred_danger:
            danger_fp += 1
        elif gold_danger and not pred_danger:
            danger_fn += 1
        else:
            danger_tn += 1

        if gold_escalate and pred_escalate:
            escalate_tp += 1
        elif not gold_escalate and pred_escalate:
            escalate_fp += 1
        elif gold_escalate and not pred_escalate:
            escalate_fn += 1
        else:
            escalate_tn += 1

        if pred_intent != gold_intent or pred_query_type != gold_query_type or pred_danger != gold_danger:
            per_case.append({
                "id": c["id"], "text": text,
                "gold_intent": gold_intent, "pred_intent": pred_intent,
                "gold_query_type": gold_query_type, "pred_query_type": pred_query_type,
                "gold_danger": gold_danger, "pred_danger": pred_danger,
            })

    n = len(cases)
    per_class = {}
    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[g][label] for g in labels if g != label)
        fn = sum(v for k, v in confusion[label].items() if k != label)
        p, r, f1 = prf1(tp, fp, fn)
        per_class[label] = {"precision": p, "recall": r, "f1": f1, "support": sum(confusion[label].values())}

    return {
        "n_cases": n,
        "intent_accuracy": round(intent_correct / n, 3),
        "routing_accuracy": round(routing_correct / n, 3),
        "per_class": per_class,
        "confusion_matrix": confusion,
        "danger_detection": dict(zip(("precision", "recall", "f1"), prf1(danger_tp, danger_fp, danger_fn)),
                                  tp=danger_tp, fp=danger_fp, fn=danger_fn, tn=danger_tn),
        "escalation_detection": dict(zip(("precision", "recall", "f1"), prf1(escalate_tp, escalate_fp, escalate_fn)),
                                      tp=escalate_tp, fp=escalate_fp, fn=escalate_fn, tn=escalate_tn),
        "mismatches": per_case,
    }


# ─── 3: RAG retrieval ─────────────────────────────────────────────────────────

def evaluate_retrieval(cases: list[dict], top_n: int = 5) -> dict:
    precisions, recalls, hits, reciprocal_ranks = [], [], [], []
    per_case = []

    for c in cases:
        expected = set(c["expected_sources"])
        docs = knowledge_base.retrieve_relevant_docs(c["query"], top_n=top_n)
        retrieved = [d["id"] for d in docs]
        retrieved_set = set(retrieved)

        if not expected:
            # Negative case: nothing in the KB should match. Correct = empty result.
            ok = len(retrieved_set) == 0
            per_case.append({"id": c["id"], "query": c["query"], "expected": [], "retrieved": retrieved, "ok": ok})
            continue

        overlap = expected & retrieved_set
        precision = len(overlap) / len(retrieved_set) if retrieved_set else 0.0
        recall = len(overlap) / len(expected)
        hit = 1 if overlap else 0

        rr = 0.0
        for rank, doc_id in enumerate(retrieved, start=1):
            if doc_id in expected:
                rr = 1 / rank
                break

        precisions.append(precision)
        recalls.append(recall)
        hits.append(hit)
        reciprocal_ranks.append(rr)
        per_case.append({
            "id": c["id"], "query": c["query"], "expected": sorted(expected),
            "retrieved": retrieved, "precision": round(precision, 3), "recall": round(recall, 3),
        })

    negative_cases = [c for c in per_case if "precision" not in c]
    negative_accuracy = (
        round(sum(1 for c in negative_cases if c["ok"]) / len(negative_cases), 3)
        if negative_cases else None
    )

    return {
        "top_n": top_n,
        "n_positive_queries": len(precisions),
        f"precision_at_{top_n}": round(sum(precisions) / len(precisions), 3) if precisions else 0.0,
        f"recall_at_{top_n}": round(sum(recalls) / len(recalls), 3) if recalls else 0.0,
        f"hit_at_{top_n}": round(sum(hits) / len(hits), 3) if hits else 0.0,
        "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 3) if reciprocal_ranks else 0.0,
        "negative_query_accuracy": negative_accuracy,
        "per_case": per_case,
    }


# ─── 4: live operational metrics (from chatbot.db) ───────────────────────────

def live_metrics() -> dict:
    try:
        db.init_db()
        return db.get_analytics()
    except Exception as exc:
        return {"error": str(exc)}


# ─── report printing ──────────────────────────────────────────────────────────

def print_report(intent_results: dict, retrieval_results: dict, live: dict) -> None:
    print("=" * 70)
    print("KANEA CHATBOT — OFFLINE EVALUATION REPORT")
    print("=" * 70)

    print(f"\n[1] Intent classification  (n={intent_results['n_cases']})")
    print(f"    Accuracy: {intent_results['intent_accuracy'] * 100:.1f}%")
    print(f"    {'intent':<15}{'precision':>10}{'recall':>10}{'f1':>10}{'support':>10}")
    for label, m in sorted(intent_results["per_class"].items()):
        print(f"    {label:<15}{m['precision']:>10.3f}{m['recall']:>10.3f}{m['f1']:>10.3f}{m['support']:>10}")

    print(f"\n[2] End-to-end query routing accuracy: {intent_results['routing_accuracy'] * 100:.1f}%")
    print("    (uses the intent the classifier actually predicted, so classifier errors propagate)")

    dd = intent_results["danger_detection"]
    print(f"\n[3] Danger-phrase detection (is_danger_message)")
    print(f"    Precision: {dd['precision']:.3f}  Recall: {dd['recall']:.3f}  F1: {dd['f1']:.3f}  "
          f"(TP={dd['tp']} FP={dd['fp']} FN={dd['fn']} TN={dd['tn']})")

    ed = intent_results["escalation_detection"]
    print(f"\n[3b] Human-escalation trigger (danger OR escalation intent)")
    print(f"    Precision: {ed['precision']:.3f}  Recall: {ed['recall']:.3f}  F1: {ed['f1']:.3f}  "
          f"(TP={ed['tp']} FP={ed['fp']} FN={ed['fn']} TN={ed['tn']})")

    if intent_results["mismatches"]:
        print(f"\n    Mismatched cases ({len(intent_results['mismatches'])}):")
        for m in intent_results["mismatches"]:
            print(f"      [{m['id']}] \"{m['text']}\"")
            print(f"          intent: gold={m['gold_intent']!r} pred={m['pred_intent']!r} | "
                  f"route: gold={m['gold_query_type']!r} pred={m['pred_query_type']!r} | "
                  f"danger: gold={m['gold_danger']} pred={m['pred_danger']}")

    k = retrieval_results["top_n"]
    print(f"\n[4] RAG retrieval (top_n={k}, {retrieval_results['n_positive_queries']} positive queries)")
    print(f"    Precision@{k}: {retrieval_results[f'precision_at_{k}']:.3f}")
    print(f"    Recall@{k}:    {retrieval_results[f'recall_at_{k}']:.3f}")
    print(f"    Hit@{k}:       {retrieval_results[f'hit_at_{k}']:.3f}")
    print(f"    MRR:            {retrieval_results['mrr']:.3f}")
    if retrieval_results["negative_query_accuracy"] is not None:
        print(f"    Negative-query accuracy (off-topic questions correctly return nothing): "
              f"{retrieval_results['negative_query_accuracy']:.3f}")

    print(f"\n[5] Live operational metrics (from chatbot.db)")
    if "error" in live:
        print(f"    Could not read chatbot.db: {live['error']}")
    else:
        print(f"    Total sessions:         {live['total_sessions']}")
        print(f"    Total user messages:    {live['total_messages']}")
        print(f"    Avg satisfaction (1-5): {live['avg_satisfaction']}  (n={live['total_ratings']})")
        print(f"    Helpful feedback rate:  {live['accuracy_percent']}%  "
              f"(helpful={live['helpful_count']}, unhelpful={live['unhelpful_count']})")
        print(f"    Escalation rate:        {live['escalation_rate']}%  (n={live['total_escalations']})")
        print(f"    Intent distribution:    {live['intent_distribution']}")
        if live["total_ratings"] == 0:
            print("    (No ratings yet — this fills in once real users chat and submit /chat-rating feedback.)")

    print("\n" + "=" * 70)


def main() -> None:
    intent_cases = load_cases("test_intents.json")
    retrieval_cases = load_cases("test_retrieval.json")

    intent_results = evaluate_intents(intent_cases)
    retrieval_results = evaluate_retrieval(retrieval_cases, top_n=5)
    live = live_metrics()

    print_report(intent_results, retrieval_results, live)

    out = {
        "intent_classification": intent_results,
        "retrieval": retrieval_results,
        "live_metrics": live,
    }
    out_path = EVAL_DIR / "results.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Full results written to {out_path}")


if __name__ == "__main__":
    main()
