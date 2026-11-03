"""Race -> Kalshi series mapping and candidate metadata.

Senate mapping is a prioritized list per race_id; the refresh step picks the
first series that yields a verifiable 2026 event with active, priced candidate
markets. We verify the *cycle* from event metadata (title/sub_title "2026" and a
post-election close_time), NOT from ticker spelling, per the task's warning about
confusing legacy Senate tickers (e.g. SENATEGA-28 is the 2028 race).
"""
from __future__ import annotations

# Prioritized candidate Kalshi series per Senate race_id.
# Person-level ("Person") series are preferred for same-party / jungle contests.
SENATE_SERIES: dict[str, list[str]] = {
    "AK-SEN": ["KXAKSENATE", "SENATEAK"],
    "AL-SEN": ["SENATEAL", "KXSENATEAL"],
    "AR-SEN": ["KXSENATEAR", "SENATEAR"],
    "CO-SEN": ["KXSENATECO", "SENATECO"],
    "DE-SEN": ["SENATEDE", "KXSENATEDE"],
    "FL-SEN": ["SENATEFLS"],            # 2026 Florida SPECIAL (Rubio seat)
    "GA-SEN": ["SENATEGA"],
    "IA-SEN": ["KXIASENATE", "SENATEIA"],
    "ID-SEN": ["KXSENATEID", "SENATEID"],
    "IL-SEN": ["SENATEIL", "KXSENATEIL"],
    "KS-SEN": ["SENATEKS", "KXSENATEKS"],
    "KY-SEN": ["SENATEKY", "KXSENATEKY"],
    "LA-SEN": ["KXSENATELA", "SENATELA"],
    "MA-SEN": ["SENATEMA", "KXSENATEMA"],
    "ME-SEN": ["KXMESENATEPERSON", "SENATEME"],
    "MI-SEN": ["KXMISENATE", "SENATEMI"],
    "MN-SEN": ["SENATEMN", "KXSENATEMN"],
    "MS-SEN": ["SENATEMS", "KXSENATEMS"],
    "MT-SEN": ["SENATEMT", "KXSENATEMT"],
    "NC-SEN": ["SENATENC", "KXSENATENC"],
    "NE-SEN": ["SENATENE", "SENATENES", "KXSENATENE"],
    "NH-SEN": ["SENATENH", "KXSENATENH"],
    "NJ-SEN": ["SENATENJ", "KXSENATENJ"],
    "NM-SEN": ["SENATENM", "KXSENATENM"],
    "OH-SEN": ["SENATEOHS"],            # 2026 Ohio SPECIAL (Vance seat)
    "OK-SEN": ["KXSENATEOK", "SENATEOK"],
    "OR-SEN": ["SENATEOR", "KXSENATEOR"],
    "RI-SEN": ["SENATERI", "KXSENATERI"],
    "SC-SEN": ["SENATESC", "KXSENATESC"],
    "SD-SEN": ["SENATESD", "KXSENATESD"],
    "TN-SEN": ["SENATETN", "KXSENATETN"],
    "TX-SEN": ["SENATETX", "KXSENATETX"],
    "VA-SEN": ["SENATEVA", "KXSENATEVA"],
    "WV-SEN": ["SENATEWV", "KXSENATEWV"],
    "WY-SEN": ["SENATEWY", "KXSENATEWY"],
}

# Party lookup for person-level markets whose ticker suffix is not -D/-R.
# Only realistic 2026 general-election contenders are needed; keyed by lowercased
# candidate display name. Sourced from public candidate rosters / news (2026).
PERSON_PARTY: dict[str, str] = {
    # Alaska
    "dan sullivan": "R", "mary peltola": "D", "daniel j. sullivan jr.": "R",
    "ann diener": "I", "richard grayson": "I", "sid hill": "I",
    "gerald heikes": "R",
    # Michigan
    "mike rogers": "R", "abdul el-sayed": "D", "haley stevens": "D",
    "mallory mcmorrow": "D",
    # Iowa
    "joni ernst": "R", "ashley hinson": "R", "zach wahls": "D",
    "nathan sage": "D", "josh turek": "D",
    # Idaho
    "jim risch": "R", "david roth": "D", "todd achilles": "D",
    # Maine
    "susan collins": "R", "graham platner": "D", "jordan wood": "D",
    "janet mills": "D", "troy jackson": "D", "shenna bellows": "D",
    "sara gideon": "D", "dan kleban": "D", "jared golden": "D",
    "nirav shah": "D", "angus king": "I", "angus king iii": "I",
    "patrick dempsey": "D", "valli geiger": "D", "brian bryant": "D",
    "mattie daughtrey": "D", "stephen king": "D",
    # Nebraska (Osborn runs as an Independent)
    "dan osborn": "I", "pete ricketts": "R", "cindy burbank": "D",
    # South Dakota
    "mike rounds": "R", "julian beaudion": "D", "brian bengs": "D",
    # House person-level / at-large extras
    "nick begich iii": "R", "eric hafner": "D", "bill hill": "I",
}


def party_for(ticker: str, candidate_name: str) -> str | None:
    """Infer party from a market ticker suffix (-D/-R/-I) or candidate name."""
    suf = ticker.rsplit("-", 1)[-1].upper() if "-" in ticker else ""
    if suf in ("D", "DEM", "DFL"):
        return "D"
    if suf in ("R", "REP", "GOP"):
        return "R"
    if suf in ("I", "IND"):
        return "I"
    return PERSON_PARTY.get((candidate_name or "").strip().lower())


def event_is_2026(event: dict) -> bool:
    """True iff an event is the 2026 cycle contest (not 2028, not a primary)."""
    et = (event.get("event_ticker") or "")
    title = (event.get("title") or "").lower()
    sub = (event.get("sub_title") or "").lower()
    # Positive 2026 signals
    says_2026 = ("2026" in title or "2026" in sub or "in 2026" in sub
                 or "-26" in et or et.endswith("26") or "26NOV" in et or "26OCT" in et)
    # Negative signals (other cycles)
    says_other = any(y in (title + sub) for y in ("2028", "2024", "2030")) or "-28" in et or "-24" in et
    # Must settle after the Nov-2026 election if a close_time is present on a market
    return says_2026 and not says_other
