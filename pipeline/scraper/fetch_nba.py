"""NBA Stats (stats.nba.com) via nba_api: one entry per table we need.

Each fetch returns the raw JSON response as a dict and caches it, so the
normalize step can be re-run without touching the network.
"""

import pandas as pd
import requests
from nba_api.stats import endpoints as E
from nba_api.stats.library.http import NBAStatsHTTP
from nba_api.stats.static import teams as static_teams

from . import cache
from .throttle import RateLimitedError, RetryableError, Throttle, with_retries

SOURCE = "nba"
TIMEOUT = 30
RETRY_DELAYS = (5, 15, 45)
CACHE_ROOT = cache.DEFAULT_ROOT

_throttle = Throttle(min_interval=2.0, jitter=1.0)

# Tracking tables from LeagueDashPtStats, named after their PtMeasureType.
PT_MEASURES = ("CatchShoot", "PullUpShot", "Drives", "PostTouch", "Passing", "SpeedDistance")


def season_tables(season):
    """Every league-wide table we pull for one season: {cache name: prepared endpoint}.

    Endpoints are built with get_request=False, so nothing is sent until _get runs.
    """
    tables = {}
    for measure in ("Base", "Advanced", "Defense"):
        tables[f"leaguedashplayerstats_{measure.lower()}"] = E.LeagueDashPlayerStats(
            season=season, measure_type_detailed_defense=measure, per_mode_detailed="Totals", get_request=False
        )
    tables["shotlocations_byzone"] = E.LeagueDashPlayerShotLocations(
        season=season, distance_range="By Zone", per_mode_detailed="Totals", get_request=False
    )
    for measure in PT_MEASURES:
        tables[f"pt_{measure.lower()}"] = E.LeagueDashPtStats(
            season=season, player_or_team="Player", pt_measure_type=measure, per_mode_simple="Totals", get_request=False
        )
    for name, category in (("ptdefend_overall", "Overall"), ("ptdefend_lt6ft", "Less Than 6Ft")):
        tables[name] = E.LeagueDashPtDefend(
            season=season, defense_category=category, per_mode_simple="Totals", get_request=False
        )
    tables["matchups"] = E.LeagueSeasonMatchups(season=season, per_mode_simple="Totals", get_request=False)
    tables["hustle"] = E.LeagueHustleStatsPlayer(season=season, per_mode_time="Totals", get_request=False)
    tables["bio"] = E.LeagueDashPlayerBioStats(season=season, per_mode_simple="Totals", get_request=False)
    for measure in ("Base", "Advanced"):
        tables[f"team_{measure.lower()}"] = E.LeagueDashTeamStats(
            season=season, measure_type_detailed_defense=measure, per_mode_detailed="Totals", get_request=False
        )
    return tables


def _get(endpoint):
    """Send one prepared nba_api endpoint request with throttling and retries; return its JSON dict."""
    name = endpoint.endpoint

    def attempt():
        _throttle.wait()
        try:
            response = NBAStatsHTTP().send_api_request(
                endpoint=name, parameters=endpoint.parameters, timeout=TIMEOUT
            )
        except (requests.Timeout, requests.ConnectionError) as e:
            raise RetryableError(f"{name}: {e}") from e

        # nba_api never raises on HTTP errors and has no public getter for the status code.
        status = response._status_code
        if status == 429:
            raise RateLimitedError(f"{name}: HTTP 429, stopping the run")
        if status >= 500 or not response.valid_json():
            raise RetryableError(f"{name}: HTTP {status}")
        if status >= 400:
            # Bad parameters or a removed endpoint: retrying won't help.
            raise RuntimeError(f"{name}: HTTP {status} for {response.get_url()}")
        return response.get_dict()

    return with_retries(attempt, delays=RETRY_DELAYS)


def fetch(season, name, endpoint):
    """Fetch one table through the cache."""
    return cache.get_or_fetch(SOURCE, season, name, lambda: _get(endpoint), root=CACHE_ROOT)


def league_player_stats(season, measure_type):
    """Season totals for every player, for one measure type such as "Base" or "Advanced"."""
    endpoint = E.LeagueDashPlayerStats(
        season=season, measure_type_detailed_defense=measure_type, per_mode_detailed="Totals", get_request=False
    )
    return fetch(season, f"leaguedashplayerstats_{measure_type.lower()}", endpoint)


def team_rosters(season):
    """Roster for every team (30 requests). Returns {team abbreviation: raw response}."""
    return {
        team["abbreviation"]: fetch(
            season,
            f"roster_{team['abbreviation'].lower()}",
            E.CommonTeamRoster(team_id=team["id"], season=season, get_request=False),
        )
        for team in static_teams.get_teams()
    }


def _first_result_set(raw):
    # Most endpoints return a list under "resultSets"; shot locations returns a single dict.
    sets = raw.get("resultSets", raw.get("resultSet"))
    return sets[0] if isinstance(sets, list) else sets


def to_frame(raw):
    """Turn the first result set of a raw stats.nba.com response into a DataFrame.

    Shot locations use two header rows (zone, then stat); those columns become "Zone|STAT".
    """
    rs = _first_result_set(raw)
    headers = rs["headers"]
    if headers and isinstance(headers[0], dict):
        zones, stats = headers[0], headers[1]
        zone_names = [z for z in zones["columnNames"] for _ in range(zones["columnSpan"])]
        lead = stats["columnNames"][: zones["columnsToSkip"]]
        rest = stats["columnNames"][zones["columnsToSkip"]:]
        headers = lead + [f"{zone}|{stat}" for zone, stat in zip(zone_names, rest)]
    return pd.DataFrame(rs["rowSet"], columns=headers)
