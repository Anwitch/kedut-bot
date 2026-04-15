"""
rule_parser.py — Deterministic, rule-based transaction parser for Kedut.

This module contains all local parsing logic that does NOT require a Gemini API call.
It is the fast-path for clear, unambiguous transaction inputs like "kopi 20k" or "gajian 5jt".

The main entry point is `parse_local_transaction(text)`, which returns a confidence level
alongside the parsed results so the orchestrator can decide whether to trust it or escalate
to Gemini.
"""

import re
from datetime import date, timedelta


# ---------------------------------------------------------------------------
# Constants & keyword lists
# ---------------------------------------------------------------------------

MAX_AMOUNT = 99_999_999_999

VALID_CATEGORIES = {
    "Makan & Minum", "Transport", "Belanja", "Kesehatan",
    "Hiburan", "Tagihan", "Pendidikan", "Olahraga", "Rumah",
    "Gaji", "Freelance", "Investasi", "Transfer", "Lainnya",
}

# Income keywords — used to detect type before categorising
_INCOME_KEYWORDS = [
    "gaji", "gajian", "slip gaji", "terima", "dapet", "dapat", "masuk",
    "transfer masuk", "diterima", "pendapatan", "pemasukan", "honor",
    "bonus", "freelance", "hasil jual", "upah", "komisi", "dividen",
    "refund", "kembalian transfer", "proyek", "proyekan", "transfer",
]

_CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    (
        "Tagihan",
        ["listrik", "air", "pln", "wifi", "internet", "token", "pulsa", "bpjs", "cicilan", "iuran"],
    ),
    (
        "Makan & Minum",
        [
            "makan", "sarapan", "siang", "malam", "nasi", "kopi", "ayam", "bakso",
            "minum", "resto", "restoran", "warung", "cafe", "kafe", "snack", "jajan",
            "pizza", "burger", "mie", "soto", "pecel", "gado", "bubur",
        ],
    ),
    (
        "Transport",
        [
            "gojek", "grab", "ojek", "bensin", "bbm", "parkir", "tol", "taksi",
            "bus", "kereta", "motor", "mobil", "uber", "angkot", "transjakarta",
            "commuter", "krl", "mrt", "lrt",
        ],
    ),
    (
        "Belanja",
        [
            "beli", "belanja", "market", "indomaret", "alfamart", "supermarket",
            "tokopedia", "shopee", "lazada", "toko", "minimarket", "hypermart",
            "carrefour", "ikea",
        ],
    ),
    (
        "Kesehatan",
        ["obat", "dokter", "rs", "rumah sakit", "apotek", "klinik", "vitamin", "suplemen"],
    ),
    (
        "Pendidikan",
        ["buku", "kursus", "kuliah", "sekolah", "les", "kelas", "workshop", "seminar", "udemy"],
    ),
    (
        "Hiburan",
        [
            "nonton", "film", "game", "spotify", "netflix", "hiburan", "bioskop",
            "youtube", "disney", "konser", "event",
        ],
    ),
    (
        "Olahraga",
        ["gym", "fitness", "renang", "futsal", "badminton", "sepatu olahraga", "olahraga"],
    ),
    (
        "Rumah",
        [
            "sewa", "kontrakan", "kos", "perabot", "service", "servis", "listrik rumah",
            "furnitur", "cat", "renovasi",
        ],
    ),
]

_INCOME_CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("Gaji", ["gaji", "gajian", "slip", "bulanan", "payroll"]),
    ("Freelance", ["proyek", "freelance", "honorar", "honor", "narasumber", "jualan", "laku", "proyekan"]),
    ("Investasi", ["dividen", "saham", "crypto", "kripto", "reksadana", "invest", "bunga", "profit", "cuan"]),
    ("Transfer", ["transfer", "kiriman", "ditransfer", "masuk dari", "go-pay", "gopay", "ovo", "dana"]),
]

# Relative date keywords in Indonesian
_RELATIVE_DATES: list[tuple[list[str], int]] = [
    (["kemarin", "kemaren"], -1),
    (["2 hari lalu", "dua hari lalu"], -2),
    (["3 hari lalu", "tiga hari lalu"], -3),
    (["minggu lalu", "seminggu lalu"], -7),
]

