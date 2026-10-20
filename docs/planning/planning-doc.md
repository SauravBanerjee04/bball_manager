# NBA Coach Sim — Planning Doc

Oct 15, 2026 · @Saurav Banerjee

## Overview

The player coaches one NBA team through a season, game by game, and tries to win a championship. Inspired by 82-0, but the player makes decisions throughout the season instead of only drafting a lineup.

Positioning: a super-lite Football Manager for the NBA — FM-style decisions in a season you can finish in an evening.

Core pillars:

- **Decisions matter game to game:** lineups, rotations, rest, effort, and tactics all change outcomes.
- **Tradeoffs, not free wins:** every lever has a cost, such as fatigue, injury risk, turnovers, or vulnerability to a counter.
- **Mistakes are possible and visible:** a bad tactic for the roster should hurt, and the game should show the player why.
- **Realistic output:** box scores and season stats should look like real NBA numbers.

## Long-term plan

The ratings come before the game. Three workstreams run in order: rating sources, then 2K-weighted ratings, then a one-game sim. Everything else in this doc builds on that sim.

1. **Rating sources:** one owner per data type, so nothing is counted twice. Details: [Stats scraping plan](stats-scraping-plan.md).
2. **2K-weighted ratings:** a regression learns how much each stat counts by matching past NBA 2K ratings. 2K never becomes a player's rating. Details: [Stats scraping plan](stats-scraping-plan.md).
3. **One-game sim v1:** a possession model where offense and defense shift league rates on the log-odds scale; see [One-game sim v1](#one-game-sim-v1).
4. **Then:** season, tactics, playoffs and AI, and depth, phase by phase in [Roadmap](roadmap.md).

> Diagram: long-term plan, 3 workstreams feeding 7 phases. Drawn in the [planning doc](https://claude.ai/code/artifact/e0c7f730-5198-4f53-a3d5-70104ee8963e); not reproduced in this snapshot.

Workstreams 1 and 2 make up Phase 0; workstream 3 is the core of Phase 2.

## Core gameplay loop

Each game follows the same cycle: review, set the game plan, sim, review results.

1. **Pre-game review:** see the opponent, your roster's energy and injury status, and the schedule (back-to-backs, road trips).
2. **Set the game plan:**
   - Starting lineup
   - Rotation and minutes targets per player
   - Rest players (DNP-rest)
   - Effort level per player or team-wide (low / normal / high)
   - Offensive and defensive tactics, plus situational toggles
3. **Sim the game:** possession-level engine produces a box score and play-by-play.
4. **Post-game review:** box score, shot chart, lineup net ratings, injuries, and tactic-fit feedback.
5. **Advance:** energy recovers based on days off; injured players count down their return.

The season runs 82 games, then playoffs (best-of-7 series). A future option is in-game control at quarter breaks.

## Simulation engine

The engine is a possession-level sim written as a pure, deterministic function, so it can be tested headless and run thousands of times.

```
simGame(homeTeam, awayTeam, homePlan, awayPlan, energyState, seed) -> GameResult
```

`GameResult` holds the final score, box score, play-by-play, minutes played, energy drained, and injuries.

Per possession (about 100 per team):

1. **Check substitutions** against the rotation plan, fouls, and in-game fatigue.
2. **Compute context:** lineup spacing, matchups, current energy, tactic modifiers.
3. **Decide outcome type:** turnover, shot, or foul drawn. Rates come from player ratings plus tactic modifiers.
4. **Pick the shooter** weighted by usage, adjusted by tactic (iso concentrates usage, motion spreads it).
5. **Pick shot type:** rim, paint, midrange, corner three, above-break three. Mix comes from player tendencies, shifted by tactic.
6. **Resolve the shot** using the shooter's zone rating, defender quality, spacing, and fatigue.
7. **Rebound** on a miss: offensive vs. defensive chance based on rebounding ratings, positioning, and shot distance.
8. **Update state:** clock, score, stats, energy, injury roll.

Use a seeded RNG so any game can be replayed exactly for debugging.

### One-game sim v1

Every event uses one rule: start from the offense's real rate and shift it by how much better or worse than average the defense is, on the log-odds scale. Offense counts fully; defense counts partly, because defensive stats are noisier.

Each 0–99 rating is turned back into its z-score, then into a rate: rate = league mean + z × league standard deviation (a finisher one standard deviation above average at the rim gets the league's rim FG% plus one standard deviation). Then:

```latex
\operatorname{logit}(p) = \operatorname{logit}(p_{off}) + w_{def}\,\big[\operatorname{logit}(p_{def}) - \operatorname{logit}(p_{lg})\big] + m
```

p\_off is the offensive player's rate, p\_def the rate this defense allows, p\_lg the league rate, w\_def the defense weight, and m the modifiers (home court, fatigue). Log-odds keeps every probability between 0 and 1, and effects add up cleanly. Example: a 40% three-point shooter against a defense allowing 34% (league 36%), with w\_def = 0.15, makes 39.7%.

**Possession chain:** turnover? → shooting foul? → pick shooter → pick zone → make? → rebound on a miss. Possessions per team = average of the two teams' pace, about 99 (approximate).

| Event | Offense side (weight 1.0) | Defense side | Starting w\_def | League baseline (approx.) |
| --- | --- | --- | --- | --- |
| Turnover | Ball handler's TOV rate | Team forced-turnover rate | 0.50 | 13% of possessions |
| Shooting foul | Shooter's foul-drawn rate | Nearest defender's foul rate | 0.50 | 10% of shots |
| Pick shooter | Usage share among the five on the floor | — | — | — |
| Pick zone | Shooter's shot mix | Fixed in v1; tactics shift it in v2 | — | League shot mix |
| Make at rim | Rim FG% | Rim protector's opponent FG% within 6 ft | 0.50 | 66% |
| Make midrange | Midrange FG% | Perimeter defense | 0.25 | 42% |
| Make three | 3P% for this shot type (catch-and-shoot or pull-up) | Perimeter defense | 0.15 | 36% |
| Offensive rebound | Team ORB% on the floor | Opponent DRB% on the floor | 1.00 | 25% of misses |

Why these weights: rim protection is the best-measured defensive skill, so it gets the largest defense weight. Three-point defense gets the smallest weight, on my assumption that opponent 3P% is mostly noise for an individual defender. Rebounding is weighted equally on both sides because both are measured directly. These are starting guesses, not tuned values.

**Modifiers in v1:** home court of about +1.5 points per 100 possessions, applied as a small bump to make probability. A fatigue penalty applies below 70% in-game energy. Tactics, spacing and chemistry wait for v2.

**Calibration:** sim last season's schedule 1,000 times. Tune the baselines and weights until league pace, eFG%, TOV%, ORB%, free-throw rate and 3PA rate are within about 2% of the real values, and simulated team win% tracks real net rating.

## Player model and ratings

Each player has ratings on a 0–100 scale, derived from real stats and calibrated against league averages.

| Group | Attributes | Derived from |
| --- | --- | --- |
| Scoring | Rim, paint, midrange, corner 3, above-break 3, free throw | FG% by zone, FT% |
| Tendencies | Usage, shot mix by zone, drive rate, post-up rate | Shot distribution, usage rate |
| Playmaking | Passing, ball handling | AST%, TOV% |
| Rebounding | Offensive, defensive | ORB%, DRB% |
| Defense | Perimeter, interior, steals, blocks | STL%, BLK%, defensive metrics |
| Physical | Stamina, speed, size, injury proneness | Minutes history, height, games missed |
| Mental | Basketball IQ | Assist-to-turnover, foul rate (approximate) |

Calibration approach: simulate a full season with real rosters and compare league-wide output (pace, eFG%, 3PA rate, TOV%, ORB%) to actual NBA averages. Tune until each is within a few percent.

## Offensive and defensive ratings by playstyle

No single offensive or defensive number drives the sim. Each player has skill ratings (how good) and tendency ratings (how often); playstyle comes from tendencies, quality from skills. An overall OFF/DEF number is computed only for display.

**Offense**

| Component | Type | Derived from |
| --- | --- | --- |
| Catch-and-shoot shooting | Skill | `LeagueDashPtStats` (CatchShoot) |
| Pull-up shooting | Skill | `LeagueDashPtStats` (PullUpShot) |
| Self-creation | Skill | Share of makes unassisted |
| Passing | Skill | AST%, potential assists |
| Ball security | Skill | TOV% (inverted) |
| Usage, shot mix, drive / post-up / cut rates | Tendency | Advanced stats, shot locations, tracking |

- **Shot type matters, not just zone.** A corner spacer and a pull-up creator can both shoot 40% from three. Forced into Iso mode, the spacer takes more pull-ups and his efficiency drops — the same mechanism as the bigs-in-shooting-mode penalty.
- **Usage-efficiency adjustment:** small skill bump for efficient high-usage scorers, so role players don't out-rate stars as shooters.

**Defense**

| Component | Derived from |
| --- | --- |
| Perimeter (on-ball) | Opponent FG% vs. their usual FG% in matchups (`LeagueSeasonMatchups`), steals, deflections |
| Rim protection | Opponent FG% within 6 ft (`LeagueDashPtDefend`), contest rate, blocks |
| Versatility | Spread of positions guarded, from matchup data; feeds Switch Everything fit |
| Defensive rebounding | DRB% |

- **Shrink harder than offense:** defensive data is noisy and team- and scheme-dependent, so regress strongly toward position average.
- On/off and DBPM are a light tiebreaker only.

**Archetypes**

Cluster players on their tendency vectors (k-means) and label clusters such as Rim-runner, Stretch big, Movement shooter, Point-of-attack defender. Archetypes power UI labels and tactic-fit hints ("Pace & Space wants 4+ shooters; you have 2"), not sim math.

**Sanity checks**

- Same 3P%, different shot types → different catch-and-shoot and pull-up ratings.
- Known rim protectors top rim protection; known switchable wings top versatility.

Endpoint names are from memory; confirm in the `nba_api` docs before coding.

## Fatigue, effort, and injuries

Energy is the shared currency: effort and minutes spend it, rest restores it, and low energy raises both mistakes and injury risk.

**Two energy pools per player:**

- **In-game energy:** drains per minute on the floor, recovers on the bench. Affects shooting and defense during the game.
- **Season energy (wear):** drains with total minutes and back-to-backs, recovers with days off and DNP-rest.

**Effort level** (low / normal / high):

- High effort: performance boost, faster drain, higher injury chance.
- Low effort: lower performance, slower drain. Useful in blowouts or meaningless games.

**Performance penalty:** below an energy threshold, shot and defense ratings scale down.

**Injury roll** (per possession or per stint):

```latex
P(\text{injury}) = base \times f(\text{energy}) \times f(\text{age}) \times f(\text{proneness}) \times f(\text{effort})
```

Severity is drawn from a distribution: day-to-day (1–3 games), short (1–3 weeks), long (1–3 months), season-ending. Tune base rates so a team loses roughly the real-world average number of player-games to injury per season.

## Chemistry and rust

Resting is never free: players who sit too long get rusty, and lineups that don't play together lose chemistry. This makes "sit the stars, sneak in as the 7 seed, arrive fresh" a real tradeoff instead of an exploit.

**Rust (per player)**

- **Builds** only after 3+ consecutive missed games (rest or injury), so normal load management on back-to-backs costs nothing.
- **Scales** with games missed, capped at about 10 games for max rust.
- **Decays** with minutes played; roughly 4–6 games of normal minutes to clear max rust.
- **Effects at max rust:** about −8% shot quality, +15% turnover rate, slower defensive reactions, and a lower in-game energy cap ("game shape"). Players coming back from injury also get a temporary re-injury risk bump if they play heavy minutes right away.

**Chemistry (per pair and team)**

| Level | Built by | Effect |
| --- | --- | --- |
| Pair familiarity | Minutes played together this season (10 pairs per lineup) | Assist rate, turnover rate, fewer defensive breakdowns on switches |
| Lineup chemistry | Average pair familiarity of the five on the floor | Applied each possession as a small modifier |
| Team chemistry | Rotation stability over recent games | Small team-wide modifier; drops with heavy lineup churn |

- Familiarity decays slowly when a pair stops playing together, so sitting stars for 20 games weakens the starting unit's chemistry while bench lineups build theirs.
- New acquisitions start with low familiarity with everyone.
- Keep chemistry effects small (about ±3–5%) so it shapes decisions without dominating talent.

**The 7-seed strategy in practice:** stars arrive fully rested but rusty and with stale chemistry, so the first playoff games are shaky. The intended optimal play is to ramp stars back 8–10 games before the playoffs, balancing energy against rust.

**Make it visible**

- Player card shows rust level and game shape; lineup screen shows a chemistry meter.
- Post-game notes, e.g. "First game back after 12 missed: 3-of-14 shooting."
- Suggested minutes restriction for players returning from injury.

**Calibrate from real data:** compare players' first 5 games after a 5+ game absence with their season averages, using game logs (`PlayerGameLogs`). Tune rust size and decay to match.

## Tactics

The player picks one offensive mode and one defensive mode per game, plus optional toggles. Every mode has a cost so none is dominant.

**Offensive modes**

| Mode | Sim effect | Fits | Backfires when |
| --- | --- | --- | --- |
| Pace & Space | More possessions, more threes | Shooters at 4–5, mobile bigs | Non-shooters on floor; slow or tired lineups |
| Post-Up / Inside | More post touches and fouls drawn, slower pace | Skilled bigs, rebounders | Weak post scorers; opponent packs the paint |
| Pick & Roll Heavy | Usage to handler and screener | Elite PG, rolling or popping big | Weak handler (turnovers); big can't finish |
| Iso / Star Ball | Usage concentrated on 1–2 players | True star scorer | Star tired or injured; teammates go cold |
| Motion | Higher assist rate and shot quality, slightly more turnovers | High-IQ passers | Low-IQ lineups turn it over |
| Grind | Fewer possessions | Underdogs, tired teams | Trailing late |
| Transition | More fast breaks | Young, athletic, high stamina | Old or tired rosters |

**Defensive modes**

| Mode | Sim effect | Fits | Backfires when |
| --- | --- | --- | --- |
| Drop Coverage | Protects rim, concedes pull-ups | Slow rim-protecting big | Elite pull-up shooters |
| Switch Everything | Fewer open shots, risk of mismatches | Versatile defenders of similar size | Big on quick guard; small guard posted up |
| Blitz / Trap | More turnovers forced, 4-on-3 behind | Long, quick, high-stamina defenders | Good passers; high fatigue cost |
| Zone | Clogs paint, concedes threes | Weak individual defenders | Good shooting opponents; weaker rebounding |
| Pack the Paint | Collapses help inside | Post-heavy or driving opponents | Opponent with spacing and shooters |
| Full-Court Press | Turnovers and pace up, very tiring | Deep benches, athletic guards | Thin rotation; elite opposing handler |

**Situational toggles:** crash the glass vs. get back, foul to stop the clock, hack a poor free-throw shooter, hunt a specific mismatch, and a pace slider independent of mode.

Implementation: each tactic is a data object of modifiers (shot-mix shifts, usage weights, pace, turnover rate, rebound positioning, energy drain), applied inside the possession loop. Keep tactics as data, not code, so new ones are easy to add.

## Tactic-roster fit

Tactics change what the team attempts; player ratings decide whether it works. A bad fit punishes itself without special-case rules.

Example: Pace & Space with three non-shooting bigs shifts more attempts to threes, but each one resolves against a 25% three-point rating, so efficiency drops.

**Emergent penalties to model:**

- **Spacing score:** computed from the five players' shooting ratings. Low spacing reduces drive and post efficiency for everyone.
- **Rebounding:** bigs pulled to the perimeter lower offensive rebound chance; long misses create long rebounds.
- **Turnovers:** pace or ball-movement tactics with low-handle, low-IQ players raise turnover rate.
- **Fatigue:** up-tempo tactics with slow, heavy lineups drain energy faster.

**Optional explicit fit score:** `fit = f(lineup, tactic)` with a small modifier (about ±5% shot quality). Keep it small to avoid double-counting the emergent effects.

**Player feedback:**

- Post-game notes, e.g. "41 threes attempted with a lineup averaging 28% from deep."
- Fit indicator (green / yellow / red) when picking a tactic; hidden on hard difficulty.
- Shot chart and per-lineup net rating in the box score.

## Season, roster, and game rules

These systems aren't the fun part, but without them the season structure, box scores, or strategy balance break.

### Play-in tournament

Seeds 7–10 in each conference play in before the playoffs: 7 vs. 8 (winner gets the 7 seed), 9 vs. 10, then the 7/8 loser plays the 9/10 winner for the 8 seed. A team coasting into 7th can be eliminated in two games, which raises the stakes of the rest-the-stars plan.

### Simulating the rest of the league

Standings need about 1,200 other games per season.

- **Option A:** run every game through the full possession sim. Consistent, but slower.
- **Option B:** a fast game-level sim for AI-vs-AI games. Faster, but its results can drift from the full sim.
- **Plan:** benchmark the possession sim early. If a full season sims in a few seconds, use it everywhere; otherwise use Option B and calibrate it against the full sim.

### Fouls

- Each player gets a foul-rate rating (personal fouls per 100 possessions) and a foul-drawing rating.
- Aggressive tactics (Blitz, Press, high effort) raise foul rates.
- **Foul trouble:** auto-sit rules (e.g. 2 fouls in the 1st quarter, 3 in the first half) the user can override, at the risk of fouling out at 6.
- Team fouls and the bonus: free throws on non-shooting fouls after 5 team fouls in a quarter.

### Players with no NBA data

Rookies and low-minute players get fallback ratings:

- Below a minutes threshold, blend their small sample with position average.
- Rookies: start from position and draft-slot averages; college stats as a later improvement.
- Flag fallback-rated players in the UI.

### Roster depth and injury crises

- 15-man roster, at least 8 healthy players required to play.
- If below 8, the user must sign a replacement from a free-agent pool of low-rated players, or call up a two-way player.
- Remaining players absorb extra minutes, which drains energy and compounds injury risk.

### Late-game logic

- **Garbage time:** auto-sub starters when the lead exceeds a threshold late (e.g. 20+ in the 4th), overridable.
- **Intentional fouling:** trailing teams foul in the last minute; leading teams target good free-throw shooters to get the ball.
- **Timeouts:** a limited number per game that briefly restore energy and can stop a run.
- **End of quarter:** hold for the last shot; desperation heaves at the buzzer (don't count heavily against shooting ratings).

## Opponent AI coaching

The AI coach picks a sensible plan for its own roster and counters what the player does, so the right tactic depends on the matchup.

- **Base plan:** pick the offensive and defensive modes with the best fit score for its roster.
- **Counters:** a lookup of tactic → counter, e.g. small-ball shooting → post up and crash the glass; drop coverage → pull-up shooters get more usage.
- **In-game adjustment:** at halftime, if the opponent is losing the efficiency battle, switch to a counter.
- **Rotation logic:** rest stars on back-to-backs, tighten rotations in the playoffs.
- **Difficulty:** easy AI ignores counters; hard AI counters immediately and scouts the player's tendencies over the season.

## Data pipeline

Ratings are generated offline from real stats and shipped as a static JSON file the game loads. Each input has exactly one source, so nothing is counted twice.

1. **Ingest:** NBA Stats via `nba_api` (tracking, zones, bio, rosters), PBP Stats (possessions, lineups), Basketball-Reference (BPM, draft), ESPN (injuries), one impact metric (EPM or DARKO). Past seasons for calibration come from the Kaggle NBA Database.
2. **Clean:** per-100-possession and percentage stats, keyed by NBA player ID; shrink small samples toward league average.
3. **Normalize:** convert each stat to a z-score within its season, and each past 2K attribute rating to a z-score within its edition, so both sides are on the same scale.
4. **Fit weights:** a ridge regression per 2K attribute learns how much each normalized stat counts toward that attribute. 2K is a training label only and never a player's rating.
5. **Rate and export:** apply the learned weights to stats only, map to 0–100, write `players.json` and `teams.json`.
6. **Validate:** a firewall test confirms no 2K value reached the export; then the calibration season sim is compared to real league averages.

Start with last season's data. This pipeline can be shared with the NBA data Substack project.

Full scraping plan: [Stats scraping plan](stats-scraping-plan.md)

## Architecture and tech stack

Keep the engine a standalone library with no UI or I/O, so the game, the AI coach, and the test harness all call the same function.

> Diagram: architecture, 6 components. Drawn in the [planning doc](https://claude.ai/code/artifact/e0c7f730-5198-4f53-a3d5-70104ee8963e); not reproduced in this snapshot.

Ratings flow in once from the offline pipeline; every consumer calls `simGame()` and gets a `GameResult` back.

| Option | Engine | UI | Tradeoff |
| --- | --- | --- | --- |
| A: All client-side | TypeScript | React + Vite | Runs in the browser like 82-0, no server; fast to share |
| B: .NET backend | C# class library | React calling an ASP.NET API | Plays to existing C# strength; needs hosting |

Either way, keep save state (season, energy, injuries) as plain JSON so it can live in local storage or a database like Supabase later.

## Milestones

Phases, priorities, and sprints now live in [Roadmap](roadmap.md). Short version: attribute database first, codebase foundation second, then a playable single game, then a full season.

## Next steps

In order, from here to a first simmed game. Each step is one brick from the Roadmap.

- [x] Paid sources: none. Free sources only (decided 2026-10-19)
- [ ] Set up `scraper/` and fetch last season from `nba_api` (base, advanced, zones, tracking, bio, rosters)
- [ ] Fetch PBP Stats possessions and lineups, Basketball-Reference BPM and draft data, ESPN injury history
- [ ] Enter 2K launch ratings for 3–5 past editions into `data/labels/2k/`, and fetch those seasons' stats
- [ ] Normalize our stats and the 2K labels to z-scores, and pair each 2K attribute with its stats
- [ ] Fit the ridge regression; report held-out error with EPM vs. DARKO and keep the better one
- [ ] Add the firewall test, then export `players.json`
- [ ] Build engine bricks E1–E5 with the One-game sim v1 weights
- [ ] Run the calibration harness on last season and tune the baselines and weights

## Open questions and risks

- [ ] Client-side TypeScript engine, or C# engine behind an API?
- [ ] Real player names and team names, or fictionalized to avoid licensing issues?
- [ ] Is a user-controlled season 82 games, or a shortened mode for quicker runs?
- [ ] In-game control at quarter breaks: MVP or later?
- [ ] Trades, free agency, and draft: in scope or out?

* [ ] Home court and travel: small home boost, extra fatigue on road trips and back-to-backs?
* [ ] Variance tuning: how streaky should shooting be so upsets happen without drowning out strategy?
* [ ] Automated strategy testing: bot coaches that always rest, always max effort, or always use one tactic, to catch dominant strategies
* [ ] Player morale: stars unhappy with reduced minutes?
* [ ] Win condition and sharing: what counts as success, and a shareable result card like 82-0's?
* [ ] Save/load: named save slots on top of JSON season state
* [x] Paid sources: decided, none. Archetypes are checked by eye instead of with BBall Index.
* [ ] 2K star bias: if 2K rates stars above their stats, do we keep that bias in our weights or remove it?
* [ ] Defense weights in the sim: are 0.50 rim, 0.25 midrange, 0.15 three the right starting point?

- **Risk — calibration time:** realistic output can take longer than building the engine. Budget for it.
- **Risk — tactics not mattering enough:** verify with A/B sim runs that each mode moves outcomes measurably.
- **Risk — injuries feeling unfair:** tune rates down and always show the cause (fatigue, effort, proneness).
