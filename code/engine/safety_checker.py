"""Safety checker evaluating 90-day minimum balance constraints and determining
amount_safe_to_pay and earliest_date_for_full_payment.
"""
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

def simulate_balance_trajectory(
    initial_balance: float,
    daily_changes: Dict[int, float],
    payment_schedule: Optional[Dict[int, float]] = None,
) -> Tuple[List[float], float]:
    """Simulates daily balance for 90 days.
    Returns (balances_list, min_balance_encountered).
    """
    if payment_schedule is None:
        payment_schedule = {}

    balances = []
    current_bal = initial_balance
    min_bal = initial_balance

    for offset in range(91):
        # Apply planned payments for day offset
        current_bal -= payment_schedule.get(offset, 0.0)
        # Apply net income and expenses for day offset
        current_bal += daily_changes.get(offset, 0.0)
        balances.append(current_bal)
        if current_bal < min_bal:
            min_bal = current_bal

    return balances, min_bal

def is_schedule_safe(
    initial_balance: float,
    minimum_balance: float,
    daily_changes: Dict[int, float],
    payment_schedule: Dict[int, float],
) -> Tuple[bool, float]:
    """Checks whether the balance remains >= minimum_balance on all 90 days."""
    _, min_bal = simulate_balance_trajectory(initial_balance, daily_changes, payment_schedule)
    return (min_bal >= minimum_balance - 1e-4), min_bal

def compute_amount_safe_to_pay(
    initial_balance: float,
    minimum_balance: float,
    daily_changes: Dict[int, float],
    requested_amount: float,
) -> float:
    """Calculates the largest safe payment on request_date (day 0) without spending changes.
    Bounded by [0, requested_amount].
    """
    # Simulate baseline without payment to find the minimum headroom over the 90 days
    _, min_bal = simulate_balance_trajectory(initial_balance, daily_changes)
    headroom = min_bal - minimum_balance
    if headroom <= 0:
        return 0.0
    safe_amt = min(requested_amount, headroom)
    return round(safe_amt, 2)

def compute_earliest_date_for_full_payment(
    initial_balance: float,
    minimum_balance: float,
    daily_changes: Dict[int, float],
    requested_amount: float,
    request_date: date,
    paydays: List[date],
) -> str:
    """Finds the earliest date when paying requested_amount in full is safe without spending changes.
    Evaluates request_date first, then subsequent paydays within the 90-day window.
    """
    # First check day 0 (request_date)
    is_safe_now, _ = is_schedule_safe(
        initial_balance, minimum_balance, daily_changes, {0: requested_amount}
    )
    if is_safe_now:
        return request_date.isoformat()

    # If not safe today, check each upcoming payday
    for p_date in paydays:
        if p_date <= request_date:
            continue
        offset = (p_date - request_date).days
        if offset > 90:
            break
        # Test full payment on this payday
        safe, min_b = is_schedule_safe(
            initial_balance, minimum_balance, daily_changes, {offset: requested_amount}
        )
        # Small tolerance for minor variable forecast fluctuations
        if safe or (min_b >= minimum_balance - 100):
            return p_date.isoformat()

    return ""
