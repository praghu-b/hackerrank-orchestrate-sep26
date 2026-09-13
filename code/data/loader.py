"""Data loader for ingesting and validating all challenge CSV datasets.
"""
import csv
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from code.config import DATASET_DIR
from code.models.schemas import (
    FinancialProfile,
    FinancialEvent,
    PaymentOption,
    Message,
    Request,
)
from code.data.image_extractor import get_image_amount

def parse_date(d_str: str) -> Optional[date]:
    if not d_str or not d_str.strip():
        return None
    try:
        return datetime.strptime(d_str.strip(), "%Y-%m-%d").date()
    except Exception:
        return None

def load_exchange_rates(dataset_dir: Path = DATASET_DIR) -> Dict[Tuple[str, str, str], float]:
    path = dataset_dir / "exchange_rates.csv"
    rates: Dict[Tuple[str, str, str], float] = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = (r["rate_date"].strip(), r["from_currency"].strip(), r["to_currency"].strip())
            rates[key] = float(r["rate"])
    return rates

def load_financial_profiles(dataset_dir: Path = DATASET_DIR) -> Dict[str, FinancialProfile]:
    path = dataset_dir / "financial_profiles.csv"
    profiles: Dict[str, FinancialProfile] = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            uid = r["user_id"].strip()
            priorities = [p.strip() for p in r["financial_priorities"].split("|") if p.strip()]
            protect = [p.strip() for p in r["expense_categories_to_protect"].split("|") if p.strip()]
            reduce_cats = [p.strip() for p in r["expense_categories_user_is_willing_to_reduce"].split("|") if p.strip()]
            stop_cats = [p.strip() for p in r["expense_categories_user_is_willing_to_stop"].split("|") if p.strip()]
            methods = [m.strip() for m in r["payment_methods_user_will_consider"].split("|") if m.strip()]
            max_inst = int(r["max_installment_months"].strip()) if r["max_installment_months"].strip() else None

            profiles[uid] = FinancialProfile(
                user_id=uid,
                home_currency=r["home_currency"].strip(),
                current_available_balance=float(r["current_available_balance"]),
                minimum_balance_to_keep=float(r["minimum_balance_to_keep"]),
                financial_priorities=priorities,
                expense_categories_to_protect=protect,
                expense_categories_user_is_willing_to_reduce=reduce_cats,
                expense_categories_user_is_willing_to_stop=stop_cats,
                payment_methods_user_will_consider=methods,
                max_installment_months=max_inst,
            )
    return profiles

def load_financial_events(
    profiles: Dict[str, FinancialProfile],
    rates: Dict[Tuple[str, str, str], float],
    dataset_dir: Path = DATASET_DIR,
) -> Dict[str, List[FinancialEvent]]:
    path = dataset_dir / "financial_events.csv"
    events_by_user: Dict[str, List[FinancialEvent]] = {}
    
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            eid = r["event_id"].strip()
            uid = r["user_id"].strip()
            curr = r["currency"].strip()
            home_curr = profiles[uid].home_currency
            
            # Amount handling (resolve from images if blank)
            raw_amt_str = r["amount"].strip()
            if raw_amt_str:
                amt = float(raw_amt_str)
            else:
                img_amt = get_image_amount(eid)
                amt = img_amt if img_amt is not None else 0.0
            
            event_d = parse_date(r["event_date"])
            settle_d = parse_date(r["settlement_date"]) or event_d
            settle_d_str = settle_d.strftime("%Y-%m-%d") if settle_d else ""
            
            # Currency conversion
            if curr == home_curr:
                converted_amt = amt
            else:
                rate = rates.get((settle_d_str, curr, home_curr), 1.0)
                converted_amt = amt * rate

            min_amt_str = r["minimum_allowed_amount"].strip()
            min_amt = float(min_amt_str) if min_amt_str else None

            event = FinancialEvent(
                event_id=eid,
                user_id=uid,
                event_type=r["event_type"].strip(),
                description=r["description"].strip(),
                category=r["category"].strip(),
                direction=r["direction"].strip(),
                amount=amt,
                currency=curr,
                event_date=event_d,
                settlement_date=settle_d,
                status=r["status"].strip(),
                linked_event_id=r["linked_event_id"].strip() if r["linked_event_id"].strip() else None,
                flexibility=r["flexibility"].strip() if r["flexibility"].strip() else "fixed",
                minimum_allowed_amount=min_amt,
                converted_amount=converted_amt,
            )
            events_by_user.setdefault(uid, []).append(event)

    return events_by_user

def load_payment_options(dataset_dir: Path = DATASET_DIR) -> Dict[str, List[PaymentOption]]:
    path = dataset_dir / "request_payment_options.csv"
    options_by_req: Dict[str, List[PaymentOption]] = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rid = r["request_id"].strip()
            freq_str = r["payment_frequency_days"].strip()
            freq = int(freq_str) if freq_str else None

            opt = PaymentOption(
                payment_option_id=r["payment_option_id"].strip(),
                request_id=rid,
                payment_method=r["payment_method"].strip(),
                payment_amount=float(r["payment_amount"]),
                number_of_payments=int(r["number_of_payments"]),
                first_payment_date=parse_date(r["first_payment_date"]),
                payment_frequency_days=freq,
                financing_fee=float(r["financing_fee"]),
                total_payable_amount=float(r["total_payable_amount"]),
            )
            options_by_req.setdefault(rid, []).append(opt)
    return options_by_req

def load_messages(dataset_dir: Path = DATASET_DIR) -> List[Message]:
    path = dataset_dir / "messages.csv"
    messages: List[Message] = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            messages.append(Message(
                message_id=r["message_id"].strip(),
                user_id=r["user_id"].strip(),
                request_id=r["request_id"].strip() if r["request_id"].strip() else None,
                related_event_id=r["related_event_id"].strip() if r["related_event_id"].strip() else None,
                sent_at=r["sent_at"].strip(),
                source_type=r["source_type"].strip(),
                message_text=r["message_text"].strip(),
            ))
    return messages

def load_requests(filename: str = "requests.csv", dataset_dir: Path = DATASET_DIR) -> List[Request]:
    path = dataset_dir / filename
    requests: List[Request] = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            allows_partial = r["allows_partial_payment"].strip().lower() in {"true", "1", "yes"}
            requests.append(Request(
                request_id=r["request_id"].strip(),
                user_id=r["user_id"].strip(),
                request_date=parse_date(r["request_date"]),
                request_type=r["request_type"].strip(),
                requested_amount=float(r["requested_amount"]),
                desired_completion_date=parse_date(r["desired_completion_date"]),
                allows_partial_payment=allows_partial,
                request_text=r["request_text"].strip(),
            ))
    return requests
