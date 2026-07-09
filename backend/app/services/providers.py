import logging
from datetime import datetime
from typing import Any

import httpx

from app.core.config import Settings
from app.services.api_utils import extract_items, first_value, map_fixture_status, parse_date

logger = logging.getLogger(__name__)


class BaseApiProvider:
    provider_name = "base"
    last_response: httpx.Response | None = None

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch_leagues_payload(
        self,
        client: httpx.AsyncClient,
        league_ids: list[int],
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def fetch_teams_payload(
        self,
        client: httpx.AsyncClient,
        league_id: int,
        season: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def fetch_fixtures_payload(
        self,
        client: httpx.AsyncClient,
        date: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def fetch_fixture_detail_payload(
        self,
        client: httpx.AsyncClient,
        fixture_id: int,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def fetch_quota_payload(self, client: httpx.AsyncClient) -> dict[str, Any]:
        raise NotImplementedError

    async def fetch_headtohead_payload(
        self,
        client: httpx.AsyncClient,
        home_team_id: int,
        away_team_id: int,
        last: int = 5,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def fetch_team_statistics_payload(
        self,
        client: httpx.AsyncClient,
        team_id: int,
        league_id: int,
        season: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def fetch_team_form_payload(
        self,
        client: httpx.AsyncClient,
        team_id: int,
        last: int = 5,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def fetch_odds_payload(
        self,
        client: httpx.AsyncClient,
        fixture_id: int,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def fetch_lineups_payload(
        self,
        client: httpx.AsyncClient,
        fixture_id: int,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def fetch_injuries_payload(
        self,
        client: httpx.AsyncClient,
        fixture_id: int,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def parse_leagues(self, payload: dict[str, Any], league_ids: list[int]) -> list[dict[str, Any]]:
        raise NotImplementedError

    def parse_teams(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        raise NotImplementedError

    def parse_fixtures(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        raise NotImplementedError

    def _json_from_response(self, response: httpx.Response) -> dict[str, Any]:
        self.last_response = response
        payload = response.json()
        if not isinstance(payload, dict):
            return {"response": payload}
        return payload


class ApiFootballProvider(BaseApiProvider):
    provider_name = "api_football"

    async def fetch_leagues_payload(
        self,
        client: httpx.AsyncClient,
        league_ids: list[int],
    ) -> dict[str, Any]:
        response = await client.get(
            self.settings.API_ENDPOINT_LEAGUES,
            params={"id": ",".join(map(str, league_ids))},
        )
        response.raise_for_status()
        return self._json_from_response(response)

    async def fetch_teams_payload(
        self,
        client: httpx.AsyncClient,
        league_id: int,
        season: str,
    ) -> dict[str, Any]:
        response = await client.get(
            self.settings.API_ENDPOINT_TEAMS,
            params={"league": league_id, "season": season},
        )
        response.raise_for_status()
        return self._json_from_response(response)

    async def fetch_fixtures_payload(
        self,
        client: httpx.AsyncClient,
        date: str,
    ) -> dict[str, Any]:
        response = await client.get(
            self.settings.API_ENDPOINT_FIXTURES,
            params={"date": date},
        )
        response.raise_for_status()
        return self._json_from_response(response)

    async def fetch_fixture_detail_payload(
        self,
        client: httpx.AsyncClient,
        fixture_id: int,
    ) -> dict[str, Any]:
        response = await client.get(
            self.settings.API_ENDPOINT_FIXTURE_DETAIL,
            params={"id": fixture_id},
        )
        response.raise_for_status()
        return self._json_from_response(response)

    async def fetch_quota_payload(self, client: httpx.AsyncClient) -> dict[str, Any]:
        response = await client.get(self.settings.API_ENDPOINT_QUOTA)
        response.raise_for_status()
        return self._json_from_response(response)

    async def fetch_headtohead_payload(
        self,
        client: httpx.AsyncClient,
        home_team_id: int,
        away_team_id: int,
        last: int = 5,
    ) -> dict[str, Any]:
        response = await client.get(
            self.settings.API_ENDPOINT_HEADTOHEAD,
            params={"h2h": f"{home_team_id}-{away_team_id}", "last": last},
        )
        response.raise_for_status()
        return self._json_from_response(response)

    async def fetch_team_statistics_payload(
        self,
        client: httpx.AsyncClient,
        team_id: int,
        league_id: int,
        season: str,
    ) -> dict[str, Any]:
        response = await client.get(
            self.settings.API_ENDPOINT_TEAM_STATISTICS,
            params={"team": team_id, "league": league_id, "season": season},
        )
        response.raise_for_status()
        return self._json_from_response(response)

    async def fetch_team_form_payload(
        self,
        client: httpx.AsyncClient,
        team_id: int,
        last: int = 5,
    ) -> dict[str, Any]:
        response = await client.get(
            self.settings.API_ENDPOINT_FIXTURES,
            params={"team": team_id, "last": last},
        )
        response.raise_for_status()
        return self._json_from_response(response)

    async def fetch_odds_payload(
        self,
        client: httpx.AsyncClient,
        fixture_id: int,
    ) -> dict[str, Any]:
        response = await client.get(
            self.settings.API_ENDPOINT_ODDS,
            params={"fixture": fixture_id},
        )
        response.raise_for_status()
        return self._json_from_response(response)

    async def fetch_lineups_payload(
        self,
        client: httpx.AsyncClient,
        fixture_id: int,
    ) -> dict[str, Any]:
        response = await client.get(
            self.settings.API_ENDPOINT_LINEUPS,
            params={"fixture": fixture_id},
        )
        response.raise_for_status()
        return self._json_from_response(response)

    async def fetch_injuries_payload(
        self,
        client: httpx.AsyncClient,
        fixture_id: int,
    ) -> dict[str, Any]:
        response = await client.get(
            self.settings.API_ENDPOINT_INJURIES,
            params={"fixture": fixture_id},
        )
        response.raise_for_status()
        return self._json_from_response(response)

    def parse_leagues(self, payload: dict[str, Any], league_ids: list[int]) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []
        allowed = set(league_ids)

        for item in extract_items(payload):
            league_id = first_value(item, [["league", "id"], ["id"], ["leagueId"], ["league_id"]])
            if league_id is None:
                continue
            league_id = int(league_id)
            if allowed and league_id not in allowed:
                continue

            seasons = item.get("seasons", [])
            current_season = next(
                (season for season in seasons if season.get("current")),
                seasons[0] if seasons else None,
            )
            season = str(
                first_value(current_season or {}, [["year"], ["season"]]) or datetime.now().year
            )

            parsed.append(
                {
                    "id": league_id,
                    "name": first_value(item, [["league", "name"], ["name"], ["leagueName"]], ""),
                    "country": first_value(
                        item, [["country", "name"], ["country"], ["countryName"]], ""
                    ),
                    "season": season,
                }
            )
        return parsed

    def parse_teams(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []
        for item in extract_items(payload):
            team_id = first_value(item, [["team", "id"], ["id"], ["teamId"], ["team_id"]])
            if team_id is None:
                continue
            parsed.append(
                {
                    "id": int(team_id),
                    "name": first_value(item, [["team", "name"], ["name"], ["teamName"]], ""),
                    "logo_url": first_value(
                        item, [["team", "logo"], ["logo"], ["logoUrl"], ["image"]]
                    ),
                }
            )
        return parsed

    def parse_fixtures(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []
        for item in extract_items(payload):
            fixture_id = first_value(item, [["fixture", "id"], ["id"], ["fixtureId"], ["fixture_id"]])
            league_id = first_value(item, [["league", "id"], ["leagueId"], ["league_id"]])
            home_team_id = first_value(
                item, [["teams", "home", "id"], ["homeTeam", "id"], ["home_team_id"]]
            )
            away_team_id = first_value(
                item, [["teams", "away", "id"], ["awayTeam", "id"], ["away_team_id"]]
            )
            fixture_date = parse_date(
                first_value(item, [["fixture", "date"], ["date"], ["matchDate"], ["kickoff"]])
            )
            if None in (fixture_id, league_id, home_team_id, away_team_id, fixture_date):
                continue

            parsed.append(
                {
                    "id": int(fixture_id),
                    "league_id": int(league_id),
                    "league_name": first_value(item, [["league", "name"], ["leagueName"]], ""),
                    "country": first_value(item, [["league", "country"], ["country"]], ""),
                    "season": str(
                        first_value(item, [["league", "season"], ["season"]], datetime.now().year)
                    ),
                    "home_team_id": int(home_team_id),
                    "away_team_id": int(away_team_id),
                    "home_team_name": first_value(
                        item, [["teams", "home", "name"], ["homeTeam", "name"]], ""
                    ),
                    "away_team_name": first_value(
                        item, [["teams", "away", "name"], ["awayTeam", "name"]], ""
                    ),
                    "home_logo": first_value(item, [["teams", "home", "logo"], ["homeTeam", "logo"]]),
                    "away_logo": first_value(item, [["teams", "away", "logo"], ["awayTeam", "logo"]]),
                    "date": fixture_date,
                    "status": map_fixture_status(
                        first_value(
                            item, [["fixture", "status", "short"], ["status", "short"], ["status"]]
                        )
                    ),
                }
            )
        return parsed


class LiveFootballDataProvider(BaseApiProvider):
    provider_name = "live_football_data"

    async def _request_json(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = await client.get(path, params=params)
        response.raise_for_status()
        return self._json_from_response(response)

    async def fetch_leagues_payload(
        self,
        client: httpx.AsyncClient,
        league_ids: list[int],
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if league_ids:
            params["id"] = ",".join(map(str, league_ids))
        return await self._request_json(client, self.settings.API_ENDPOINT_LEAGUES, params or None)

    async def fetch_teams_payload(
        self,
        client: httpx.AsyncClient,
        league_id: int,
        season: str,
    ) -> dict[str, Any]:
        param_sets = [
            {"league": league_id, "season": season},
            {"league_id": league_id, "season": season},
            {"leagueId": league_id, "season": season},
            {"id": league_id, "season": season},
        ]
        last_error: Exception | None = None
        for params in param_sets:
            try:
                return await self._request_json(client, self.settings.API_ENDPOINT_TEAMS, params)
            except Exception as exc:
                last_error = exc
                logger.debug("Teams request failed with params %s: %s", params, exc)
        assert last_error is not None
        raise last_error

    async def fetch_fixtures_payload(
        self,
        client: httpx.AsyncClient,
        date: str,
    ) -> dict[str, Any]:
        param_sets = [
            {"date": date},
            {"match_date": date},
            {"date_from": date, "date_to": date},
        ]
        last_error: Exception | None = None
        for params in param_sets:
            try:
                return await self._request_json(
                    client, self.settings.API_ENDPOINT_FIXTURES, params
                )
            except Exception as exc:
                last_error = exc
                logger.debug("Fixtures request failed with params %s: %s", params, exc)
        assert last_error is not None
        raise last_error

    async def fetch_fixture_detail_payload(
        self,
        client: httpx.AsyncClient,
        fixture_id: int,
    ) -> dict[str, Any]:
        param_sets = [
            {"id": fixture_id},
            {"fixture_id": fixture_id},
            {"fixtureId": fixture_id},
        ]
        last_error: Exception | None = None
        for params in param_sets:
            try:
                return await self._request_json(
                    client,
                    self.settings.API_ENDPOINT_FIXTURE_DETAIL,
                    params,
                )
            except Exception as exc:
                last_error = exc
                logger.debug("Fixture detail request failed with params %s: %s", params, exc)
        assert last_error is not None
        raise last_error

    async def fetch_quota_payload(self, client: httpx.AsyncClient) -> dict[str, Any]:
        return await self._request_json(
            client,
            self.settings.API_ENDPOINT_QUOTA,
            {"search": "a"},
        )

    async def fetch_headtohead_payload(
        self,
        client: httpx.AsyncClient,
        home_team_id: int,
        away_team_id: int,
        last: int = 5,
    ) -> dict[str, Any]:
        return await ApiFootballProvider(self.settings).fetch_headtohead_payload(
            client, home_team_id, away_team_id, last
        )

    async def fetch_team_statistics_payload(
        self,
        client: httpx.AsyncClient,
        team_id: int,
        league_id: int,
        season: str,
    ) -> dict[str, Any]:
        return await ApiFootballProvider(self.settings).fetch_team_statistics_payload(
            client, team_id, league_id, season
        )

    async def fetch_team_form_payload(
        self,
        client: httpx.AsyncClient,
        team_id: int,
        last: int = 5,
    ) -> dict[str, Any]:
        return await ApiFootballProvider(self.settings).fetch_team_form_payload(
            client, team_id, last
        )

    async def fetch_odds_payload(
        self,
        client: httpx.AsyncClient,
        fixture_id: int,
    ) -> dict[str, Any]:
        return {"response": []}

    async def fetch_lineups_payload(
        self,
        client: httpx.AsyncClient,
        fixture_id: int,
    ) -> dict[str, Any]:
        return {"response": []}

    async def fetch_injuries_payload(
        self,
        client: httpx.AsyncClient,
        fixture_id: int,
    ) -> dict[str, Any]:
        return {"response": []}

    def parse_leagues(self, payload: dict[str, Any], league_ids: list[int]) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []
        allowed = set(league_ids)

        for item in extract_items(payload):
            league_id = first_value(item, [["league", "id"], ["id"], ["leagueId"], ["league_id"]])
            if league_id is None:
                continue
            league_id = int(league_id)
            if allowed and league_id not in allowed:
                continue

            parsed.append(
                {
                    "id": league_id,
                    "name": first_value(item, [["league", "name"], ["name"], ["leagueName"]], ""),
                    "country": first_value(
                        item, [["country", "name"], ["country"], ["countryName"]], ""
                    ),
                    "season": str(
                        first_value(
                            item,
                            [["season"], ["seasonYear"], ["currentSeason"]],
                            datetime.now().year,
                        )
                    ),
                }
            )
        return parsed

    def parse_teams(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return ApiFootballProvider(self.settings).parse_teams(payload)

    def parse_fixtures(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return ApiFootballProvider(self.settings).parse_fixtures(payload)


class ApiFootball186Provider(ApiFootballProvider):
    provider_name = "api_football186"

    async def _try_paths(
        self,
        client: httpx.AsyncClient,
        paths: list[str],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        unique_paths: list[str] = []
        for path in paths:
            if path and path not in unique_paths:
                unique_paths.append(path)

        last_error: Exception | None = None
        for path in unique_paths:
            try:
                response = await client.get(path, params=params)
                response.raise_for_status()
                return self._json_from_response(response)
            except Exception as exc:
                last_error = exc
                logger.debug("Request failed for %s with params %s: %s", path, params, exc)

        assert last_error is not None
        raise last_error

    async def fetch_leagues_payload(
        self,
        client: httpx.AsyncClient,
        league_ids: list[int],
    ) -> dict[str, Any]:
        params = {"id": ",".join(map(str, league_ids))} if league_ids else None
        return await self._try_paths(
            client,
            [self.settings.API_ENDPOINT_LEAGUES, "/v3/leagues", "/leagues"],
            params,
        )

    async def fetch_teams_payload(
        self,
        client: httpx.AsyncClient,
        league_id: int,
        season: str,
    ) -> dict[str, Any]:
        param_sets = [
            {"league": league_id, "season": season},
            {"league_id": league_id, "season": season},
        ]
        last_error: Exception | None = None
        for params in param_sets:
            try:
                return await self._try_paths(
                    client,
                    [self.settings.API_ENDPOINT_TEAMS, "/v3/teams", "/teams"],
                    params,
                )
            except Exception as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    async def fetch_fixtures_payload(
        self,
        client: httpx.AsyncClient,
        date: str,
    ) -> dict[str, Any]:
        param_sets = [{"date": date}, {"match_date": date}]
        last_error: Exception | None = None
        for params in param_sets:
            try:
                return await self._try_paths(
                    client,
                    [self.settings.API_ENDPOINT_FIXTURES, "/v3/fixtures", "/fixtures"],
                    params,
                )
            except Exception as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    async def fetch_fixture_detail_payload(
        self,
        client: httpx.AsyncClient,
        fixture_id: int,
    ) -> dict[str, Any]:
        param_sets = [{"id": fixture_id}, {"fixture_id": fixture_id}]
        last_error: Exception | None = None
        for params in param_sets:
            try:
                return await self._try_paths(
                    client,
                    [self.settings.API_ENDPOINT_FIXTURE_DETAIL, "/v3/fixtures", "/fixtures"],
                    params,
                )
            except Exception as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    async def fetch_quota_payload(self, client: httpx.AsyncClient) -> dict[str, Any]:
        response = await client.get(self.settings.API_ENDPOINT_QUOTA)
        response.raise_for_status()
        return self._json_from_response(response)


def get_api_provider(settings: Settings) -> BaseApiProvider:
    if settings.API_PROVIDER == "api_football":
        return ApiFootballProvider(settings)
    if settings.API_PROVIDER == "api_football186":
        return ApiFootball186Provider(settings)
    return LiveFootballDataProvider(settings)
