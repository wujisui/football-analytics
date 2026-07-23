"""Auto-translate unmapped clubs that appear in ``config/leagues.json`` leagues.

Curated names in ``team_names.BY_ID`` always win. Accepted machine translations
are stored in ``data/team_names_auto.json`` and merged at lookup time.

Machine translation is a fallback only — football short names are often wrong
(e.g. Hearts →「心」). Strict quality gates reject garbage; prefer adding common
clubs to ``team_names.BY_ID``.

Run via::

    python manage.py translate-catalog-teams
    python manage.py translate-catalog-teams --dry-run
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.fixture import Fixture
from app.models.team import Team
from app.services.team_names import (
    backfill_team_names,
    name_has_cjk,
    persist_auto_names,
    team_needs_zh,
)

logger = logging.getLogger(__name__)

_SUFFIX_RE = re.compile(
    r"[\s.\-]*(?:fc|ff|fk|nk|afc|cf|sc|ac|bk|if|sk|vsc|sv|asd|calcio|aif)\s*$",
    re.IGNORECASE,
)
_LEADING_JUNK_RE = re.compile(r"^\s*\d+[\.、:：)\]]\s*")
_BAD_ZH_RE = re.compile(
    r"(公司|股份|省|市辖|spain|province|http|www|_|[A-Za-z0-9])",
    re.IGNORECASE,
)
_TRANSLATE_URL = "https://api.mymemory.translated.net/get"
_MAX_PER_RUN = 80


def _clean_source_name(name: str) -> str:
    text = str(name or "").strip()
    text = _SUFFIX_RE.sub("", text).strip(" .-_")
    return text or str(name or "").strip()


def _accept_zh(source: str, zh: str) -> str | None:
    """Return cleaned Chinese name or None when machine output is unusable."""
    text = _LEADING_JUNK_RE.sub("", str(zh or "").strip())
    text = re.sub(r"\s+", "", text)
    if not text or not name_has_cjk(text):
        return None
    if len(text) < 2 or len(text) > 16:
        return None
    if _BAD_ZH_RE.search(text):
        return None
    # Too short vs long English club names is often a failed gloss (Hearts→心).
    src = _clean_source_name(source)
    if len(src) >= 10 and len(text) <= 2:
        return None
    return text


async def _translate_en_to_zh(client: httpx.AsyncClient, name: str) -> str | None:
    source = _clean_source_name(name)
    if not source or name_has_cjk(source):
        return source if name_has_cjk(source) else None
    try:
        resp = await client.get(
            _TRANSLATE_URL,
            params={"q": source, "langpair": "en|zh-CN"},
            timeout=12.0,
        )
        resp.raise_for_status()
        payload = resp.json()
        text = str((payload.get("responseData") or {}).get("translatedText") or "").strip()
    except Exception as exc:
        logger.warning("Team name translate failed for %r: %s", name, exc)
        raise
    if not text or text.lower() == source.lower():
        return None
    accepted = _accept_zh(name, text)
    if accepted is None:
        logger.info("Rejected low-quality translate for %r -> %r", name, text)
    return accepted


async def list_untranslated_catalog_teams(session: AsyncSession) -> list[Team]:
    """Clubs that appear in fixtures of ``leagues.json`` leagues and still lack Chinese."""
    settings = get_settings()
    league_ids = set(settings.LEAGUE_IDS.values())
    if not league_ids:
        return []

    home_ids = select(Fixture.home_team_id).where(Fixture.league_id.in_(league_ids))
    away_ids = select(Fixture.away_team_id).where(Fixture.league_id.in_(league_ids))
    team_id_rows = (await session.execute(home_ids.union(away_ids))).all()
    ids = {int(row[0]) for row in team_id_rows if row and row[0] is not None}
    if not ids:
        return []

    teams = (
        await session.execute(select(Team).where(Team.id.in_(ids)).order_by(Team.id))
    ).scalars().all()
    return [team for team in teams if team_needs_zh(team.name, team.id)]


async def auto_translate_catalog_teams(
    session: AsyncSession,
    *,
    dry_run: bool = False,
    limit: int = _MAX_PER_RUN,
) -> dict[str, Any]:
    """Translate missing catalog-league clubs and persist auto map + DB names."""
    missing = await list_untranslated_catalog_teams(session)
    targets = missing[: max(0, limit)]
    proposed: dict[int, str] = {}
    rejected = 0
    transport_errors = 0
    aborted = False

    if targets:
        settings = get_settings()
        async with httpx.AsyncClient(verify=settings.HTTP_VERIFY_SSL) as client:
            for idx, team in enumerate(targets):
                try:
                    zh = await _translate_en_to_zh(client, team.name)
                except Exception:
                    transport_errors += 1
                    if transport_errors >= 3 and not proposed:
                        aborted = True
                        logger.error(
                            "Aborting catalog team auto-translate after %s transport errors",
                            transport_errors,
                        )
                        break
                    continue
                transport_errors = 0
                if zh:
                    proposed[team.id] = zh
                    logger.info(
                        "Auto team name: %s (%s) -> %s",
                        team.name,
                        team.id,
                        zh,
                    )
                else:
                    rejected += 1
                if idx + 1 < len(targets):
                    await asyncio.sleep(0.25)

    stored = 0 if dry_run else persist_auto_names(proposed)
    backfilled = 0 if dry_run else await backfill_team_names(session)
    if dry_run:
        unresolved = [team for team in missing if team.id not in proposed]
    else:
        unresolved = [team for team in missing if team_needs_zh(team.name, team.id)]
    return {
        "catalog_missing": len(missing),
        "attempted": 0 if aborted and not proposed else len(targets),
        "translated": len(proposed),
        "rejected": rejected,
        "stored": stored,
        "backfilled": backfilled,
        "dry_run": dry_run,
        "aborted": aborted,
        "still_missing": [{"id": t.id, "name": t.name} for t in unresolved[:30]],
        "samples": [{"id": tid, "zh": zh} for tid, zh in list(proposed.items())[:10]],
    }
