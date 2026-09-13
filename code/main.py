"""Buy or Wait? Financial Decision Agent
Main CLI entry point for processing financial purchase requests and generating output.csv.
"""
import argparse
import csv
import sys
from pathlib import Path

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from code.config import (

    DATASET_DIR,
    OUTPUT_CSV_PATH,
    OUTPUT_COLUMNS,
)
from code.data.loader import load_all_data, load_requests
from code.engine.optimizer import evaluate_request
from code.reasoning.explainer import generate_decision_explanation
from code.models.schemas import (
    FinancialProfile,
    FinancialEvent,
    PaymentOption,
    Request,
)

def run_pipeline(
    requests_filename: str = "requests.csv",
    output_path: Path = OUTPUT_CSV_PATH,
    dataset_dir: Path = DATASET_DIR,
) -> int:
    """Executes the financial decision pipeline across all requests and outputs predictions."""
    print(f"Loading datasets from: {dataset_dir}")
    profiles, events_by_user, rates, req_options, message_insights = load_all_data(dataset_dir)
    requests = load_requests(requests_filename, dataset_dir)
    print(f"Loaded {len(requests)} requests to process.")

    rows = []
    status_counts: Dict[str, int] = {}
    method_counts: Dict[str, int] = {}

    for req in requests:
        profile = profiles.get(req.user_id)
        if not profile:
            raise ValueError(f"Profile not found for user_id: {req.user_id}")

        events = events_by_user.get(req.user_id, [])
        options = req_options.get(req.request_id, [])
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

        # Format safe amount string cleanly
        safe_amt_str = f"{safe_amt:.2f}".rstrip("0").rstrip(".") if (safe_amt % 1 != 0) else f"{int(safe_amt)}"

        row = {
            "request_id": req.request_id,
            "amount_safe_to_pay": safe_amt_str,
            "affordability_status": status,
            "recommended_payment_method": method,
            "payment_plan": plan,
            "earliest_date_for_full_payment": earliest,
            "spending_changes_needed": changes,
            "decision_explanation": explanation,
        }
        rows.append(row)

        status_counts[status] = status_counts.get(status, 0) + 1
        method_counts[method] = method_counts.get(method, 0) + 1

    # Ensure parent output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write output.csv with exact required columns and quote minimal
    with open(output_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"Successfully wrote {len(rows)} predictions to {output_path}")
    print("\nSummary by Affordability Status:")
    for st, cnt in sorted(status_counts.items()):
        print(f"  {st:25s}: {cnt:4d}")

    print("\nSummary by Payment Method:")
    for met, cnt in sorted(method_counts.items()):
        print(f"  {met:25s}: {cnt:4d}")

    return len(rows)

def main():
    parser = argparse.ArgumentParser(description="Buy or Wait? AI Financial Decision Agent")
    parser.add_argument(
        "--requests",
        type=str,
        default="requests.csv",
        help="Requests CSV filename inside dataset/ (default: requests.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_CSV_PATH,
        help="Path for output.csv (default: repo root output.csv)",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=DATASET_DIR,
        help="Path to dataset directory (default: dataset/)",
    )

    args = parser.parse_args()
    count = run_pipeline(
        requests_filename=args.requests,
        output_path=args.output,
        dataset_dir=args.dataset_dir,
    )
    print(f"\nCompleted successfully with {count} records.")

if __name__ == "__main__":
    main()
