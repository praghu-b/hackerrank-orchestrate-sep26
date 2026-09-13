"""Message analyzer for extracting financial amendments and updates from messages.csv.
Applies conflict-resolution precedence:
1. Explicit cancellations / amendments
2. Newer records
3. Settled events
4. Financially safer interpretation
"""
import re
from datetime import date, datetime
from typing import Dict, List, Optional, Any
from code.models.schemas import Message

class MessageInsights:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.salary_amount: Optional[float] = None
        self.salary_effective_date: Optional[date] = None
        self.contract_ended: bool = False
        self.one_time_arrears: Optional[float] = None
        self.rent_multiplier: float = 1.0
        self.confirmed_invoice_amount: Optional[float] = None
        self.confirmed_invoice_date: Optional[date] = None
        self.notes: List[str] = []

def parse_iso_date(d_str: str) -> Optional[date]:
    try:
        return datetime.strptime(d_str, "%Y-%m-%d").date()
    except Exception:
        return None

def extract_amount_from_text(text: str) -> Optional[float]:
    # Match currencies: INR, ZAR, IDR, USD, EUR followed by number
    match = re.search(r'\b(?:INR|ZAR|IDR|USD|EUR)\s+([0-9]+(?:\.[0-9]+)?)\b', text, re.IGNORECASE)
    if match:
        return float(match.group(1).replace(",", ""))
    return None

def extract_all_amounts_from_text(text: str) -> List[float]:
    matches = re.findall(r'\b(?:INR|ZAR|IDR|USD|EUR)\s+([0-9]+(?:\.[0-9]+)?)\b', text, re.IGNORECASE)
    return [float(m.replace(",", "")) for m in matches]

def analyze_user_messages(messages: List[Message], user_id: str) -> MessageInsights:
    insights = MessageInsights(user_id)
    # Sort messages by sent_at ascending so newer messages override older ones
    user_msgs = sorted(
        [m for m in messages if m.user_id == user_id],
        key=lambda m: m.sent_at if m.sent_at else ""
    )
    
    for msg in user_msgs:
        txt = msg.message_text
        txt_lower = txt.lower()
        
        # 1. Seasonal contract ended / no renewal confirmed
        if "contract has ended" in txt_lower or "kontrak telah berakhir" in txt_lower:
            insights.contract_ended = True
            insights.notes.append("Employment contract ended; no recurring salary.")
            continue
            
        # 2. Rent increase / lease renewal
        rent_match = re.search(r'rent by (\d+)%|sewa sebesar (\d+)%', txt, re.IGNORECASE)
        if rent_match:
            pct = float(rent_match.group(1) or rent_match.group(2))
            insights.rent_multiplier = 1.0 + (pct / 100.0)
            insights.notes.append(f"Rent increased by {pct}%")

        # 3. Confirmed invoice / client payout from service provider
        if msg.source_type == "service_provider" and ("client approved an invoice" in txt_lower or "klien menyetujui" in txt_lower):
            amt = extract_amount_from_text(txt)
            date_match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', txt)
            if amt and date_match:
                inv_date = parse_iso_date(date_match.group(1))
                insights.confirmed_invoice_amount = amt
                insights.confirmed_invoice_date = inv_date
                insights.notes.append(f"Confirmed client invoice {amt} on {inv_date}")
            continue

        # 4. Employer salary amendments
        if msg.source_type == "employer":
            # Date update: "confirmed salary is now expected on 2024-09-23"
            date_match = re.search(r'expected on (\d{4}-\d{2}-\d{2})|dijadwalkan pada (\d{4}-\d{2}-\d{2})|tanggal (\d{4}-\d{2}-\d{2})|resumes on (\d{4}-\d{2}-\d{2})|confirmed for (\d{4}-\d{2}-\d{2})', txt, re.IGNORECASE)
            if date_match:
                for g in date_match.groups():
                    if g:
                        insights.salary_effective_date = parse_iso_date(g)
                        break

            # One-time arrears adjustment
            if "arrears" in txt_lower or "tunggakan" in txt_lower or "one-time" in txt_lower:
                all_amts = extract_all_amounts_from_text(txt)
                if len(all_amts) >= 2:
                    insights.salary_amount = all_amts[0]
                    insights.one_time_arrears = all_amts[1]
                    insights.notes.append(f"Regular salary {all_amts[0]} with one-time arrears {all_amts[1]}")
                elif len(all_amts) == 1:
                    insights.one_time_arrears = all_amts[0]
                continue

            # Regular / updated salary
            amt = extract_amount_from_text(txt)
            if amt is not None:
                insights.salary_amount = amt
                insights.notes.append(f"Updated salary to {amt}")

    return insights
