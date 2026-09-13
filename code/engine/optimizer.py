"""Payment plan optimizer evaluating full payment, installments, partial payment,
wait, and spending changes according to challenge constraints and preference ranking.
"""
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple, Set
import calendar

from code.models.schemas import (
    FinancialProfile,
    FinancialEvent,
    PaymentOption,
    Request,
    CandidatePlan,
)
from code.data.message_analyzer import MessageInsights
from code.engine.cashflow_forecaster import project_daily_cashflow, add_months
from code.engine.safety_checker import (
    is_schedule_safe,
    compute_amount_safe_to_pay,
    compute_earliest_date_for_full_payment,
)
from code.engine.spending_adjuster import (
    find_candidate_spending_adjustments,
    get_spending_combinations,
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

def format_payment_schedule(schedule: List[Tuple[date, float]]) -> str:
    parts = []
    for d, amt in schedule:
        amt_str = f"{amt:.2f}".rstrip("0").rstrip(".") if (amt % 1 != 0) else f"{int(amt)}"
        parts.append(f"{d.isoformat()}:{amt_str}")
    return "|".join(parts)

def evaluate_request(
    request: Request,
    profile: FinancialProfile,
    events: List[FinancialEvent],
    payment_options: List[PaymentOption],
    insights: MessageInsights,
) -> Tuple[float, str, str, str, str, str, Optional[PaymentOption]]:
    """Evaluates a financial request and returns:
    (amount_safe_to_pay, affordability_status, recommended_payment_method,
     payment_plan, earliest_date_for_full_payment, spending_changes_needed, chosen_option)
    """
    req_date = request.request_date
    req_amt = request.requested_amount
    desired_date = request.desired_completion_date

    # 1. Base cashflow without spending changes
    base_daily_changes, state = project_daily_cashflow(profile, events, insights, req_date)
    init_bal = state.initial_balance
    min_bal = state.minimum_balance

    # 2. Extract upcoming paydays within 90 days
    paydays: List[date] = []
    if state.has_ongoing_salary and state.salary_amount > 0:
        cur_d = req_date
        year, month = cur_d.year, cur_d.month
        day = min(state.salary_day, calendar.monthrange(year, month)[1])
        first_p = date(year, month, day)
        if first_p < req_date:
            first_p = add_months(first_p, 1)
        if state.salary_override_date and state.salary_override_date >= req_date:
            first_p = state.salary_override_date

        p_cursor = first_p
        while p_cursor <= req_date + timedelta(days=90):
            paydays.append(p_cursor)
            p_cursor = add_months(p_cursor, 1)

    # 3. Amount safe to pay today
    amount_safe_to_pay = compute_amount_safe_to_pay(init_bal, min_bal, base_daily_changes, req_amt)

    # 4. Earliest date for single full payment without spending changes
    earliest_date_str = compute_earliest_date_for_full_payment(
        init_bal, min_bal, base_daily_changes, req_amt, req_date, paydays
    )
    earliest_date = date.fromisoformat(earliest_date_str) if earliest_date_str else None

    # 5. Generate Candidate Plans
    candidates: List[CandidatePlan] = []
    methods_considered = set(profile.payment_methods_user_will_consider)

    # Spending adjustment candidates
    spending_candidates = find_candidate_spending_adjustments(profile, state.flexible_events)
    spending_combos = get_spending_combinations(spending_candidates, max_actions=3)

    # --- Method A: full_payment today ---
    if METHOD_FULL_PAYMENT in methods_considered:
        # Check without spending changes
        safe_base = (amount_safe_to_pay >= req_amt)
        if safe_base:
            candidates.append(CandidatePlan(
                method=METHOD_FULL_PAYMENT,
                payment_plan_str=f"{req_date.isoformat()}:{req_amt:.2f}".rstrip("0").rstrip(".") if req_amt % 1 != 0 else f"{req_date.isoformat()}:{int(req_amt)}",
                schedule=[(req_date, req_amt)],
                spending_changes="none",
                total_cost=req_amt,
                earliest_payment_date=req_date,
                completion_date=req_date,
                payment_count=1,
                payment_option_id=None,
                is_safe=True,
                min_projected_balance=init_bal - req_amt,
            ))
        else:
            # Check with spending changes
            deficit = req_amt - amount_safe_to_pay
            valid_combos = [
                c for c in spending_combos
                if sum(x.saved_amount for x in c) >= deficit - 1e-4
            ]
            valid_combos.sort(key=lambda c: (sum(x.saved_amount for x in c) - deficit, len(c)))

            for combo in valid_combos:
                stopped_ids = {c.event_id for c in combo if c.action_type == "stop"}
                reduced_evs = {c.event_id: c.new_amount for c in combo if c.action_type == "reduce_to"}
                combo_daily_changes, _ = project_daily_cashflow(
                    profile, events, insights, req_date, stopped_ids, reduced_evs
                )
                safe_combo, min_p = is_schedule_safe(init_bal, min_bal, combo_daily_changes, {0: req_amt})
                if safe_combo or (init_bal - req_amt + sum(c.saved_amount for c in combo) >= min_bal):
                    changes_str = "|".join(sorted([c.key for c in combo], key=lambda k: (0 if k.startswith("stop") else 1, k)))
                    candidates.append(CandidatePlan(

                        method=METHOD_FULL_PAYMENT,
                        payment_plan_str=f"{req_date.isoformat()}:{req_amt:.2f}".rstrip("0").rstrip(".") if req_amt % 1 != 0 else f"{req_date.isoformat()}:{int(req_amt)}",
                        schedule=[(req_date, req_amt)],
                        spending_changes=changes_str,
                        total_cost=req_amt,
                        earliest_payment_date=req_date,
                        completion_date=req_date,
                        payment_count=1,
                        payment_option_id=None,
                        is_safe=True,
                        min_projected_balance=min_p,
                    ))
                    break


    # --- Method B: installments ---
    if METHOD_INSTALLMENTS in methods_considered:
        for opt in payment_options:
            if opt.payment_method != METHOD_INSTALLMENTS:
                continue

            # Check max_installment_months
            if profile.max_installment_months is not None:
                total_plan_days = (opt.number_of_payments - 1) * (opt.payment_frequency_days or 30)
                if (opt.number_of_payments > profile.max_installment_months + 1) or (total_plan_days > profile.max_installment_months * 31):
                    continue

            freq = opt.payment_frequency_days or 30
            opt_schedule: List[Tuple[date, float]] = []
            opt_offsets: Dict[int, float] = {}
            for i in range(opt.number_of_payments):
                p_date = opt.first_payment_date + timedelta(days=i * freq)
                opt_schedule.append((p_date, opt.payment_amount))
                offset = (p_date - req_date).days
                if offset <= 90:
                    opt_offsets[offset] = opt_offsets.get(offset, 0.0) + opt.payment_amount

            comp_date = opt_schedule[-1][0]
            plan_str = format_payment_schedule(opt_schedule)

            # Check safety without spending changes
            safe_base, min_p = is_schedule_safe(init_bal, min_bal, base_daily_changes, opt_offsets)
            # An installment plan is safe if daily balance stays above minimum or first installment is <= amount_safe_to_pay
            first_safe = (opt.first_payment_date == req_date and opt.payment_amount <= amount_safe_to_pay) or (opt.first_payment_date > req_date)
            if safe_base and first_safe:
                candidates.append(CandidatePlan(
                    method=METHOD_INSTALLMENTS,
                    payment_plan_str=plan_str,
                    schedule=opt_schedule,
                    spending_changes="none",
                    total_cost=opt.total_payable_amount,
                    earliest_payment_date=opt_schedule[0][0],
                    completion_date=comp_date,
                    payment_count=opt.number_of_payments,
                    payment_option_id=opt.payment_option_id,
                    is_safe=True,
                    min_projected_balance=min_p,
                ))

    # --- Method C: partial_payment ---
    if request.allows_partial_payment and (METHOD_PARTIAL_PAYMENT in methods_considered):
        if (0 < amount_safe_to_pay < req_amt) and earliest_date and (earliest_date <= desired_date):
            p1_amt = amount_safe_to_pay
            p2_amt = round(req_amt - p1_amt, 2)
            part_schedule = [(req_date, p1_amt), (earliest_date, p2_amt)]
            p1_offset = 0
            p2_offset = (earliest_date - req_date).days
            part_offsets = {p1_offset: p1_amt, p2_offset: p2_amt}
            
            safe_part, min_p = is_schedule_safe(init_bal, min_bal, base_daily_changes, part_offsets)
            if safe_part:
                candidates.append(CandidatePlan(
                    method=METHOD_PARTIAL_PAYMENT,
                    payment_plan_str=format_payment_schedule(part_schedule),
                    schedule=part_schedule,
                    spending_changes="none",
                    total_cost=req_amt,
                    earliest_payment_date=req_date,
                    completion_date=earliest_date,
                    payment_count=2,
                    payment_option_id=None,
                    is_safe=True,
                    min_projected_balance=min_p,
                ))

    # --- Method D: wait ---
    if (METHOD_FULL_PAYMENT in methods_considered) and earliest_date and (earliest_date > req_date):
        wait_schedule = [(earliest_date, req_amt)]
        candidates.append(CandidatePlan(
            method=METHOD_WAIT,
            payment_plan_str=f"{earliest_date.isoformat()}:{req_amt:.2f}".rstrip("0").rstrip(".") if req_amt % 1 != 0 else f"{earliest_date.isoformat()}:{int(req_amt)}",
            schedule=wait_schedule,
            spending_changes="none",
            total_cost=req_amt,
            earliest_payment_date=earliest_date,
            completion_date=earliest_date,
            payment_count=1,
            payment_option_id=None,
            is_safe=True,
            min_projected_balance=min_bal,
        ))

    # 6. Filter and Rank Candidate Plans
    safe_candidates = [c for c in candidates if c.is_safe]

    # Filter plans that complete by desired completion date
    feasible_on_time = [c for c in safe_candidates if c.completion_date <= desired_date]

    chosen_candidates = feasible_on_time if feasible_on_time else safe_candidates

    if not chosen_candidates:
        return (
            amount_safe_to_pay,
            STATUS_NOT_AFFORDABLE,
            METHOD_NOT_RECOMMENDED,
            "none",
            earliest_date_str,
            "none",
            None,
        )

    # Ranking:
    # 1. Completes by deadline (True first)
    # 2. No spending changes (True first)
    # 3. Minimize total amount paid
    # 4. Start earlier
    # 5. Fewer payments
    # 6. Lowest payment_option_id
    def plan_sort_key(p: CandidatePlan):
        completes_on_time = (p.completion_date <= desired_date)
        no_changes = (p.spending_changes == "none")
        opt_id = p.payment_option_id or "zzzzzz"
        return (
            0 if completes_on_time else 1,
            0 if no_changes else 1,
            round(p.total_cost, 2),
            p.earliest_payment_date,
            p.payment_count,
            opt_id,
        )

    chosen_candidates.sort(key=plan_sort_key)
    best_plan = chosen_candidates[0]

    # If the best plan cannot complete by deadline and is wait, check feasibility
    if best_plan.completion_date > desired_date and best_plan.method != METHOD_WAIT:
        return (
            amount_safe_to_pay,
            STATUS_NOT_AFFORDABLE,
            METHOD_NOT_RECOMMENDED,
            "none",
            earliest_date_str,
            "none",
            None,
        )

    # Status assignment
    if best_plan.method == METHOD_FULL_PAYMENT and best_plan.earliest_payment_date == req_date and best_plan.spending_changes == "none":
        status = STATUS_AFFORDABLE_NOW
    elif best_plan.method in {METHOD_INSTALLMENTS, METHOD_PARTIAL_PAYMENT} or (best_plan.spending_changes != "none"):
        status = STATUS_AFFORDABLE_WITH_PLAN
    elif best_plan.method == METHOD_WAIT:
        if best_plan.completion_date <= desired_date:
            status = STATUS_AFFORDABLE_LATER
        else:
            return (
                amount_safe_to_pay,
                STATUS_NOT_AFFORDABLE,
                METHOD_NOT_RECOMMENDED,
                "none",
                earliest_date_str,
                "none",
                None,
            )
    else:
        status = STATUS_NOT_AFFORDABLE

    chosen_opt = None
    if best_plan.payment_option_id:
        for opt in payment_options:
            if opt.payment_option_id == best_plan.payment_option_id:
                chosen_opt = opt
                break

    return (
        amount_safe_to_pay,
        status,
        best_plan.method,
        best_plan.payment_plan_str,
        earliest_date_str,
        best_plan.spending_changes,
        chosen_opt,
    )
