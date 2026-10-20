from scraper.cache import cache_path, get_or_fetch


def test_second_call_makes_zero_requests(tmp_path):
    calls = []

    def fetch():
        calls.append(1)
        return {"rows": [1, 2, 3]}

    first = get_or_fetch("nba", "2025-26", "table", fetch, root=tmp_path)
    second = get_or_fetch("nba", "2025-26", "table", fetch, root=tmp_path)

    assert first == second == {"rows": [1, 2, 3]}
    assert len(calls) == 1


def test_file_lands_under_source_and_season(tmp_path):
    get_or_fetch("bref", "2024-25", "advanced", lambda: {}, root=tmp_path)
    assert cache_path("bref", "2024-25", "advanced", tmp_path).exists()


def test_failed_fetch_leaves_nothing_cached(tmp_path):
    def broken():
        raise RuntimeError("network down")

    try:
        get_or_fetch("nba", "2025-26", "table", broken, root=tmp_path)
    except RuntimeError:
        pass
    assert not cache_path("nba", "2025-26", "table", tmp_path).exists()