# Noise words that don't contribute to the expense description
_NOISE_WORDS = re.compile(
    r"(?i)\b("
    r"aku|saya|gue|gw|ane|w|"
    r"tadi|tadi(?:nya)?|ini|itu|"
    r"harga(?:nya)?|bayar|bayarin|beli(?:in)?|buat|untuk|dgn|dengan|"
    r"sebesar|senilai|seharga|totalnya|total|sebanyak|"
    r"di|ke|dari|yang|yg|dan|juga|udah|sudah|udh|"
    r"nya|lah|deh|dong|nih|sih|ya|yaa|wkwk"
    r")\b"
)

# Time-of-day words that look like numbers when stripped — used to detect false positives.
# e.g. "makan jam 12" should NOT be parsed as amount=12.
_TIME_CONTEXT_PATTERN = re.compile(
    r"(?i)\b(jam|pukul|pk\.?)\s*\d{1,2}(?:[.:]\d{2})?(?:\s*(?:pagi|siang|sore|malam|wib|wita|wit))?\b"
)

# Minimum threshold for bare (no-suffix) numbers to be trusted as amounts.
# Numbers below this AND without a suffix are treated as ambiguous.
_MIN_BARE_AMOUNT = 1_000


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def guess_type(text: str) -> str:
    """Return 'income' if text contains income keywords, else 'expense'."""
    lowered = text.lower()
    if any(kw in lowered for kw in _INCOME_KEYWORDS):
        return "income"
    return "expense"


# Private alias for internal use within this module
_guess_type = guess_type


def _guess_category(note: str, tx_type: str = "expense") -> str:
    lowered = note.lower()
    pool = _CATEGORY_KEYWORDS if tx_type == "expense" else _INCOME_CATEGORY_KEYWORDS
    for category, keywords in pool:
        if any(keyword in lowered for keyword in keywords):
            return category
    return "Lainnya"


def parse_relative_date(text: str) -> date:
    """Return a date offset from today if a relative keyword is found, else today."""
    lowered = text.lower()
    for keywords, offset in _RELATIVE_DATES:
        if any(kw in lowered for kw in keywords):
            return date.today() + timedelta(days=offset)
    return date.today()


# Private alias for internal use within this module
_parse_relative_date = parse_relative_date


def _normalize_indonesian_amount(text: str) -> str:
    # "2jt500rb" → 2_500_000
    text = re.sub(r'(?i)(\d+)\s*jt\s*(\d{1,3})\s*(?:rb|ribu|k)\b',
                  lambda m: str(int(m.group(1)) * 1_000_000 + int(m.group(2)) * 1_000),
                  text)
    # "2jt500" → 2_500_000 (dibaca: 2 juta 500 ribu)
    text = re.sub(r'(?i)(\d+)\s*jt\s*(\d{1,3})\b',
                  lambda m: str(int(m.group(1)) * 1_000_000 + int(m.group(2)) * 1_000),
                  text)
    # "1rb500" → 1_500
    text = re.sub(r'(?i)(\d+)\s*(?:rb|ribu|k)\s*(\d{1,3})\b(?!\s*(?:rb|ribu|jt|juta|k))',
                  lambda m: str(int(m.group(1)) * 1_000 + int(m.group(2))),
                  text)
    return text


def _normalize_number_str(num_str: str) -> str:
    """
    Normalize Indonesian/European thousand-separator formats to a plain float string.
    Examples:
      "1.500.000" → "1500000"
      "1.500"     → "1500"    (assumed thousands, not decimal)
      "1,5"       → "1.5"
      "150000"    → "150000"
    """
    dot_count = num_str.count(".")
    comma_count = num_str.count(",")

    if dot_count > 1:
        # e.g. "1.500.000" — dots are thousand separators
        return num_str.replace(".", "")
    if comma_count > 0 and dot_count == 0:
        # e.g. "1,5" or "1,500" — treat comma as decimal separator
        return num_str.replace(",", ".")
    if dot_count == 1 and comma_count == 0:
        # Ambiguous: "1.500" could be 1500 or 1.5
        # If the fractional part has exactly 3 digits → thousand separator
        parts = num_str.split(".")
        if len(parts[1]) == 3:
            return num_str.replace(".", "")
        # Otherwise treat as decimal (e.g. "1.5jt")
        return num_str
    # No separators
    return num_str


