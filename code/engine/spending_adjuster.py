"""Solves for minimal permitted flexible spending adjustments (stop / reduce_to)
when an otherwise preferred payment plan requires assistance.
"""
from typing import Dict, List, Optional, Set, Tuple
from code.models.schemas import FinancialProfile, FinancialEvent

class SpendingOption:
    def __init__(self, action_type: str, event_id: str, new_amount: Optional[float], saved_amount: float, desc: str):
        self.action_type = action_type  # 'stop' or 'reduce_to'
        self.event_id = event_id
        self.new_amount = new_amount
        self.saved_amount = saved_amount
        self.desc = desc

    @property
    def key(self) -> str:
        if self.action_type == "stop":
            return f"stop:{self.event_id}"
        else:
            # Format float cleanly (integer if no decimal, else 2 decimal places)
            val_str = f"{self.new_amount:.2f}".rstrip("0").rstrip(".") if self.new_amount is not None else ""
            return f"reduce_to:{self.event_id}:{val_str}"

def find_candidate_spending_adjustments(
    profile: FinancialProfile,
    flexible_events: List[FinancialEvent],
) -> List[SpendingOption]:
    """Finds all valid individual spending reduction/stop options."""
    protect = set(profile.expense_categories_to_protect)
    stop_cats = set(profile.expense_categories_user_is_willing_to_stop) - protect
    reduce_cats = set(profile.expense_categories_user_is_willing_to_reduce) - protect

    candidates: List[SpendingOption] = []
    seen_events: Set[str] = set()

    for e in flexible_events:
        if e.event_id in seen_events:
            continue
        seen_events.add(e.event_id)

        # Candidate for stop
        if e.category in stop_cats and e.flexibility in {"stoppable", "reducible_or_stoppable"}:
            candidates.append(SpendingOption(
                action_type="stop",
                event_id=e.event_id,
                new_amount=None,
                saved_amount=e.converted_amount,
                desc=e.description,
            ))

        # Candidate for reduce
        if e.category in reduce_cats and e.flexibility in {"reducible", "reducible_or_stoppable"}:
            # Default reduction: 50%
            new_amt = round(e.converted_amount * 0.5, 2)
            if e.minimum_allowed_amount is not None and new_amt < e.minimum_allowed_amount:
                new_amt = e.minimum_allowed_amount
            saved = e.converted_amount - new_amt
            if saved > 0:
                candidates.append(SpendingOption(
                    action_type="reduce_to",
                    event_id=e.event_id,
                    new_amount=new_amt,
                    saved_amount=saved,
                    desc=e.description,
                ))

    # Sort descending by saved amount
    candidates.sort(key=lambda x: x.saved_amount, reverse=True)
    return candidates

def get_spending_combinations(candidates: List[SpendingOption], max_actions: int = 3) -> List[List[SpendingOption]]:
    """Generates combinations of 1, 2, or 3 spending adjustments where stop and reduce
    on the same event are mutually exclusive.
    """
    valid_combos: List[List[SpendingOption]] = []
    
    # 1 action
    for c1 in candidates:
        valid_combos.append([c1])

    # 2 actions
    if max_actions >= 2:
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                c1, c2 = candidates[i], candidates[j]
                if c1.event_id != c2.event_id:
                    valid_combos.append([c1, c2])

    # 3 actions
    if max_actions >= 3:
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                for k in range(j + 1, len(candidates)):
                    c1, c2, c3 = candidates[i], candidates[j], candidates[k]
                    if len({c1.event_id, c2.event_id, c3.event_id}) == 3:
                        valid_combos.append([c1, c2, c3])

    return valid_combos
