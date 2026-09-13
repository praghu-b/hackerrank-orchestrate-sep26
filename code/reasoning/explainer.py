"""Explanation generator for Buy or Wait? financial decision recommendations.
Generates concise, grounded explanations matching the tone and precision of the benchmark.
"""
from datetime import date
from typing import Dict, Optional, List

from code.models.schemas import (
    FinancialProfile,
    FinancialEvent,
    PaymentOption,
    Request,
)
from code.config import (
    STATUS_AFFORDABLE_NOW,
    STATUS_AFFORDABLE_WITH_PLAN,
    STATUS_AFFORDABLE_LATER,
    STATUS_NOT_AFFORDABLE,
    METHOD_FULL_PAYMENT,
    METHOD_PARTIAL_PAYMENT,
    METHOD_INSTALLMENTS,
    METHOD_WAIT,
    METHOD_NOT_RECOMMENDED,
)

def format_currency_amount(amount: float, currency: str) -> str:
    """Formats an amount with comma grouping, using 2 decimal places if not whole."""
    rounded = round(amount, 2)
    if rounded % 1 != 0:
        return f"{currency} {rounded:,.2f}"
    else:
        return f"{currency} {int(rounded):,}"

def format_date_human(d: date) -> str:
    """Formats a date as 'Day Month Year' (e.g. '8 August 2025')."""
    return f"{d.day} {d.strftime('%B')} {d.year}"

def generate_spending_description(
    changes_str: str,
    events_by_id: Dict[str, FinancialEvent],
    currency: str,
) -> str:
    """Formats spending changes (e.g. 'stop:event_476', 'reduce_to:event_989:665950')
    into human-readable English phrases.
    """
    if not changes_str or changes_str == "none":
        return ""

    actions = changes_str.split("|")
    phrases: List[str] = []

    for act in actions:
        parts = act.split(":")
        act_type = parts[0]
        event_id = parts[1]
        
        event = events_by_id.get(event_id)
        desc = event.description if event else "flexible expense"
        desc_clean = desc.strip()
        if desc_clean:
            desc_clean = desc_clean[0].lower() + desc_clean[1:]

        if act_type == "stop":
            phrases.append(f"stop the {desc_clean}")
        elif act_type == "reduce_to":
            new_amt = float(parts[2])
            amt_fmt = format_currency_amount(new_amt, currency)
            phrases.append(f"reduce the {desc_clean} to {amt_fmt}")

    if not phrases:
        return ""
    
    combined = " and ".join(phrases)
    return combined[0].upper() + combined[1:]

def generate_decision_explanation(
    request: Request,
    profile: FinancialProfile,
    amount_safe_to_pay: float,
    affordability_status: str,
    recommended_payment_method: str,
    payment_plan: str,
    earliest_date_for_full_payment: str,
    spending_changes_needed: str,
    events_by_id: Dict[str, FinancialEvent],
    chosen_option: Optional[PaymentOption] = None,
) -> str:
    """Generates grounded decision explanation supporting the recommendation."""
    curr = profile.home_currency
    req_amt_fmt = format_currency_amount(request.requested_amount, curr)
    min_bal_fmt = format_currency_amount(profile.minimum_balance_to_keep, curr)
    safe_amt_fmt = format_currency_amount(amount_safe_to_pay, curr)

    # 1. Affordable Now
    if affordability_status == STATUS_AFFORDABLE_NOW:
        return f"Pay {req_amt_fmt} today. This leaves at least {min_bal_fmt} available over the next 90 days."

    # 2. Affordable With Plan - Installments
    if affordability_status == STATUS_AFFORDABLE_WITH_PLAN and recommended_payment_method == METHOD_INSTALLMENTS:
        if chosen_option:
            n_inst = chosen_option.number_of_payments
            inst_amt_fmt = format_currency_amount(chosen_option.payment_amount, curr)
            start_date_fmt = format_date_human(chosen_option.first_payment_date)
            return f"Use {n_inst} installments of {inst_amt_fmt}, starting {start_date_fmt}. This leaves at least {min_bal_fmt} available."
        elif payment_plan != "none":
            plan_items = payment_plan.split("|")
            n_inst = len(plan_items)
            first_d_str, first_amt_str = plan_items[0].split(":")
            first_d = date.fromisoformat(first_d_str)
            inst_amt_fmt = format_currency_amount(float(first_amt_str), curr)
            start_date_fmt = format_date_human(first_d)
            return f"Use {n_inst} installments of {inst_amt_fmt}, starting {start_date_fmt}. This leaves at least {min_bal_fmt} available."

    # 3. Affordable With Plan - Partial Payment
    if affordability_status == STATUS_AFFORDABLE_WITH_PLAN and recommended_payment_method == METHOD_PARTIAL_PAYMENT:
        plan_items = payment_plan.split("|")
        p2_d_str, p2_amt_str = plan_items[1].split(":")
        p2_d = date.fromisoformat(p2_d_str)
        p2_d_fmt = format_date_human(p2_d)
        p2_amt_fmt = format_currency_amount(float(p2_amt_str), curr)
        return (
            f"Pay {safe_amt_fmt} today and the remaining {p2_amt_fmt} on {p2_d_fmt}. "
            f"This completes the full request and keeps the {min_bal_fmt} minimum protected."
        )

    # 4. Affordable With Plan - Full Payment with Spending Changes
    if affordability_status == STATUS_AFFORDABLE_WITH_PLAN and recommended_payment_method == METHOD_FULL_PAYMENT:
        spending_phrase = generate_spending_description(spending_changes_needed, events_by_id, curr)
        if spending_phrase:
            return f"{spending_phrase}, then pay {req_amt_fmt} today. This leaves at least {min_bal_fmt} available."
        else:
            return f"Pay {req_amt_fmt} today. This leaves at least {min_bal_fmt} available."

    # 5. Affordable Later - Wait
    if affordability_status == STATUS_AFFORDABLE_LATER and recommended_payment_method == METHOD_WAIT:
        if earliest_date_for_full_payment:
            pay_d = date.fromisoformat(earliest_date_for_full_payment)
            pay_d_fmt = format_date_human(pay_d)
            return f"Pay {req_amt_fmt} in full on {pay_d_fmt}. Paying earlier would take the balance below the {min_bal_fmt} minimum."
        else:
            des_d_fmt = format_date_human(request.desired_completion_date)
            return f"Pay {req_amt_fmt} in full on {des_d_fmt}. Paying earlier would take the balance below the {min_bal_fmt} minimum."

    # 6. Not Affordable - Not Recommended
    if affordability_status == STATUS_NOT_AFFORDABLE:
        des_d_fmt = format_date_human(request.desired_completion_date)
        if not earliest_date_for_full_payment:
            return (
                f"Do not proceed with the {req_amt_fmt} request. Although {safe_amt_fmt} is available today, "
                f"the full amount cannot be completed safely within 90 days."
            )
        else:
            return f"Do not make this payment by {des_d_fmt}. None of the available options keeps the {min_bal_fmt} minimum protected."

    return f"Recommendation: {recommended_payment_method} for {req_amt_fmt}."
