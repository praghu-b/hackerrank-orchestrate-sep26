# Buy or Wait? — AI-Powered Financial Decision Agent

Starter & Solution repository for the **HackerRank Orchestrate** hackathon challenge: **Buy or Wait?**

An intelligent financial reasoning system that decides whether a user can safely afford a requested expense on a given date by reconstructing their financial position, forecasting a 90-day cash flow, accounting for recurring commitments and payment options, extracting evidence from messages and media images, optimizing payment methods, and providing clear, grounded explanations.

---

## 1. System Architecture

The solution uses a hybrid architecture combining a high-precision deterministic financial simulation engine with grounded AI explanation synthesis:

1. **Context & Ingestion Layer (`code/data/`)**:
   - Ingests user profiles, historical/pending events, fixed dated exchange rates, seller payment options, and supporting messages/images.
   - Normalizes foreign currency transactions using exact rates from `exchange_rates.csv`.
   - Extracts verified amounts from receipt/invoice images for events missing values.
   - Analyzes messages to extract salary adjustments, lease changes, and payment updates according to conflict resolution precedence.

2. **Simulation & Cash Flow Engine (`code/engine/`)**:
   - **State Reconstructor**: Separates settled vs. pending transactions, reserves pending debits, ignores non-cash/unrealized gains, and counts confirmed salary strictly on settlement dates.
   - **Cash Flow Forecaster**: Projects daily cash balances over the 90-day evaluation horizon, identifying recurring frequencies (rent, utilities, groceries, transport, dining, subscriptions).
   - **Safety Checker**: Evaluates balance against `minimum_balance_to_keep` at each day; calculates `amount_safe_to_pay` and conservative `earliest_date_for_full_payment`.
   - **Optimizer**: Evaluates eligible options (`full_payment`, `partial_payment`, `installments`, `wait`, `not_recommended`) against user preferences and `max_installment_months`.
   - **Spending Adjuster**: If needed, identifies up to 3 non-protected flexible expenses to stop or reduce.

3. **Reasoning & Explainer Layer (`code/reasoning/`)**:
   - Formats concise, audit-ready explanations highlighting amounts safe today, minimum balance buffers, exact dates, and required spending actions.

4. **Evaluation & Reporting Layer (`code/evaluation/`)**:
   - Evaluates performance against the 25 solved cases in `dataset/sample_requests.csv`.
   - Produces `evaluation/usage_report.md` tracking model calls, tokens, and cost.

---

## 2. Directory Layout

```text
.
├── AGENTS.md                         # Rules for AI coding tools + transcript logging
├── problem_statement.md              # Full challenge statement
├── README.md                         # Project documentation and run guide
├── log.txt                           # Conversation transcript log (gitignored)
├── output.csv                        # Final generated predictions (250 rows)
├── dataset/                          # Input data files and media
│   ├── requests.csv                  # 250 requests to evaluate
│   ├── sample_requests.csv           # 25 solved examples for evaluation
│   ├── financial_profiles.csv        # Balances, minimum balance, preferences
│   ├── financial_events.csv          # Transactions, payroll, subscriptions
│   ├── request_payment_options.csv   # Installment and full payment offers
│   ├── exchange_rates.csv            # Fixed dated conversion rates
│   ├── messages.csv                  # Communication records
│   ├── images.csv                    # Media image metadata
│   └── media/images/                 # Receipts, invoices, payslips (.png)
└── code/                             # Solution implementation
    ├── main.py                       # Main CLI entry point: produces output.csv
    ├── config.py                     # Constants, currencies, paths
    ├── models/                       # Schemas and domain objects
    ├── data/                         # CSV loaders, image extractor, message analyzer
    ├── engine/                       # Cashflow projection, safety checker, optimizer
    ├── reasoning/                    # Explanation generation
    ├── utils/                        # Packaging and helper utilities
    └── evaluation/
        ├── main.py                   # Self-evaluation against sample_requests.csv
        └── usage_report.md           # Model usage, token counts, and cost breakdown
```

---

## 3. Quick Start

### Prerequisites
- Python 3.10+ (tested on Python 3.11)
- Standard library dependencies (`csv`, `json`, `datetime`, `re`, `math`, `typing`, `collections`, `os`, `sys`)
- Optional packages (already available): `pillow`, `google-generativeai`

### Run Predictions
To generate the final `output.csv` in the repository root:

```bash
python code/main.py
```

This reads `dataset/requests.csv` and all supporting datasets, and outputs `output.csv` with exactly 250 prediction rows matching the required schema.

### Run Evaluation
To score the system against the 25 public ground-truth examples:

```bash
python code/evaluation/main.py
```

### Package Submission
To build `code.zip` for submission:

```bash
python -m code.utils.packager
```

---

## 4. Submission Checklist

- [x] `.gitignore` configured to exclude `log.txt`, `.venv/`, `__pycache__/`, and temporary files.
- [x] `output.csv` generated in the repo root with exact columns and 250 rows.
- [x] All amounts satisfy `0 <= amount_safe_to_pay <= requested_amount`.
- [x] Installment plans strictly match options in `request_payment_options.csv`.
- [x] Spending changes target only non-protected flexible expenses.
- [x] `code/evaluation/usage_report.md` included with model tokens and cost summary.
- [x] `log.txt` maintained per `AGENTS.md` protocol.
