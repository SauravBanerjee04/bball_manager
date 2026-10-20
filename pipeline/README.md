# Stats pipeline

Fetches public NBA stats, caches the raw responses, and (later) turns them into `players.json`.
The plan lives in [docs/planning/stats-scraping-plan.md](../docs/planning/stats-scraping-plan.md).

## Setup

```sh
cd pipeline
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run

```sh
.venv/bin/python -m scraper.cli --season 2025-26 --steps fetch
```

Raw responses are cached under `data/raw/{source}/{season}/` at the repo root, so a second run makes no requests.
Run it from a home connection; stats.nba.com often blocks cloud IPs.

## Test

```sh
.venv/bin/pytest
```

Tests use a fake server, so they never touch the network.
