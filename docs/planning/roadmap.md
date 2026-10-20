# Roadmap and priorities

Build in thin, playable slices: the attribute database first, then the codebase foundation, then one game you can play end to end, then a full season. Everything off that path waits.

## Product vision

A super-lite Football Manager for the NBA: FM-style decisions (rotations, fitness, tactics, matchup prep) in a season you can finish in an evening, not 40 hours. No finances, scouting, contracts, or youth development at launch.

Reference: [82-0 repo](https://github.com/DanielTomaro13/nba-82-0). Worth borrowing:

- **Layout:** a data pipeline, a game engine and simulator library, and a web app in one repo.
- **Data flow:** datasets generated into JSON that the pages read at build time.
- **Stack:** Next.js + TypeScript + React, exported as a static site, so no backend is needed to start.
- **Optional backend:** a Cloudflare Worker only for the leaderboard.
- It's MIT licensed: keep the copyright and license notice for any code you copy.

## Phases

| Phase | Goal | Scope | Done when |
| --- | --- | --- | --- |
| **0. Attribute database** | Ratings for every current player | Everything in the [Stats scraping plan](stats-scraping-plan.md): source evaluation, fetch from one owner per data type, cache, normalize, composites, 2K calibration regression, rate, export | `players.json` and `teams.json` for last season pass the validation checks; regression held-out error about 3 points or less; firewall test green |
| **1. Codebase foundation** | Repo and workflow ready | Repo layout, CI, engine package skeleton, first ADRs, backlog | CI green on a first engine test; Phase 2–3 stories written |
| **2. Walking skeleton** | Play one game end to end | Possession sim from One-game sim v1 (shots, fouls, rebounds, turnovers), box score, minimal UI: pick team, set lineup, sim | One game played in the browser with a believable box score |
| **3. Playable season (v0.1)** | Coach a full regular season | Schedule, standings, league sim, energy, simple injuries, rest, lineups, minutes, 2–3 tactics per side | Someone else plays a full season without help |
| **4. Tactics depth** | Decisions that matter | All modes, fit effects, spacing, post-game feedback, calibration in CI | A/B sims show each tactic moves outcomes; bad fits measurably hurt |
| **5. Postseason and AI** | Win a title | Play-in, playoffs, AI coach counters, fouls, late-game logic | A season plays through the Finals |
| **6. Depth** | Long-term hooks | Rust and chemistry, archetypes, morale, trades, sharing, leaderboard, difficulty | Ordered by playtest feedback |

## Feature priority for v0.1

| Priority | Features |
| --- | --- |
| **Must** | Ratings database with fallback ratings for low-data players, possession sim, box score, starting lineup, rest, minutes, energy, basic injuries, schedule and standings, league sim, 2–3 offensive and defensive tactics, save state as JSON |
| **Should (v0.2–0.3)** | All tactics, tactic-fit feedback, play-in and playoffs, fouls and foul trouble, AI counters, bot-coach strategy tests |
| **Could** | Rust and chemistry, detailed late-game logic, archetypes, home court and travel, variance tuning, shareable result card |
| **Won't (for now)** | Trades, free agency, finances, morale, multi-season careers, in-game quarter control |

## Agile workflow

- **Backlog:** a GitHub Projects board. Phases are epics; work items are user stories with acceptance criteria.
  - Example: *As a coach, I can rest a player for one game so he recovers energy.* Acceptance: he gets a DNP, energy recovers at the rest rate, the game still sims normally.
- **Sprints:** 2 weeks, one sprint goal, ending in a demoable build. Review = play the build; retro = three lines in `docs/retros/`.
- **Vertical slices:** each story goes through data, engine, and UI as needed. Avoid building the whole engine before any UI.
- **Definition of Done:** PR merged to `main` with a self-review checklist, unit tests, CI green, preview deployed, docs or ADR updated.
- **Branching:** short-lived feature branches, PRs, conventional commits, semantic version tags per release.
- **Testing:** engine unit tests with a seeded RNG; from Phase 4, statistical regression tests in CI (1,000 sims, league averages within tolerance).
- **ADRs:** record major decisions in `docs/adr/` (engine language, league sim approach, hosting).
- **Estimation:** T-shirt sizes per story; track completed stories per sprint to forecast.

## Learning approach: coding Lego

The goal is to understand every piece, not just ship. Each brick is a small module with one job, a typed interface, and its own tests. You build one brick, prove it works, then snap it onto the last one.

**Rules for every brick**

1. **One new concept per brick.** If a brick needs two things you don't know yet, split it.
2. **Test first.** Write the test that describes what the brick should do, then make it pass. The test defines the brick's shape.
3. **Write it yourself first.** Use AI for explanations, hints, and code review, not full solutions. Escalate only when stuck: ask for a hint, then a nudge, then an example after about 30 minutes of trying.
4. **Explain-it-back test.** Never merge code you can't explain line by line. If you can't, ask why it works before moving on.
5. **Compare after, not before.** Look at how 82-0 or Basketball GM solved the same problem only after your brick works.
6. **Log it.** One short entry per brick in `docs/learning-log.md`: what you built, what you learned, what confused you.

Add "I can explain it" and a learning-log entry to the Definition of Done. Put the AI rules in a `CLAUDE.md` at the repo root (e.g. "give hints and explanations, not complete implementations, unless asked") so coding assistants follow them.

**Pipeline bricks (Python, Phase 0)**

| Brick | You build | You learn | Proof it works |
| --- | --- | --- | --- |
| P1 | Fetch one endpoint, print a table | HTTP requests, `nba_api`, DataFrames | Prints last season's player stats |
| P2 | Cache wrapper | File I/O, caching, idempotence | Second run makes zero requests |
| P3 | Rate limiter with retries | Backoff, error handling | Test with a fake failing request |
| P4 | Normalize into SQLite | Schemas, joins, primary keys | Row counts and no duplicate IDs |
| P5 | Percentile ratings | Statistics, small-sample shrinkage | Known elite shooters rate highest |
| P5b | Fit rating weights against 2K labels | Z-scores, ridge regression, train/test split by player, leakage | Held-out error about 3 points or less; firewall test passes |
| P6 | JSON export | Serialization, data contracts | Game-side types load it without errors |

**Engine bricks (TypeScript, Phases 1–3)**

| Brick | You build | You learn | Proof it works |
| --- | --- | --- | --- |
| E1 | Seeded RNG and weighted pick | Pure functions, determinism | Same seed gives same output; picks match weights over 10,000 draws |
| E2 | Player and Team types, data loader | TypeScript types, runtime validation (e.g. zod) | Loads `players.json`; bad data fails loudly |
| E3 | Shot resolver: shooter + shot type → make or miss | Probability, unit testing | 40% shooter makes about 40% over many shots |
| E4 | One possession: shooter, shot, rebound, turnover | Composition, small state machines | Each outcome occurs at sensible rates |
| E5 | Game loop and box score | Immutable state, reducers | Box score totals match the final score |
| E6 | Substitutions and energy | Time-based state updates | Tired players' efficiency drops; subs happen |
| E7 | Schedule and standings | Data structures, sorting, tiebreakers | 82 games per team; standings sum correctly |
| E8 | Save and load | Serialization, versioned formats | Reloaded season continues identically |

**UI bricks (React, Phases 2–3)**

| Brick | You build | You learn | Proof it works |
| --- | --- | --- | --- |
| U1 | Box score table | Components, props | Renders a saved `GameResult` |
| U2 | Lineup picker | State, events, controlled inputs | Can't start a game with an invalid lineup |
| U3 | Game plan screen | Composing components, lifting state | Plan changes reach the engine |
| U4 | Season view | Routing, derived data | Standings update after each sim |

Each brick is one user story on the board, so the Agile process and the learning path are the same list.

## Built to sell later

- **Licensing is the biggest risk.** Real NBA team names, logos, and player names or likenesses generally need licenses (league and players' association) for a commercial product. 82-0 uses a non-affiliation disclaimer, which works for a free project but isn't a license. Get legal advice before charging money.
- **Keep data swappable:** the engine reads a ratings file and doesn't care whether players are real, so it can ship with fictional players if licensing isn't viable.
- **Clean IP:** write your own code; keep MIT notices on anything copied from 82-0; ship only derived ratings, not raw scraped stats.
- **Engine as a package** with a documented API, so it can be reused or licensed separately (other leagues, other sports).

## Codebase plan (Phase 1)

```
nba-coach-sim/
  pipeline/            # Python scraper -> data JSON (see Stats scraping plan)
  packages/engine/     # TypeScript sim library: pure, seeded, no UI or I/O
  packages/data/       # generated players.json, teams.json + TS types
  web/                 # Next.js + React UI, static export
  tools/               # calibration harness, bot coaches
  docs/adr/            # architecture decision records
  .github/workflows/   # CI: lint, test, build, deploy preview
```

First ADRs to write:

1. **Engine in TypeScript** rather than C#: matches 82-0, runs client-side, and shares types with the UI.
2. **Static hosting first** (GitHub Pages or Vercel); add a backend only when cloud saves or leaderboards need it.
3. **Python for the pipeline only**, communicating with the game through generated JSON.

## First seven sprints

| Sprint | Goal |
| --- | --- |
| 1 | Fetch and cache base and advanced stats, rosters, and bio data from `nba_api` |
| 2 | Shot zones, shot type, tracking and matchups; PBP Stats lineups; ESPN injuries; normalize into SQLite |
| 3 | 2K labels for 3–5 past editions with matching prior-season stats; z-score both sides and pair each 2K attribute with its stats |
| 4 | Ridge regression, EPM vs. DARKO test, firewall test, fallback ratings, JSON export, validation |
| 5 | Repo skeleton, CI, engine types, single-possession sim with the v1 weights and tests |
| 6 | Full-game sim, box score, calibration harness v1 |
| 7 | Minimal UI: pick a team, set a lineup, sim a game — walking skeleton demo |
