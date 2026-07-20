"""API-Sports league id / English name → 中文 display name.

Single source of truth (mirrors ``team_names.py``):
- ingest / sync (``FootballFetcher._upsert_league``)
- list & detail APIs (``fixtures._league_name``)
- filter options (``leagues._name``)
- form / H2H match rows (``localize_match_row``)
"""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings

# English names shared by many countries — never default to a major league without country.
_NEEDS_COUNTRY = frozenset(
    {
        "Premier League",
        "Pro League",
        "Serie A",
        "Super League",
        "FA Cup",
        "League One",
        "League Two",
        "Liga Pro",
        "First Division",
        "Second Division",
    }
)

# Unambiguous English API names.
_BY_NAME: dict[str, str] = {
    "Championship": "英冠",
    "EFL Cup": "联赛杯",
    "La Liga": "西甲",
    "Segunda División": "西乙",
    "Copa Del Rey": "国王杯",
    "Serie B": "意乙",
    "Coppa Italia": "意大利杯",
    "Bundesliga": "德甲",
    "2. Bundesliga": "德乙",
    "DFB Pokal": "德国杯",
    "Ligue 1": "法甲",
    "Ligue 2": "法乙",
    "Coupe de France": "法国杯",
    "Eredivisie": "荷甲",
    "Primeira Liga": "葡超",
    "UEFA Champions League": "欧冠",
    "UEFA Europa League": "欧罗巴",
    "UEFA Europa Conference League": "欧协联",
    "UEFA Super Cup": "欧洲超级杯",
    "AFC Champions League": "亚冠",
    "AFC Champions League Elite": "亚冠精英",
    "AFC Champions League Two": "亚冠二级",
    "World Cup": "世界杯",
    "Euro Championship": "欧洲杯",
    "Africa Cup of Nations": "非洲杯",
    "Copa America": "美洲杯",
    "Confederations Cup": "联合会杯",
    "Friendlies": "友谊赛",
    "Friendlies Clubs": "俱乐部友谊赛",
    "Club Friendlies": "俱乐部友谊赛",
    "World Cup - Qualification Europe": "世预赛(欧)",
    "World Cup - Qualification Africa": "世预赛(非)",
    "World Cup - Qualification South America": "世预赛(南美)",
    "World Cup - Qualification Asia": "世预赛(亚)",
    "UEFA Nations League": "欧国联",
    "Scottish Premiership": "苏超",
    "Super Lig": "土超",
    "Saudi Pro League": "沙特联",
    "Major League Soccer": "美职联",
    "MLS": "美职联",
    "Brazil Serie A": "巴甲",
    "Serie A - Brazil": "巴甲",
    "A-League": "澳超",
    "J1 League": "日职联",
    "K League 1": "韩K联",
    "Korea Cup": "韩国杯",
    "Chinese Super League": "中超",
    "China League One": "中甲",
    "China League Two": "中乙",
    "CFA": "足协杯",
    "Chinese FA Cup": "足协杯",
    "1 Lyga": "立甲",
    "A Lyga": "立乙",
    "Calcutta Premier A Division": "加尔各答超A组",
    "Calcutta Premier Division": "加尔各答超",
    "I-League": "印度I联赛",
    "Division Profesional": "玻利甲",
}

# ``name|country`` as returned by API-Sports.
_BY_NAME_COUNTRY: dict[str, str] = {
    "Premier League|England": "英超",
    "Premier League|Malta": "马耳他超",
    "Premier League|Israel": "以超",
    "Premier League|Wales": "威超",
    "Premier League|Uganda": "乌干达超",
    "Premier League|Bahrain": "巴林超",
    "Premier League|Bangladesh": "孟加拉超",
    "Premier League|Ghana": "加纳超",
    "Premier League|Libya": "利比亚超",
    "Premier League|Kuwait": "科威特超",
    "Premier League|Hong-Kong": "港超",
    "Premier League|Hong Kong": "港超",
    "Premier League|Singapore": "新加坡超",
    "Premier League|Jamaica": "牙买加超",
    "Premier League|Trinidad-And-Tobago": "特立尼达超",
    "Premier League|Trinidad And Tobago": "特立尼达超",
    "League One|China": "中甲",
    "League Two|China": "中乙",
    "Super League|China": "中超",
    "Super League|Uzbekistan": "乌兹超",
    "Super League|Switzerland": "瑞士超",
    "Super League|Greece": "希腊超",
    "FA Cup|China": "足协杯",
    "FA Cup|England": "足总杯",
    "FA Cup|South-Korea": "韩国杯",
    "FA Cup|South Korea": "韩国杯",
    "Korea Cup|South-Korea": "韩国杯",
    "Korea Cup|South Korea": "韩国杯",
    "Serie A|Brazil": "巴甲",
    "Serie A|Italy": "意甲",
    "Serie B|Italy": "意乙",
    "League One|England": "英甲",
    "League Two|England": "英乙",
    "Pro League|Belgium": "比甲",
    "Pro League|Saudi-Arabia": "沙特联",
    "Pro League|Saudi Arabia": "沙特联",
    "Liga Pro|Ecuador": "厄甲",
    "Primera División|Bolivia": "玻利甲",
    "Division Profesional|Bolivia": "玻利甲",
    "First Division|Ireland": "爱超",
    "Premier Division|Ireland": "爱超",
}

