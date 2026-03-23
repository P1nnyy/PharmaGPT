# HSN (Harmonized System of Nomenclature) Codes - Pharma Products
COMMON_HSN_MAP = {
    "96032100": {"desc": "Toothbrush", "tax": 18.0},
    "9603": {"desc": "Brushes/Brooms", "tax": 18.0},
    "30049011": {"desc": "Medicaments (Allopathic)", "tax": 12.0},
    "3004": {"desc": "Medicaments", "tax": 12.0},
    "2106": {"desc": "Food Supplement", "tax": 18.0}
}

# Critical extraction rules for OCR
EXTRACTION_RULES = [
    "CRITICAL: Do NOT extract 8-digit HSN codes (e.g. 30043110) as Expiry Date.",
    "CRITICAL: Do NOT extract 4-digit HSN codes (e.g. 3004) as Expiry Date.",
    "CRITICAL: Quantity is usually small (< 50). Do not confuse Rate/MRP (e.g. 100, 200) with Qty."
]

# Auditor node configuration
AUDITOR_CONFIG = {
    'NOISE_THRESHOLD': 5,
    'DEDUP_THRESHOLD': 1.0,
    'ZERO_VALUE_TOLERANCE': 0.01,
    'MAX_QUANTITY': 50,
    'MAX_PRICE': 5000
}

# Blacklisted keywords for deduplication
BLACKLIST_KEYWORDS = [
    "total", "subtotal", "grand total", "amount", "output", "input",
    "gst", "freight", "discount", "round off", "net amount",
    "taxable value", "output cgst", "output sgst"
]

# Common unit measurements
COMMON_UNITS = ['pieces', 'ml', 'L', 'strip', 'box', 'tube', 'vial', 'ampoule', 'g', 'mg', 'kg']

# Scheme/Offer detection patterns
SCHEME_PATTERNS = ["buy", "get", "free", "offer", "initiative", "gift"]
