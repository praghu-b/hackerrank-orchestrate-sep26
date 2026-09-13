from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Dict, Any

@dataclass
class FinancialProfile:
    user_id: str
    home_currency: str
    current_available_balance: float
    minimum_balance_to_keep: float
    financial_priorities: List[str]
    expense_categories_to_protect: List[str]
    expense_categories_user_is_willing_to_reduce: List[str]
    expense_categories_user_is_willing_to_stop: List[str]
    payment_methods_user_will_consider: List[str]
    max_installment_months: Optional[int] = None

@dataclass
class FinancialEvent:
    event_id: str
    user_id: str
    event_type: str
    description: str
    category: str
    direction: str  # 'debit' or 'credit'
    amount: float
    currency: str
    event_date: date
    settlement_date: Optional[date]
    status: str  # 'settled', 'pending', 'scheduled', 'failed', 'cancelled', 'unrealized'
    linked_event_id: Optional[str] = None
    flexibility: str = "fixed"  # 'fixed', 'reducible', 'stoppable'
    minimum_allowed_amount: Optional[float] = None
    converted_amount: Optional[float] = None  # in user's home currency

@dataclass
class PaymentOption:
    payment_option_id: str
    request_id: str
    payment_method: str  # 'full_payment', 'installments'
    payment_amount: float
    number_of_payments: int
    first_payment_date: date
    payment_frequency_days: Optional[int]
    financing_fee: float
    total_payable_amount: float

@dataclass
class Message:
    message_id: str
    user_id: str
    request_id: Optional[str]
    related_event_id: Optional[str]
    sent_at: str
    source_type: str
    message_text: str

@dataclass
class Request:
    request_id: str
    user_id: str
    request_date: date
    request_type: str
    requested_amount: float
    desired_completion_date: date
    allows_partial_payment: bool
    request_text: str

@dataclass
class CandidatePlan:
    method: str
    payment_plan_str: str
    schedule: List[tuple]  # list of (date, amount)
    spending_changes: str  # 'none' or 'stop:...|reduce_to:...'
    total_cost: float
    earliest_payment_date: date
    completion_date: date
    payment_count: int
    payment_option_id: Optional[str]
    is_safe: bool
    min_projected_balance: float

@dataclass
class DecisionOutput:
    request_id: str
    amount_safe_to_pay: float
    affordability_status: str
    recommended_payment_method: str
    payment_plan: str
    earliest_date_for_full_payment: str
    spending_changes_needed: str
    decision_explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "amount_safe_to_pay": self.amount_safe_to_pay,
            "affordability_status": self.affordability_status,
            "recommended_payment_method": self.recommended_payment_method,
            "payment_plan": self.payment_plan,
            "earliest_date_for_full_payment": self.earliest_date_for_full_payment,
            "spending_changes_needed": self.spending_changes_needed,
            "decision_explanation": self.decision_explanation,
        }