# Country label for generic ``{country}超`` fallback.
_COUNTRY_ZH: dict[str, str] = {
    "England": "英格兰",
    "Malta": "马耳他",
    "Israel": "以色列",
    "Wales": "威尔士",
    "Uganda": "乌干达",
    "Bahrain": "巴林",
    "Bangladesh": "孟加拉",
    "Ghana": "加纳",
    "Libya": "利比亚",
    "Kuwait": "科威特",
    "Hong-Kong": "香港",
    "Hong Kong": "香港",
    "Singapore": "新加坡",
    "Jamaica": "牙买加",
    "India": "印度",
    "Lithuania": "立陶宛",
    "Ireland": "爱尔兰",
    "Scotland": "苏格兰",
    "Northern-Ireland": "北爱尔兰",
    "Northern Ireland": "北爱尔兰",
}


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _norm_country(country: str | None) -> str:
    return (country or "").strip()


def _country_key(country: str) -> str:
    return country.strip().replace(" ", "-")


def _country_matches(country: str, allowed: list[str]) -> bool:
    normalized = _country_key(country)
    for entry in allowed:
        candidate = _country_key(entry)
        if candidate == normalized:
            return True
        if candidate.replace("-", " ") == normalized.replace("-", " "):
            return True
    return False


def _lookup_name_country(name: str, country: str) -> str | None:
    if not country:
        return None
    return _BY_NAME_COUNTRY.get(f"{name}|{country}") or _BY_NAME_COUNTRY.get(
        f"{name}|{_country_key(country)}"
    )


def _catalog_name(settings: Settings, league_id: int, fallback: str = "") -> str:
    for label, lid in settings.REFERENCE_LEAGUE_IDS.items():
        if lid == league_id:
            return label
    configured = settings.league_display_name(league_id, fallback)
    if configured and configured != fallback:
        return configured
    return fallback


def _id_countries(settings: Settings, league_id: int) -> list[str]:
    if league_id in settings.LEAGUE_COUNTRIES:
        return [settings.LEAGUE_COUNTRIES[league_id]]
    if league_id in settings.REFERENCE_LEAGUE_COUNTRIES:
        return [settings.REFERENCE_LEAGUE_COUNTRIES[league_id]]
    return []


def _generic_country_label(country: str) -> str | None:
    if not country:
        return None
    return (
        _COUNTRY_ZH.get(country)
        or _COUNTRY_ZH.get(_country_key(country))
        or _COUNTRY_ZH.get(country.replace("-", " "))
    )


def _generic_league_name(name: str, country: str) -> str | None:
    label = _generic_country_label(country)
    if not label:
        return None
    if name in {"Premier League", "Super League"}:
        return f"{label}超"
    if name == "Pro League":
        return f"{label}联赛"
    if name in {"First Division", "Second Division"}:
        tier = "甲" if name == "First Division" else "乙"
        return f"{label}{tier}"
    return None


def league_name_zh(
    name: str | None,
    *,
    league_id: int | None = None,
    country: str | None = None,
    settings: Settings | None = None,
) -> str:
    """Resolve a display name; prefer configured/reference 中文, then name+country rules."""
    cfg = settings or get_settings()
    country_n = _norm_country(country)

    if league_id is not None:
        catalog = _catalog_name(cfg, league_id, "")
        if catalog and _has_cjk(catalog):
            allowed = _id_countries(cfg, league_id)
            if not allowed or not country_n or _country_matches(country_n, allowed):
                return catalog

    if not name or not str(name).strip():
        if league_id is not None:
            return _catalog_name(cfg, league_id, "") or f"League {league_id}"
        return ""

    trimmed = str(name).strip()
    if _has_cjk(trimmed):
        return trimmed

    by_country = _lookup_name_country(trimmed, country_n)
    if by_country:
        return by_country

    if league_id is not None:
        catalog = _catalog_name(cfg, league_id, trimmed)
        if catalog and _has_cjk(catalog):
            allowed = _id_countries(cfg, league_id)
            if not allowed or not country_n or _country_matches(country_n, allowed):
                if not (
                    trimmed in _NEEDS_COUNTRY
                    and allowed
                    and country_n
                    and not _country_matches(country_n, allowed)
                ):
                    return catalog

    if trimmed in _BY_NAME:
        return _BY_NAME[trimmed]

    if trimmed in _NEEDS_COUNTRY and country_n:
        generic = _generic_league_name(trimmed, country_n)
        if generic:
            return generic

    if "Friendly" in trimmed:
        return "俱乐部友谊赛" if "Club" in trimmed else "友谊赛"

    return trimmed


def localize_match_row(match: dict[str, Any]) -> dict[str, Any]:
    """Localize team + league labels on a form/H2H row."""
    from app.services.team_names import localize_match_teams

    row = localize_match_teams(dict(match))
    league_id_raw = row.get("league_id")
    try:
        league_id = int(league_id_raw) if league_id_raw is not None else None
    except (TypeError, ValueError):
        league_id = None
    country_raw = row.get("league_country")
    country = str(country_raw).strip() if country_raw else None
    raw_name = row.get("league_name")
    row["league_name"] = league_name_zh(
        raw_name if isinstance(raw_name, str) else None,
        league_id=league_id,
        country=country,
    )
    return row


def localize_matches_block(block: dict[str, Any] | None) -> dict[str, Any]:
    """Localize all match rows inside a form / H2H summary dict."""
    if not isinstance(block, dict):
        return {"played": 0, "matches": []}
    matches = block.get("matches")
    if isinstance(matches, list):
        block = {
            **block,
            "matches": [
                localize_match_row(dict(m)) for m in matches if isinstance(m, dict)
            ],
        }
    return block
