"""Projects conservative daily cashflows over a 90-day evaluation horizon.
"""
from datetime import date, timedelta
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
import calendar

from code.models.schemas import FinancialProfile, FinancialEvent
from code.data.message_analyzer import MessageInsights
from code.engine.state_reconstructor import ReconstructedState, reconstruct_user_state

MONTHLY_CATEGORIES = {
    "rent", "utilities", "education", "debt_repayment",
    "music_subscription", "delivery_membership", "housing",
    "insurance", "healthcare", "entertainment", "cloud_storage",
    "streaming", "shopping", "gym", "family_support"
}

def add_months(d: date, months: int) -> date:
    year = d.year + (d.month + months - 1) // 12
    month = (d.month + months - 1) % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)

def project_daily_cashflow(
    profile: FinancialProfile,
    events: List[FinancialEvent],
    insights: MessageInsights,
    request_date: date,
    stopped_event_ids: Optional[Set[str]] = None,
    reduced_events: Optional[Dict[str, float]] = None,
) -> Tuple[Dict[int, float], ReconstructedState]:
    """Generates daily net cash change (credits - debits) for day 0 to day 90."""
    if stopped_event_ids is None:
        stopped_event_ids = set()
    if reduced_events is None:
        reduced_events = {}
    if insights is None:
        insights = MessageInsights(profile.user_id)

    state = reconstruct_user_state(profile, events, insights, request_date)
    daily_changes: Dict[int, float] = defaultdict(float)

    # 1. Salary projections
    if state.has_ongoing_salary and state.salary_amount > 0:
        cur_d = request_date
        year, month = cur_d.year, cur_d.month
        day = min(state.salary_day, calendar.monthrange(year, month)[1])
        first_pay_date = date(year, month, day)
        if first_pay_date < request_date:
            first_pay_date = add_months(first_pay_date, 1)

        # Salary date override from message
        if state.salary_override_date and state.salary_override_date >= request_date:
            first_pay_date = state.salary_override_date

        pay_d = first_pay_date
        is_first = True
        while pay_d <= request_date + timedelta(days=90):
            sal_amt = state.salary_amount
            if is_first and state.one_time_arrears:
                sal_amt += state.one_time_arrears
            offset = (pay_d - request_date).days
            if 0 <= offset <= 90:
                daily_changes[offset] += sal_amt
            pay_d = add_months(pay_d, 1)
            is_first = False

    # Confirmed client invoice / payout from messages
    if insights.confirmed_invoice_amount and insights.confirmed_invoice_date:
        if request_date <= insights.confirmed_invoice_date <= request_date + timedelta(days=90):
            offset = (insights.confirmed_invoice_date - request_date).days
            daily_changes[offset] += insights.confirmed_invoice_amount

    # 2. Pending debits (must be reserved immediately or on settlement date)
    for pe in state.pending_debits:
        d = pe.settlement_date or pe.event_date
        offset = max(0, (d - request_date).days)
        if offset <= 90:
            daily_changes[offset] -= pe.converted_amount

    # 3. Monthly recurring streams
    streams = defaultdict(list)
    for e in state.recurring_debits:
        if e.category in MONTHLY_CATEGORIES:
            streams[(e.category, e.description)].append(e)

    for (cat, desc), elist in streams.items():
        if len(elist) >= 2:
            slist = sorted(elist, key=lambda x: x.event_date)
            last_ev = slist[-1]

            # If this stream is stopped
            if last_ev.event_id in stopped_event_ids:
                continue

            amt = last_ev.converted_amount
            if last_ev.event_id in reduced_events:
                amt = reduced_events[last_ev.event_id]
            elif cat == "rent" and state.rent_multiplier != 1.0:
                amt = amt * state.rent_multiplier

            pay_day = last_ev.event_date.day
            cur_d = request_date
            year, month = cur_d.year, cur_d.month
            max_day = calendar.monthrange(year, month)[1]
            first_d = date(year, month, min(pay_day, max_day))
            if first_d < request_date:
                first_d = add_months(first_d, 1)

            proj_d = first_d
            while proj_d <= request_date + timedelta(days=90):
                offset = (proj_d - request_date).days
                if 0 <= offset <= 90:
                    daily_changes[offset] -= amt
                proj_d = add_months(proj_d, 1)

    # 4. Essential variable streams: groceries, transport
    for vcat, def_interval in [("groceries", 7), ("transport", 7)]:

        vevs = [e for e in state.recurring_debits if e.category == vcat]
        if vevs:
            vevs_sorted = sorted(vevs, key=lambda x: x.event_date)
            if len(vevs_sorted) >= 3:
                diffs = [(vevs_sorted[i+1].event_date - vevs_sorted[i].event_date).days for i in range(len(vevs_sorted)-1)]
                intv = round(sum(diffs) / len(diffs))
                if intv < 5:
                    intv = def_interval
            else:
                intv = def_interval

            # Check if any event in this variable category is stopped or reduced
            if any(e.event_id in stopped_event_ids for e in vevs):
                continue

            latest_ev = vevs_sorted[-1]
            if latest_ev.event_id in reduced_events:
                avg_amt = reduced_events[latest_ev.event_id]
            else:
                recent_amts = [
                    (reduced_events[e.event_id] if e.event_id in reduced_events else e.converted_amount)
                    for e in vevs_sorted[-4:]
                ]
                avg_amt = sum(recent_amts) / len(recent_amts)


            last_d = vevs_sorted[-1].event_date
            proj_d = last_d + timedelta(days=intv)
            while proj_d < request_date:
                proj_d += timedelta(days=intv)

            while proj_d <= request_date + timedelta(days=90):
                offset = (proj_d - request_date).days
                if 0 <= offset <= 90:
                    daily_changes[offset] -= avg_amt
                proj_d += timedelta(days=intv)

    return daily_changes, state
