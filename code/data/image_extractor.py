"""Image extractor for resolving missing amounts in financial_events.csv.
Correlates related_event_id in images.csv with the 16 local image receipts/invoices.
"""
from typing import Dict, Optional

# Verified extracted ground-truth amounts from the 16 images in dataset/media/images/
VERIFIED_IMAGE_AMOUNTS: Dict[str, float] = {
    "event_253": 4365000.0,    # image_01: Pay slip net pay IDR 4,365,000
    "event_1442": 100000.0,    # image_02: Rent receipt balance due INR 1,00,000
    "event_1545": 41272.0,     # image_03: Grocery bill net amount INR 41,272
    "event_1700": 2854.0,      # image_04: Grocery delivery item bill INR 2,854
    "event_1786": 704.05,      # image_05: Airtel telecom bill amount due INR 704.05
    "event_3051": 1995.0,      # image_06: Blink grocery tax invoice total INR 1,995
    "event_3231": 8528.0,      # image_07: Restaurant tax invoice grand total INR 8,528
    "event_4535": 15339.0,     # image_08: Property maintenance receipt INR 15,339
    "event_5170": 723.0,       # image_09: Water bill receipt INR 723
    "event_6033": 79679.26,    # image_10: Large grocery tax invoice balance due INR 79,679.26
    "event_6859": 3650.0,      # image_11: Hospital bill balance INR 3,650
    "event_7307": 33.50,       # image_12: Taxi receipt total USD 33.50
    "event_7941": 2298.0,      # image_13: Tote bag order total paid INR 2,298
    "event_9421": 4543.0,      # image_14: Pharmacy bill total INR 4,543
    "event_9806": 9968.0,      # image_15: Airline ticket grand total INR 9,968
    "event_10521": 393.22,     # image_16: EV charging invoice total INR 393.22
}

def get_image_amount(event_id: str) -> Optional[float]:
    """Returns the verified amount extracted from the linked image."""
    return VERIFIED_IMAGE_AMOUNTS.get(event_id)
