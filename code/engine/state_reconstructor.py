"""Reconstructs the active financial baseline for a user, filtering non-cash items,
reserving pending debits, and reconciling message-based salary/rent amendments.
"""
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from code.models.schemas import FinancialProfile, FinancialEvent
from code.data.message_analyzer import MessageInsights

class ReconstructedState:
    def __init__(
        self,
        user_id: str,
        initial_balance: float,
        minimum_balance: float,
        salary_amount: float,
        salary_day: int,
        salary_override_date: Optional[date],
        has_ongoing_salary: bool,
        one_time_arrears: Optional[float],
        rent_multiplier: float,
        pending_debits: List[FinancialEvent],
        recurring_debits: List[FinancialEvent],
        flexible_events: List[FinancialEvent],
    ):
        self.user_id = user_id
        self.initial_balance = initial_balance
        self.minimum_balance = minimum_balance
        self.salary_amount = salary_amount
        self.salary_day = salary_day
        self.salary_override_date = salary_override_date
        self.has_ongoing_salary = has_ongoing_salary
        self.one_time_arrears = one_time_arrears
        self.rent_multiplier = rent_multiplier
        self.pending_debits = pending_debits
        self.recurring_debits = recurring_debits
        self.flexible_events = flexible_events

def reconstruct_user_state(
    profile: FinancialProfile,
    events: List[FinancialEvent],
    insights: Optional[MessageInsights],
    request_date: date,
) -> ReconstructedState:
    """Reconstructs the active financial state of a user."""
    if insights is None:
        insights = MessageInsights(profile.user_id)

    initial_balance = profile.current_available_balance

    minimum_balance = profile.minimum_balance_to_keep

    # Pending debits (must be reserved)
    pending_debits = [
        e for e in events
        if e.direction == "debit" and e.status == "pending"
    ]

    # Check for final payroll description or message ending contract
    has_final_payroll_desc = any(
        ("final" in e.description.lower() or "last" in e.description.lower())
        for e in events if e.category == "salary" and e.direction == "credit" and e.status == "settled"
    )
    has_ongoing_salary = (not insights.contract_ended) and (not has_final_payroll_desc)

    # Check for scheduled or settled salary (excluding commissions, bonuses, arrears)
    def is_recurring_salary(e: FinancialEvent) -> bool:
        desc = e.description.lower()
        return not any(w in desc for w in ["commission", "bonus", "arrears", "final"])

    scheduled_salary = [
        e for e in events
        if e.category == "salary" and e.direction == "credit" and e.status == "scheduled" and is_recurring_salary(e)
    ]
    settled_salary = [
        e for e in events
        if e.category == "salary" and e.direction == "credit" and e.status == "settled" and is_recurring_salary(e)
    ]


    if scheduled_salary:
        sched = scheduled_salary[0]
        base_salary_amt = sched.converted_amount
        base_salary_day = sched.settlement_date.day
        base_salary_date = sched.settlement_date
    elif settled_salary:
        recent_sal = sorted(settled_salary, key=lambda x: x.settlement_date or x.event_date)[-1]
        base_salary_amt = recent_sal.converted_amount
        base_salary_day = (recent_sal.settlement_date or recent_sal.event_date).day
        base_salary_date = None
    else:
        base_salary_amt = 0.0
        base_salary_day = 15
        base_salary_date = None

    final_salary_amt = insights.salary_amount if insights.salary_amount is not None else base_salary_amt
    final_salary_date = insights.salary_effective_date if insights.salary_effective_date is not None else base_salary_date
    final_salary_day = final_salary_date.day if final_salary_date is not None else base_salary_day

    # Recurring debits and flexible events
    recurring_debits = [
        e for e in events
        if e.direction == "debit" and e.status == "settled"
    ]

    flexible_events = [
        e for e in events
        if e.direction == "debit" and e.flexibility in {"stoppable", "reducible", "reducible_or_stoppable"}
    ]

    return ReconstructedState(
        user_id=profile.user_id,
        initial_balance=initial_balance,
        minimum_balance=minimum_balance,
        salary_amount=final_salary_amt,
        salary_day=final_salary_day,
        salary_override_date=final_salary_date,
        has_ongoing_salary=has_ongoing_salary,
        one_time_arrears=insights.one_time_arrears,
        rent_multiplier=insights.rent_multiplier,
        pending_debits=pending_debits,
        recurring_debits=recurring_debits,
        flexible_events=flexible_events,
    )
