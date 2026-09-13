"""Evaluation pipeline comparing agent predictions against dataset/sample_requests.csv.
Computes field-by-field accuracy, confusion matrices, and validation scores.
"""
import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Ensure repo root on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from code.config import DATASET_DIR
from code.data.loader import load_all_data, load_requests
from code.engine.optimizer import evaluate_request
from code.reasoning.explainer import generate_decision_explanation

def run_evaluation(dataset_dir: Path = DATASET_DIR) -> Dict[str, float]:
    """Evaluates the decision pipeline against sample_requests.csv."""
    sample_file = dataset_dir / "sample_requests.csv"
    if not sample_file.exists():
        print(f"Error: {sample_file} not found.")
        sys.exit(1)

    print(f"Loading data from {dataset_dir}...")
    profiles, events_by_user, rates, req_options, message_insights = load_all_data(dataset_dir)
    sample_requests = load_requests("sample_requests.csv", dataset_dir)

    # Load ground truth
    ground_truth: Dict[str, dict] = {}
    with open(sample_file, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ground_truth[r["request_id"]] = r

    n_samples = len(sample_requests)
    print(f"Running evaluation against {n_samples} ground-truth benchmark requests...\n")

    correct_status = 0
    correct_method = 0
    correct_plan = 0
    correct_earliest = 0
    correct_changes = 0
    close_amount = 0
    exact_decision = 0

    results = []

    for req in sample_requests:
        rid = req.request_id
        gt = ground_truth[rid]
        profile = profiles[req.user_id]
        events = events_by_user.get(req.user_id, [])
        options = req_options.get(rid, [])
        insights = message_insights.get(req.user_id)
        events_by_id = {e.event_id: e for e in events}

        safe_amt, status, method, plan, earliest, changes, chosen_opt = evaluate_request(
            req, profile, events, options, insights
        )
        explanation = generate_decision_explanation(
            req,
            profile,
            safe_amt,
            status,
            method,
            plan,
            earliest,
            changes,
            events_by_id,
            chosen_opt,
        )

        gt_safe = float(gt["amount_safe_to_pay"])
        gt_status = gt["affordability_status"].strip()
        gt_method = gt["recommended_payment_method"].strip()
        gt_plan = gt["payment_plan"].strip()
        gt_earliest = gt["earliest_date_for_full_payment"].strip()
        gt_changes = gt["spending_changes_needed"].strip()

        m_status = (status == gt_status)
        m_method = (method == gt_method)
        m_plan = (plan == gt_plan)
        m_earliest = (earliest == gt_earliest)
        m_changes = (changes == gt_changes)
        m_amount = abs(safe_amt - gt_safe) <= max(1.0, 0.05 * gt_safe)
        m_full_decision = m_status and m_method

        if m_status:
            correct_status += 1
        if m_method:
            correct_method += 1
        if m_plan:
            correct_plan += 1
        if m_earliest:
            correct_earliest += 1
        if m_changes:
            correct_changes += 1
        if m_amount:
            close_amount += 1
        if m_full_decision:
            exact_decision += 1

        results.append({
            "request_id": rid,
            "status_match": m_status,
            "method_match": m_method,
            "plan_match": m_plan,
            "pred_status": status,
            "gt_status": gt_status,
            "pred_method": method,
            "gt_method": gt_method,
        })

    # Summary table
    print("=" * 80)
    print("HACKERRANK ORCHESTRATE — BUY OR WAIT? EVALUATION BENCHMARK")
    print("=" * 80)
    print(f"{'Metric':<35} | {'Correct':<10} | {'Total':<8} | {'Accuracy (%)':<12}")
    print("-" * 80)
    print(f"{'Affordability Status':<35} | {correct_status:<10} | {n_samples:<8} | {correct_status/n_samples*100:6.1f}%")
    print(f"{'Payment Method':<35} | {correct_method:<10} | {n_samples:<8} | {correct_method/n_samples*100:6.1f}%")
    print(f"{'Status + Method Match':<35} | {exact_decision:<10} | {n_samples:<8} | {exact_decision/n_samples*100:6.1f}%")
    print(f"{'Payment Plan Structure':<35} | {correct_plan:<10} | {n_samples:<8} | {correct_plan/n_samples*100:6.1f}%")
    print(f"{'Spending Changes Needed':<35} | {correct_changes:<10} | {n_samples:<8} | {correct_changes/n_samples*100:6.1f}%")
    print(f"{'Earliest Date for Full Payment':<35} | {correct_earliest:<10} | {n_samples:<8} | {correct_earliest/n_samples*100:6.1f}%")
    print(f"{'Safe Amount Headroom (within 5%)':<35} | {close_amount:<10} | {n_samples:<8} | {close_amount/n_samples*100:6.1f}%")
    print("=" * 80)

    print("\nDetailed Per-Request Verification:")
    print(f"{'Request ID':<12} | {'Status Pred':<22} | {'Status GT':<22} | {'Match'}")
    print("-" * 70)
    for r in results:
        mark = "[PASS]" if (r["status_match"] and r["method_match"]) else "[DIFF]"
        print(f"{r['request_id']:<12} | {r['pred_status']:<22} | {r['gt_status']:<22} | {mark}")


    metrics = {
        "status_accuracy": correct_status / n_samples,
        "method_accuracy": correct_method / n_samples,
        "decision_accuracy": exact_decision / n_samples,
        "plan_accuracy": correct_plan / n_samples,
        "spending_accuracy": correct_changes / n_samples,
    }
    return metrics

def main():
    parser = argparse.ArgumentParser(description="Evaluate Buy or Wait? agent against sample_requests.csv")
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=DATASET_DIR,
        help="Path to dataset directory (default: dataset/)",
    )
    args = parser.parse_args()
    run_evaluation(args.dataset_dir)

if __name__ == "__main__":
    main()
