import os
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "dataset"
MEDIA_DIR = DATASET_DIR / "media" / "images"
OUTPUT_CSV_PATH = REPO_ROOT / "output.csv"
USAGE_REPORT_PATH = REPO_ROOT / "code" / "evaluation" / "usage_report.md"

# Supported Currencies
SUPPORTED_CURRENCIES = {"INR", "ZAR", "IDR", "USD", "EUR"}

# Allowed Affordability Statuses
STATUS_AFFORDABLE_NOW = "affordable_now"
STATUS_AFFORDABLE_WITH_PLAN = "affordable_with_plan"
STATUS_AFFORDABLE_LATER = "affordable_later"
STATUS_NOT_AFFORDABLE = "not_affordable"

# Allowed Payment Methods
METHOD_FULL_PAYMENT = "full_payment"
METHOD_PARTIAL_PAYMENT = "partial_payment"
METHOD_INSTALLMENTS = "installments"
METHOD_WAIT = "wait"
METHOD_NOT_RECOMMENDED = "not_recommended"

# Forecast Window
FORECAST_DAYS = 90

# Output Column Order
OUTPUT_COLUMNS = [
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation",
]
