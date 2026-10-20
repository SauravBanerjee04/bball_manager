"""Run pipeline steps from the command line.

    python -m scraper.cli --season 2021-22,2022-23,2023-24,2024-25,2025-26 --steps fetch
    python -m scraper.cli --season 2026-27 --steps rosters

fetch pulls every league-wide table for each season; rosters pulls all 30 team rosters.
normalize, fit, rate and export come next.
"""

import argparse
import sys

from . import fetch_nba
from .throttle import RateLimitedError

STEPS = ("fetch", "rosters", "normalize", "fit", "rate", "export")

# After-fetch checks from the Stats scraping plan.
EXPECTED_PLAYERS = range(450, 651)  # 2021-22 had 605 (COVID hardship signings), 2025-26 had 582


def fetch(season):
    print(f"== {season}")
    for name, endpoint in fetch_nba.season_tables(season).items():
        df = fetch_nba.to_frame(fetch_nba.fetch(season, name, endpoint))
        print(f"  {name}: {len(df)} rows, {len(df.columns)} columns")

        if name == "leaguedashplayerstats_base" and len(df) not in EXPECTED_PLAYERS:
            print(f"    WARNING: expected {EXPECTED_PLAYERS.start}-{EXPECTED_PLAYERS.stop - 1} players")
        if "PLAYER_ID" in df.columns and df["PLAYER_ID"].duplicated().any():
            print(f"    WARNING: {df['PLAYER_ID'].duplicated().sum()} duplicate player IDs")
        if df.empty:
            print("    WARNING: empty table")


def rosters(season):
    print(f"== {season} rosters")
    sizes = {team: len(fetch_nba.to_frame(raw)) for team, raw in fetch_nba.team_rosters(season).items()}
    print("  " + ", ".join(f"{team} {n}" for team, n in sizes.items()))
    print(f"  {sum(sizes.values())} players on {len(sizes)} teams")


def main(argv=None):
    parser = argparse.ArgumentParser(description="NBA stats pipeline")
    parser.add_argument("--season", required=True, help='One or more season labels, e.g. "2024-25,2025-26"')
    parser.add_argument("--steps", default="fetch", help=f"Comma-separated, from: {','.join(STEPS)}")
    args = parser.parse_args(argv)

    steps = args.steps.split(",")
    unknown = [s for s in steps if s not in STEPS]
    if unknown:
        parser.error(f"unknown steps: {', '.join(unknown)}")

    runners = {"fetch": fetch, "rosters": rosters}
    try:
        for step in steps:
            if step not in runners:
                print(f"{step}: not built yet")
                continue
            for season in args.season.split(","):
                runners[step](season)
    except RateLimitedError as e:
        print(f"Stopped: {e}. Wait before running again; cached tables are kept.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
