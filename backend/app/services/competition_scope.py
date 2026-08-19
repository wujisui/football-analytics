"""Competition admission policy for worldwide fixture feeds.

API-Sports returns every competition for a date in one response.  Only IDs
listed here (plus the configured catalog) may cross the persistence boundary.
IDs are verified against official payloads already stored in ``api_snapshots``;
do not infer IDs from names or list order.
"""

from __future__ import annotations

from typing import Protocol


class _SettingsWithLeagues(Protocol):
    LEAGUE_IDS: dict[str, int]


# Current non-catalog top divisions observed in the official date feed.
TOP_DIVISION_IDS = frozenset(
    {
        116,  # Belarus - Premier League
        239,  # Colombia - Primera A
        288,  # South Africa - Premier Soccer League
        290,  # Iran - Persian Gulf Pro League
        305,  # Qatar - Stars League
        342,  # Armenia - Premier League
        369,  # Uzbekistan - Super League
        401,  # Zimbabwe - Premier Soccer League
        479,  # Canada - Canadian Premier League
        566,  # Burundi - Ligue A
        567,  # Tanzania - Ligi kuu Bara
        1031,  # Bhutan - Premier League
    }
)

# Senior national / regional cups from established top-flight regions.
SENIOR_CUP_IDS = frozenset(
    {
        24,  # AFF Championship
        102,  # Japan - Emperor Cup
        115,  # Sweden - Svenska Cupen
        121,  # Denmark - DBU Pokalen
        130,  # Argentina - Copa Argentina
        199,  # Greece - Cup
        237,  # Russia - Cup
        241,  # Colombia - Cup
        285,  # Romania - Cupa Romaniei
        294,  # South Korea - FA Cup
        347,  # Czech Republic - Cup
        498,  # Kazakhstan - Cup
        501,  # Paraguay - Copa Paraguay
        504,  # Saudi Arabia - King's Cup
        680,  # Slovakia - Cup
        874,  # Australia - Australia Cup
        917,  # Ecuador - Copa Ecuador
        1028,  # CONCACAF Central American Cup
        1113,  # Venezuela - Copa Venezuela
    }
)

# Club friendlies. International friendlies are already in the configured
# catalog for the current provider ID set.
FRIENDLY_IDS = frozenset({667})

EXTRA_COMPETITION_IDS = TOP_DIVISION_IDS | SENIOR_CUP_IDS | FRIENDLY_IDS


def allowed_competition_ids(settings: _SettingsWithLeagues) -> frozenset[int]:
    """Configured catalog plus the explicit non-catalog whitelist."""
    configured = {int(value) for value in settings.LEAGUE_IDS.values()}
    return frozenset(configured | EXTRA_COMPETITION_IDS)


def competition_is_allowed(
    league_id: int,
    settings: _SettingsWithLeagues,
) -> bool:
    return int(league_id) in allowed_competition_ids(settings)
