"""Documented candidate-level fallbacks for races with no usable Kalshi market.

Each entry maps a race_id to a defensible candidate drawn from a public roster /
forecast. These are flagged FALLBACK_NO_MARKET in the audit and never silently
replace score-based picks in priced races. Populated only as needed after the
refresh reports NO_MARKET_FOUND rows.

Format: race_id -> {"candidate_name": str, "party": "D"|"R"|"I", "source": str}
"""
from __future__ import annotations

SENATE_FALLBACKS: dict[str, dict] = {
    # Kentucky has only primary-nominee markets on Kalshi (KXSENATEKYR/D), no
    # general-winner contract. Open seat (McConnell retiring); GOP nominee Andy
    # Barr in a Safe-R state. q from safe-seat rating, not a market price.
    "KY-SEN": {"candidate_name": "Andy Barr", "party": "R", "q": 0.95,
               "source": "public candidate roster; Safe-R open seat (Cook/Sabato)"},
}

# Nine California districts have no Kalshi market (safe seats; several are
# top-two same-party generals after the jungle primary, so the *party* is robust
# but the specific name is ambiguous). Zero-scoring fallbacks: they contribute no
# expected-points, only a valid/defensible row. Names from Ballotpedia/CalMatters
# 2026 rosters; flagged FALLBACK_NO_MARKET. q reflects seat safety, not a price.
HOUSE_FALLBACKS: dict[str, dict] = {
    "CA-04": {"candidate_name": "Mike Thompson", "party": "D", "q": 0.95,
              "source": "incumbent, Safe-D (Ballotpedia 2026)"},
    "CA-07": {"candidate_name": "Doris Matsui", "party": "D", "q": 0.95,
              "source": "incumbent, Safe-D (Ballotpedia 2026)"},
    "CA-11": {"candidate_name": "Scott Wiener", "party": "D", "q": 0.80,
              "source": "open seat (Pelosi retiring); D-vs-D top-two, Wiener frontrunner"},
    "CA-12": {"candidate_name": "Lateefah Simon", "party": "D", "q": 0.95,
              "source": "incumbent, Safe-D (Ballotpedia 2026)"},
    "CA-14": {"candidate_name": "Aisha Wahab", "party": "D", "q": 0.85,
              "source": "D-vs-D top-two, Safe-D (Ballotpedia 2026)"},
    "CA-29": {"candidate_name": "Luz Rivas", "party": "D", "q": 0.95,
              "source": "incumbent, Safe-D"},
    "CA-34": {"candidate_name": "Jimmy Gomez", "party": "D", "q": 0.90,
              "source": "incumbent, D-vs-D top-two, Safe-D"},
    "CA-37": {"candidate_name": "Sydney Kamlager-Dove", "party": "D", "q": 0.95,
              "source": "incumbent, Safe-D"},
    "CA-40": {"candidate_name": "Ken Calvert", "party": "R", "q": 0.80,
              "source": "R-held seat; R-vs-R top-two, Calvert incumbent"},
}
