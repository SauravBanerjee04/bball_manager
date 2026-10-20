import json

import pytest
import requests
from nba_api.library.http import NBAResponse

from scraper import fetch_nba
from scraper.throttle import RateLimitedError, RetryableError, Throttle

PAYLOAD = {
    "resultSets": [
        {
            "name": "LeagueDashPlayerStats",
            "headers": ["PLAYER_ID", "PLAYER_NAME", "PTS"],
            "rowSet": [[1, "A Player", 100], [2, "B Player", 200]],
        }
    ]
}


@pytest.fixture
def fake_server(monkeypatch, tmp_path):
    """Replace the network with a queue of canned responses; no sleeping, cache in tmp_path."""
    queue = []
    sent = []

    def send_api_request(self, endpoint, parameters, timeout=None, **kwargs):
        sent.append((endpoint, dict(parameters)))
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        status, body = item
        return NBAResponse(response=body, status_code=status, url=f"https://stats.nba.com/stats/{endpoint}")

    monkeypatch.setattr("scraper.fetch_nba.NBAStatsHTTP.send_api_request", send_api_request)
    monkeypatch.setattr(fetch_nba, "RETRY_DELAYS", (0, 0, 0))
    monkeypatch.setattr(fetch_nba, "CACHE_ROOT", tmp_path)
    monkeypatch.setattr(fetch_nba, "_throttle", Throttle(min_interval=0))
    return queue, sent


def test_fetches_parses_and_caches(fake_server):
    queue, sent = fake_server
    queue.append((200, json.dumps(PAYLOAD)))

    raw = fetch_nba.league_player_stats("2025-26", "Base")
    again = fetch_nba.league_player_stats("2025-26", "Base")

    assert raw == again == PAYLOAD
    assert len(sent) == 1  # second call served from the cache
    endpoint, params = sent[0]
    assert endpoint == "leaguedashplayerstats"
    assert params["Season"] == "2025-26"
    assert params["MeasureType"] == "Base"
    assert list(fetch_nba.to_frame(raw)["PTS"]) == [100, 200]


def test_retries_server_errors_and_timeouts(fake_server):
    queue, sent = fake_server
    queue.extend([(503, "busy"), requests.Timeout("slow"), (200, json.dumps(PAYLOAD))])

    assert fetch_nba.league_player_stats("2025-26", "Advanced") == PAYLOAD
    assert len(sent) == 3


def test_429_stops_without_retrying(fake_server):
    queue, sent = fake_server
    queue.append((429, "slow down"))

    with pytest.raises(RateLimitedError):
        fetch_nba.league_player_stats("2025-26", "Base")
    assert len(sent) == 1


def test_gives_up_after_four_failed_attempts(fake_server):
    queue, sent = fake_server
    queue.extend([(500, "")] * 4)

    with pytest.raises(RetryableError):
        fetch_nba.league_player_stats("2025-26", "Base")
    assert len(sent) == 4


def test_client_error_is_not_retried(fake_server):
    queue, sent = fake_server
    queue.append((400, json.dumps({"message": "bad parameter"})))

    with pytest.raises(RuntimeError, match="HTTP 400"):
        fetch_nba.league_player_stats("2025-26", "Base")
    assert len(sent) == 1


def test_shot_location_headers_become_zone_and_stat():
    raw = {
        "resultSets": {
            "name": "ShotLocations",
            "headers": [
                {"name": "SHOT_CATEGORY", "columnSpan": 2, "columnsToSkip": 2,
                 "columnNames": ["Restricted Area", "Mid-Range"]},
                {"name": "columns", "columnSpan": 1,
                 "columnNames": ["PLAYER_ID", "PLAYER_NAME", "FGM", "FGA", "FGM", "FGA"]},
            ],
            "rowSet": [[1, "A Player", 5, 8, 2, 6]],
        }
    }
    df = fetch_nba.to_frame(raw)
    assert list(df.columns) == [
        "PLAYER_ID", "PLAYER_NAME",
        "Restricted Area|FGM", "Restricted Area|FGA", "Mid-Range|FGM", "Mid-Range|FGA",
    ]
    assert df.loc[0, "Mid-Range|FGA"] == 6