def coerce_amount(value) -> float:
    """Convert a raw amount value into a float (supports Indonesian separators)."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return 0.0

    # Strip common currency markers
    text = re.sub(r"(?i)rp\.?\s*", "", text)
    text = text.replace("IDR", "").replace("idr", "")
    text = re.sub(r"\s+", "", text)
    # Keep only digits and separators
    text = re.sub(r"[^0-9,\.]", "", text)
    if not text:
        return 0.0

    try:
        normalized = _normalize_number_str(text)
        return float(normalized)
    except Exception:
        return 0.0


# Private alias for internal use within this module
_coerce_amount = coerce_amount


def _parse_amount_local(text: str) -> tuple[float, str] | tuple[None, None]:
    """
    Return (amount, matched_token) for the most significant amount found in text,
    or (None, None) if nothing is found.

    Strategy: collect all matches, prefer those with an explicit rb/jt suffix
    (they are unambiguous), otherwise take the largest numeric value above the
    minimum threshold (_MIN_BARE_AMOUNT) to avoid false positives like "makan jam 12".
    """
    pattern = re.compile(
        r"(?i)(?P<num>\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
        r"\s*(?P<suffix>rb|ribu|jt|juta|k)?\b"
    )
    matches = list(pattern.finditer(text))
    if not matches:
        return None, None

    candidates: list[tuple[float, str, bool]] = []  # (value, token, has_suffix)
    for m in matches:
        num_str = _normalize_number_str(m.group("num"))
        suffix = (m.group("suffix") or "").lower()
        try:
            value = float(num_str)
        except ValueError:
            continue

        if suffix in {"rb", "ribu", "k"}:
            value *= 1_000
        elif suffix in {"jt", "juta"}:
            value *= 1_000_000

        if value <= 0:
            continue

        # For bare numbers (no suffix), apply minimum threshold to avoid
        # false positives. E.g. "makan jam 12" → 12 is discarded.
        if not suffix and value < _MIN_BARE_AMOUNT:
            continue

        candidates.append((float(int(value)), m.group(0), bool(suffix)))

    if not candidates:
        return None, None

    # Prefer suffixed candidates (unambiguous), then pick the largest value
    suffixed = [c for c in candidates if c[2]]
    pool = suffixed if suffixed else candidates
    best = max(pool, key=lambda c: c[0])
    return best[0], best[1]


def _clean_note(raw: str) -> str:
    """Remove noise words and tidy up whitespace from a note string."""
    cleaned = _NOISE_WORDS.sub(" ", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip("-–—:;,. ")
    # Capitalize first letter
    return cleaned.capitalize() if cleaned else "pengeluaran"


def _strip_time_references(text: str) -> str:
    """
    Remove time-of-day phrases (e.g. "jam 12", "pukul 08.00") from text
    before amount parsing to prevent the hour number from being mistaken
    as a transaction amount.
    """
    return _TIME_CONTEXT_PATTERN.sub("", text)


def _parse_expense_local(text: str, default_date: date | None = None) -> dict | None:
    # Strip time references first to avoid false amount detection
    sanitized = _strip_time_references(text)
    normalized_text = _normalize_indonesian_amount(sanitized)
    amount, token = _parse_amount_local(normalized_text)
    if amount is None or token is None:
        return None

    # Remove the amount token from the note
    note = normalized_text
    try:
        note = re.sub(re.escape(token), "", note, count=1, flags=re.IGNORECASE).strip()
    except re.error:
        note = normalized_text

    # Strip relative date keywords from note
    for keywords, _ in _RELATIVE_DATES:
        for kw in keywords:
            note = re.sub(re.escape(kw), "", note, flags=re.IGNORECASE)

    tx_type = _guess_type(text)
    note = _clean_note(note)
    if not note:
        note = "Pemasukan" if tx_type == "income" else "Pengeluaran"

    category = _guess_category(note, tx_type)
    expense_date = default_date or _parse_relative_date(text)

    return {
        "type": tx_type,
        "amount": float(amount),
        "category": category,
        "note": note,
        "date": expense_date,
    }


def parse_local_multiple(text: str, default_date: date | None = None) -> list[dict]:
    """Splits text by comma or 'dan' to parse multiple items locally."""
    default_date = default_date or _parse_relative_date(text)
    # Split the input text into phrases
    phrases = re.split(r"(?i)\s*(?:,|\bdan\b|\bterus\b|\bserta\b)\s*", text)
    items = []
    for phrase in phrases:
        if not phrase.strip():
            continue
        parsed = _parse_expense_local(phrase, default_date=default_date)
        if parsed and parsed.get("amount", 0) > 0:
            items.append(parsed)
    return items


# Private alias for internal use within this module
_parse_local_multiple = parse_local_multiple


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

class Confidence:
    HIGH = "high"    # Rule parser is certain — skip Gemini
    LOW  = "low"     # Ambiguous — escalate to Gemini


def _assess_confidence(text: str, items: list[dict]) -> str:
    """
    Determine how confident we are in the local parse result.

    HIGH confidence when:
      - At least one item was parsed
      - The original OR normalized text contains an explicit Indonesian suffix
        (rb/k/jt/juta/ribu) — handles compound forms like "2jt500rb" which
        lose their suffix after normalization.
      - No bare 4+ digit numbers remain after stripping suffixed tokens
        (avoids "nasi 35rb kemarin jam 1730" confusing 1730 as a second amount)

    LOW (escalate to Gemini) in all other cases.
    """
    if not items:
        return Confidence.LOW

    raw_stripped = _strip_time_references(text)
    normalized = _normalize_indonesian_amount(raw_stripped)

    # Pattern for standalone suffixed amounts: "35rb", "20k", "5jt"
    _SUFFIX_PATTERN = re.compile(
        r'\d+(?:[.,]\d+)?\s*(?:rb|ribu|jt|juta|k)\b', re.IGNORECASE
    )
    # Pattern for compound amounts: "2jt500rb", "1jt500" — `jt` has no \b because
    # it's directly followed by another digit, so we need a separate check.
    _COMPOUND_PATTERN = re.compile(
        r'\d+\s*(?:jt|juta)\s*\d{1,3}\s*(?:rb|ribu|k)?', re.IGNORECASE
    )

    has_suffix_raw = bool(_SUFFIX_PATTERN.search(raw_stripped))
    has_suffix_norm = bool(_SUFFIX_PATTERN.search(normalized))
    has_compound = bool(_COMPOUND_PATTERN.search(raw_stripped))

    if not (has_suffix_raw or has_suffix_norm or has_compound):
        return Confidence.LOW

    # Check for leftover bare numbers from the RAW (pre-normalization) text.
    # Working from raw avoids false positives where compound amounts like "2jt500rb"
    # get converted to "2500000" by normalization and then mistakenly flagged as
    # an unexpected bare number.
    check_text = _SUFFIX_PATTERN.sub('', raw_stripped)   # strip "35rb", "5jt", "20k"
    check_text = _COMPOUND_PATTERN.sub('', check_text)   # strip "2jt500rb", "1jt500"
    leftover_bare = re.findall(r'\b\d{4,}\b', check_text)
    if leftover_bare:
        # Still has unexplained bare large numbers — escalate to Gemini.
        return Confidence.LOW

    return Confidence.HIGH


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_local_transaction(text: str) -> tuple[list[dict], str]:
    """
    Parse a transaction string using only local rule-based logic.

    Returns:
        (items, confidence)
        - items: list of parsed transaction dicts (may be empty)
        - confidence: Confidence.HIGH or Confidence.LOW

    The caller should escalate to Gemini if confidence is LOW or items is empty.
    """
    items = _parse_local_multiple(text)
    confidence = _assess_confidence(text, items)
    return items, confidence
