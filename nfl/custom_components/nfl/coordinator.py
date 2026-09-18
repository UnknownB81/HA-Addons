from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from aiohttp import ClientError, ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SCOREBOARD_URL, STANDINGS_URL


class NFLCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, update_interval: timedelta) -> None:
        self._session: ClientSession = aiohttp_client.async_get_clientsession(hass)
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name="NFL",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            standings, preseason, scoreboard = await asyncio.gather(
                self._async_get_json(STANDINGS_URL, {"seasontype": 2, "level": 3}),
                self._async_get_json(STANDINGS_URL, {"seasontype": 1, "level": 3}),
                self._async_get_json(SCOREBOARD_URL, {}),
            )
        except (ClientError, TimeoutError, ValueError) as error:
            raise UpdateFailed(f"Impossible de recuperer les donnees ESPN: {error}") from error

        regular_teams = _parse_standings(standings)
        preseason_teams = _parse_standings(preseason)
        return {
            "standings": regular_teams,
            "preseason_standings": preseason_teams,
            "global_standings": _sort_global(regular_teams),
            "games": _parse_games(scoreboard, 2),
            "preseason_games": _parse_games(scoreboard, 1),
        }

    async def _async_get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        async with self._session.get(url, params=params, timeout=30) as response:
            response.raise_for_status()
            return await response.json()


def _parse_standings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    teams = []
    for conference in payload.get("children", []):
        for division in conference.get("children", []):
            for entry in division.get("standings", {}).get("entries", []):
                stats = {stat.get("name"): stat for stat in entry.get("stats", [])}
                teams.append(
                    {
                        "conference": conference.get("name", ""),
                        "division": division.get("name", ""),
                        "team": entry.get("team", {}).get("displayName", ""),
                        "abbreviation": entry.get("team", {}).get("abbreviation", ""),
                        "logo": entry.get("team", {}).get("logos", [{}])[0].get("href", ""),
                        "wins": _stat_number(stats, "wins"),
                        "losses": _stat_number(stats, "losses"),
                        "pct": _stat_float(stats, "winPercent"),
                    }
                )
    return teams


def _sort_global(teams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_teams = sorted(teams, key=lambda team: (team["wins"], team["pct"], -team["losses"]), reverse=True)
    return [team | {"rank": rank} for rank, team in enumerate(sorted_teams, 1)]


def _parse_games(payload: dict[str, Any], season_type: int) -> list[dict[str, Any]]:
    games = []
    for event in payload.get("events", []):
        if event.get("season", {}).get("type") != season_type:
            continue
        competition = event.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])
        home = next((item for item in competitors if item.get("homeAway") == "home"), {})
        away = next((item for item in competitors if item.get("homeAway") == "away"), {})
        games.append(
            {
                "date": _format_date(event.get("date")),
                "away_team": away.get("team", {}).get("abbreviation", ""),
                "away_logo": away.get("team", {}).get("logo", ""),
                "away_score": away.get("score", ""),
                "home_team": home.get("team", {}).get("abbreviation", ""),
                "home_logo": home.get("team", {}).get("logo", ""),
                "home_score": home.get("score", ""),
                "status": competition.get("status", {}).get("type", {}).get("shortDetail", ""),
                "venue": competition.get("venue", {}).get("fullName", ""),
            }
        )
    return games


def _stat_number(stats: dict[str, Any], name: str) -> int:
    return int(float(stats.get(name, {}).get("value", 0)))


def _stat_float(stats: dict[str, Any], name: str) -> float:
    return float(stats.get(name, {}).get("value", 0))


def _format_date(value: str | None) -> str:
    if not value:
        return ""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%a %d %b, %H:%M")