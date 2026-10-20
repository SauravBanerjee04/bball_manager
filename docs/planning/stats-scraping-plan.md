# Stats scraping plan

Pull player stats once per season from public sources, cache the raw responses, and turn them into the `players.json` ratings file the sim engine loads.

## Sources

NBA Stats (through `nba_api`) stays the base. Four other sources each add one thing it lacks. The rest serve as a training label or a validation check, or aren't used. Rows are sorted by how much each source feeds the ratings. Every source we use is free: no subscriptions.

| Source | What it gives | Accuracy evidence | Useful for per-skill ratings? | Access and cost | Our use |
| --- | --- | --- | --- | --- | --- |
| [NBA Stats via nba\_api](https://github.com/swar/nba_api) | Box, advanced, shot zones, tracking (catch-and-shoot, pull-ups, drives, post-ups, passing), defense tracking, matchups, hustle, bio, rosters, game logs | Official league counts; defensive tracking is noisy | High: the only source with tracking data | Free; unofficial endpoints change without notice; MIT client | Primary input |
| [PBP Stats](https://github.com/dblackrun/pbpstats) | Play-by-play parsed into possessions, lineups on the floor for every event, assisted vs. unassisted by zone | Derived from NBA.com play-by-play, so same accuracy | High for self-creation and lineup chemistry | Free site and Python package | Input: possessions and lineups |
| [Basketball-Reference](https://www.sports-reference.com/bot-traffic.html) | Box, per-100, advanced, BPM / VORP / WS, draft slot, college | BPM: RMSE 2.71 in the [D&T test](https://dunksandthrees.com/blog/metric-comparison) | Medium: box score only | Free; max 20 requests per minute | Input: BPM and draft data |
| [ESPN](https://dev.to/zuplo/unlocking-espns-hidden-api-a-developers-guide-1pp7) (site.api.espn.com) | Injury reports, transactions, schedules, game logs | Factual records, not ratings | Low for skills; high for injury history | Free; undocumented, may change without notice | Input: injury vs. rest for missed games |
| [Dunks & Threes EPM](https://dunksandthrees.com/epm) | Overall impact split into offense and defense | Best in the only public head-to-head test: RMSE 2.48 ([D&T, June 2020](https://dunksandthrees.com/blog/metric-comparison); run by EPM's author) | Medium: one number per side | Free table only; we don't pay for the subscription | Candidate impact feature, tested against DARKO |
| [DARKO](https://darko.app/) | Daily predictive impact (DPM) with offense, defense and box parts; per-100 projections | Built to predict; no published head-to-head numbers found | Medium | Free, CSV download | Candidate impact feature, tested against EPM |
| [BBall Index](https://www.bball-index.com/lebron-introduction/) | LEBRON impact, offensive roles, skill talent grades | None published on its intro page; LEBRON placed 17th of 18 in the 2023-24 [APBR win contest](https://www.apbr.org/metrics/viewtopic.php?p=43314) (forum result) | High: closest public match to per-skill attributes | LEBRON app free; talent grades paid | Not used: its useful grades need a subscription |
| [Kaggle NBA Database](https://www.kaggle.com/datasets/wyattowalsh/basketball) | SQLite of 65,000+ games since 1946-47, 13M+ play-by-play rows, updated daily | Same NBA.com data | Low for ratings; high for calibration | Free, CC BY-SA 4.0, about 4.7 GB | Historical games for calibration |
| NBA 2K ratings | 0–99 overall and attribute ratings | Expert-set by 2K, partly stat-based | Training label | Proprietary; 2kratings.com blocked my automated fetch, so collect by hand | Label only, never an input |
| [SportsDataIO](https://sportsapis.dev/apis/sportsdata-io) | Injuries, rosters, schedules, lineups | Commercial feed | Low | Free trial uses scrambled data; real data, delayed a day, costs $99–149/mo | Not used: paid |
| [Sportradar](https://developer.sportradar.com/getting-started/docs/registration) | Licensed game stats and play-by-play feeds | Commercial feed | Low beyond nba\_api | Real-data trial with limited requests; B2B, quoted pricing | Not used: paid |

Also checked and not used: RAPTOR (RMSE 2.63, but it stopped updating when FiveThirtyEight shut down in 2023), [nbarapm.com](https://nbarapm.com/) (it collects the metrics above), and Cleaning the Glass (paid, and it covers the same data as PBP Stats).

> Chart: RMSE by metric from the Dunks & Threes comparison (June 2020): EPM 2.48, RPM 2.60, RAPTOR 2.63, BPM 2.71, PREDATOR 2.73, PIPM 2.78, RAPM 2.80, WS/48 2.85, aPER 3.12, PER 3.20. Drawn in the [planning doc](https://claude.ai/code/artifact/e0c7f730-5198-4f53-a3d5-70104ee8963e).

The spread is small: the top seven metrics fall within 0.32 points of each other. That's why the regression tests EPM against DARKO (which wasn't in this test) on our own data instead of trusting this ranking. [Source](https://dunksandthrees.com/blog/metric-comparison).

## One owner per data type

Each rating input comes from exactly one source. Other sources may cross-check it during validation, but they are never blended into the rating. The NBA Stats website and `nba_api` are one source: `nba_api` is a Python client for stats.nba.com.

| Data | Owner | Why this one |
| --- | --- | --- |
| Shot zones, catch-and-shoot, pull-ups, drives, post-ups, passing, hustle, rim and perimeter defense tracking, matchups, bio, rosters, game logs, league team averages | NBA Stats via `nba_api` | Only source with tracking data; league-wide tables keep requests low |
| Possessions, lineups on the floor, on/off, assisted vs. unassisted makes by zone, putbacks, fouls drawn per possession | PBP Stats | Possessions and lineups come already parsed; feeds self-creation, chemistry and lineup calibration |
| BPM, draft slot, college, Basketball-Reference ID map | Basketball-Reference | Box-only impact feature for the regression; draft data for the rookie fallback |
| Injury reports, injury vs. rest reason for each missed game, transactions | ESPN | Separates rest from injury for injury proneness and rust calibration |
| Overall impact feature | EPM **or** DARKO, one only | Both come from the same RAPM family and are highly correlated. Fit the regression with each, keep the one with lower held-out error, drop the other |
| Past seasons' box scores and play-by-play | Kaggle NBA Database | Same NBA.com data, already in bulk, so calibration costs zero requests. Past seasons only; the current season comes from `nba_api` |
| Roles and archetypes check | Manual review | No subscriptions, so no BBall Index: check our k-means archetypes by eye against well-known players |
| Training label | NBA 2K ratings | Label only, behind the firewall in the 2K calibration regression section |

The raw data is for building the game's ratings, not for redistribution. Before publishing the game, check each site's data-use terms and ship only derived 0–100 ratings, not raw stat tables.

## Data to collect

Each rating group in the main plan maps to specific stats and one primary endpoint.

| Rating group | Stats needed | Source and endpoint | B-Ref cross-check (validation only) |
| --- | --- | --- | --- |
| Scoring by zone | FGM/FGA for restricted area, paint, midrange, corner 3, above-break 3 | `LeagueDashPlayerShotLocations` (By Zone) | Shooting (by distance) |
| Shot type | Catch-and-shoot and pull-up FGM/FGA, 3PM/3PA | `LeagueDashPtStats` (CatchShoot, PullUpShot) | Shooting (% assisted, rough proxy) |
| Self-creation | % of makes unassisted | PBP Stats (assisted / unassisted makes by zone) | Shooting (% assisted) |
| Free throws | FTM, FTA | `LeagueDashPlayerStats` (Base) | Per game |
| Tendencies | Usage %, shot mix by zone, drives, post-ups | `LeagueDashPlayerStats` (Advanced), shot locations, `LeagueDashPtStats` (Drives, PostTouch) | Advanced, shooting |
| Playmaking | AST%, TOV%, assists, potential assists | `LeagueDashPlayerStats` (Advanced), `LeagueDashPtStats` (Passing) | Advanced |
| Rebounding | ORB%, DRB% | `LeagueDashPlayerStats` (Advanced) | Advanced |
| Defense | STL%, BLK%, defensive rating, opponent FG% within 6 ft | `LeagueDashPlayerStats` (Advanced, Defense), `LeagueDashPtDefend` | Advanced (DBPM) |
| Perimeter defense and versatility | Opponent FG% when guarded vs. usual, positions guarded, partial possessions | `LeagueSeasonMatchups` | None |
| Hustle | Deflections, contested shots | `LeagueHustleStatsPlayer` | None |
| Physical | Height, weight, age, minutes, games played | `LeagueDashPlayerBioStats`, `LeagueDashPlayerStats` | Per game, roster pages |
| Injury proneness | Games missed over the last 3 seasons | `LeagueDashPlayerStats` (GP) for 3 seasons; ESPN injury reports for the injury vs. rest reason | Per game (G) |
| Rosters | Team, player ID, position | `CommonTeamRoster` per team | Team roster pages |

Also pull league averages (pace, eFG%, 3PA rate, TOV%, ORB%) from `LeagueDashTeamStats` for calibration. Endpoint names are from `nba_api`; confirm each in its docs before coding, since NBA.com changes them.

## Scraper design

A Python CLI that fetches each table once, caches the raw response to disk, and never re-fetches what it already has.

```
scraper/
  fetch_nba.py       # nba_api calls, one function per endpoint (primary)
  fetch_pbpstats.py  # possessions, lineups, assisted/unassisted by zone
  fetch_bref.py      # BPM, draft slot, college, ID map
  fetch_espn.py      # injury reports, injury vs. rest per missed game
  fetch_impact.py    # EPM or DARKO table (one, chosen by the regression test)
  load_kaggle.py     # past seasons from the Kaggle SQLite, for calibration
  cache.py           # read/write raw files under data/raw/{source}/{season}/
  normalize.py       # raw -> clean tables keyed by NBA player ID
  fit_weights.py     # the only reader of data/labels/2k/ -> rating_weights.yaml
  rate.py            # clean tables + weights -> 0-100 ratings (no 2K input)
  export.py          # write players.json, teams.json
  cli.py             # python cli.py --season 2025-26 --steps fetch,normalize,fit,rate,export
```

Rules:

- **Cache first:** every request checks `data/raw/` before calling the network. Re-running the pipeline costs zero requests.
- **Rate limit:** NBA.com, 1 request every 2–3 seconds with jitter. Basketball-Reference, 1 request every 4 seconds (15 per minute, under the 20 limit).
- **Headers and timeouts:** pass a browser User-Agent and Referer to `nba_api`; 30-second timeout.
- **Retries:** exponential backoff (5s, 15s, 45s) on timeouts and 5xx; on a 429, stop the run instead of retrying.
- **Run locally:** run from a home connection, not a cloud VM or CI, since cloud IPs are more likely to be blocked (approximate; from community reports).
- **Parsing B-Ref:** use `pandas.read_html`; some tables sit inside HTML comments, so strip comment markers before parsing ([ref](https://apify.com/lulzasaur/basketball-reference-scraper)).

## Storage schema

Three layers: raw responses as files, clean tables in SQLite, and the shipped JSON.

| Layer | Location | Contents |
| --- | --- | --- |
| Raw | `data/raw/{source}/{season}/{endpoint}.json` | Untouched API responses or HTML, for replays and debugging |
| Clean | `data/stats.db` (SQLite) | `players`, `player_season_stats`, `player_shot_zones`, `player_tracking`, `team_rosters`, `league_averages` |
| Shipped | `game/data/players.json`, `teams.json` | Ratings only, keyed by NBA player ID |

Use NBA.com player IDs as the primary key. Keep a `player_id_map` table to join Basketball-Reference slugs (e.g. `jamesle01`) when the fallback is used. SQLite keeps it simple; the same tables can move to Supabase or Postgres later if the Substack analysis needs them.

## Ratings transform

Convert each stat to a 0–100 rating by league percentile, after shrinking small samples toward league average.

1. **Filter:** players with at least 10 games played go in; below that, use position-average ratings.
2. **Shrink small samples:** blend each rate stat with league average by attempts, so a 4-for-5 three-point shooter isn't rated elite.

```latex
adjusted = \frac{makes + k \times leagueRate}{attempts + k}
```

Start with k ≈ 100 for three-point %, lower for higher-volume stats; tune by eye.

3. **Normalize:** convert each adjusted stat to a z-score within the season. The 2K calibration regression below maps z-scores to 0–99, capped at 25–99. An attribute with no 2K counterpart uses its season percentile instead.
4. **Invert where lower is better:** turnover rate, foul rate.
5. **Composite ratings:** perimeter defense, interior defense, and basketball IQ combine several stats with weights stored in `rating_weights.yaml`.
6. **Missing data:** if a tracking stat is missing, fall back to position average and flag it in the output.

## 2K calibration regression

A regression learns how much each stat should count by matching our normalized stats to NBA 2K's normalized attribute ratings, then scores every player from stats alone. 2K ratings teach the weights. **They are never a player's rating.**

- **Why:** percentiles alone leave the weighting of each component as a guess (for example, how much rim protection vs. blocks counts toward interior defense). 2K's ratings are expert judgment on a scale players know, which makes them a reasonable target for learning those weights.
- **Labels:** 2K launch ratings for each attribute in the table below, plus overall, for 3–5 past editions. Enter them by hand into `data/labels/2k/{edition}.csv`.
- **Matching:** pair each edition with the **previous** season's stats, because launch ratings are set from last season. Using same-season stats would leak information the game didn't have.
- **Normalize both sides to z-scores:**
  - Our stats: shrink small samples (formula above), flip stats where lower is better, then z = (stat − season mean) ÷ season standard deviation, among qualified players in that season.
  - 2K ratings: the same z-score for each attribute within its edition. 2K's scale drifts between editions, and this keeps that drift from looking like a change in players.
  - Both sides now read as standard deviations above or below average, so the fit compares like with like.
- **Model:** ridge regression, one per 2K attribute. It predicts that attribute's 2K z-score from the z-scores of its matching stats (table below), plus age, minutes and height. Because every input is on the same scale, each weight reads directly: a weight of 0.6 on 3P% means one standard deviation of 3P% moves the predicted rating 0.6 standard deviations. Overall uses the attribute predictions plus the one impact metric (EPM or DARKO) and BPM. Try gradient boosting only if ridge's held-out error is clearly worse.
- **Back to 0–99:** rating = the attribute's 2K mean + predicted z × its 2K standard deviation, both averaged across editions, capped at 25–99. Ratings then land on a scale that feels like 2K's, even though no player's 2K value is used.
- **Split by player:** train and test sets never share a player, so the model can't memorize names.
- **Success:** held-out mean absolute error about 3 rating points or less on overall; top-20 lists per attribute look right; review residuals for systematic bias. For example, 2K may rate stars above their stats. Keeping or dropping that bias is a deliberate design choice.

**2K attribute to our stat**

| 2K attribute | Our normalized stat | Owner |
| --- | --- | --- |
| Close Shot | FG% in the paint outside the restricted area | NBA Stats via `nba_api` |
| Driving Layup | FG% on drives | NBA Stats via `nba_api` |
| Mid-Range Shot | Midrange FG% | NBA Stats via `nba_api` |
| Three-Point Shot | 3P%, split catch-and-shoot and pull-up | NBA Stats via `nba_api` |
| Free Throw | FT% | NBA Stats via `nba_api` |
| Post Control | Points per post-up | NBA Stats via `nba_api` |
| Draw Foul | Shooting fouls drawn per 100 possessions | PBP Stats |
| Ball Handle | Unassisted share of makes, drive rate, TOV% (flipped) | PBP Stats, NBA Stats |
| Pass Accuracy, Pass Vision | AST%, potential assists | NBA Stats via `nba_api` |
| Interior Defense | Opponent FG% within 6 ft vs. expected (flipped) | NBA Stats via `nba_api` |
| Perimeter Defense | Matchup opponent FG% vs. their usual (flipped) | NBA Stats via `nba_api` |
| Steal | STL% | NBA Stats via `nba_api` |
| Block | BLK% | NBA Stats via `nba_api` |
| Offensive Rebound | ORB% | NBA Stats via `nba_api` |
| Defensive Rebound | DRB% | NBA Stats via `nba_api` |
| Stamina | Minutes per game | NBA Stats via `nba_api` |
| Speed | Average speed from tracking | NBA Stats via `nba_api` |
| Strength, Vertical | Weight, height (weak stand-ins) | NBA Stats via `nba_api` |
| Overall Durability | Games missed to injury over 3 seasons | ESPN |

Attribute names are from recent 2K editions; confirm them against each edition's list. Speed, Strength and Vertical have only weak public stand-ins, so expect larger errors there.

**The firewall:**

1. 2K numbers live only in `data/labels/` and are read only by `fit_weights.py`.
2. The fit writes learned weights to `rating_weights.yaml`. The ratings step reads only stats, those weights, and each attribute's 2K mean and standard deviation (two numbers per attribute, never any player's value).
3. A test fails the build if any 2K column, or any value copied from a label file, reaches `players.json`.
4. 2K ratings are for internal fitting only. They are never committed to a public repo or redistributed.

## Validation and refresh cadence

Check the data at three points; refresh once per season plus optionally at the trade deadline.

- **After fetch:** row counts per endpoint (about 450–600 players per season; 2025-26 had 582), no duplicate player IDs.
- **After normalize:** spot-check 5 known players against the live NBA.com and Basketball-Reference pages.
- **After rating:** eyeball the top 10 for each rating; known elite shooters, rebounders, and rim protectors should show up.
- **In the sim:** the calibration harness from the main plan is the final test.
- **Refresh:** full pull after the regular season ends; an optional mid-season pull for roster changes. Cached raw files mean only new data is fetched.

## Build tasks

- [ ] Set up the `scraper/` project with `nba_api`, `pandas`, `requests`, and a pinned `requirements.txt`
- [ ] Write `cache.py` and a rate-limited request wrapper
- [ ] Fetch base and advanced stats for last season; confirm endpoint names
- [ ] Fetch shot locations by zone and tracking stats (drives, post-ups, rim defense)
- [ ] Fetch rosters and bio stats
- [ ] Fetch PBP Stats possessions and lineups; fetch ESPN injury history
- [ ] Load past seasons from the Kaggle database for the calibration harness
- [ ] Pull EPM and DARKO tables for the regression test
- [ ] Enter 2K launch ratings for 3–5 editions into `data/labels/2k/`
- [ ] Write `fit_weights.py` (ridge per attribute group, split by player) and report held-out error
- [ ] Add the firewall test: no 2K value can reach `players.json`
- [ ] Normalize into SQLite tables
- [ ] Write the ratings transform and `rating_weights.yaml`
- [ ] Export `players.json` and `teams.json`
- [ ] Run validation checks
- [ ] Use Basketball-Reference only as a cross-check; switch an input's owner only if its NBA.com endpoint breaks
