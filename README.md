# Ranger Steel Intel

Mobile-friendly carbon steel plate market briefing and categorized news with an archived quarterly forecast dashboard, hosted at https://bwerd44.github.io/ranger-steel-intel/ . The **root** files on `main` are the active application. The nested `ranger-steel-intel/` directory is legacy and is not updated or deployed by the collector workflow.

## Morning Market Briefing

Six narrative sections cover Market Overview, Domestic Mill Supply, Imports & Trade, Pricing Trends, Demand Outlook, and Overall Market Conditions. There are no article cards, headline counts, Top Developments, grade-coverage boxes or update-target boxes in the briefing.

Reported paragraphs cite primary evidence and identify its reporting period and evidence date. Context and interpretation are separate. A quarterly producer assessment does not establish today's spot conditions. AISI raw steel and all-steel import data are explicitly distinguished from discrete carbon steel plate supply.

No numerical price is inferred. No live mill allocation, shutdown, lead-time, tariff, freight or grade-by-size availability claim is generated from an RSS headline. Unavailable or unverified information is stated explicitly. The report gives no purchasing or sales instructions.

## Free automatic collection

`collect.py` uses Python's standard library only; there is no paid service, API key or AI subscription. Run:

```sh
python -m unittest -v test_collect.py
python collect.py
```

Each run writes and validates `data/latest.json` atomically, containing a six-section `briefing`, unique categorized `articles`, and collection diagnostics. It fetches SSAB's market outlook, AISI weekly production and the latest recognized AISI import release. Parsers accept dated, recognized structures only. Unsupported page layouts or direction wording cause a data gap, not an invented update. This conservative deterministic system is not an open-ended AI market analyst.

`data/reviewed-evidence.json` stores manually reviewed fallbacks with source URLs, review dates, evidence dates and expiry windows. Retained evidence is labeled as not reverified in that collection. Production evidence expires after 14 days, import releases after 45 days and quarterly commentary after 105 days from period end. Dates never roll forward simply because collection ran. Reviewed evidence should be maintained as source coverage expands. The generator is intentionally conservative when no recognized new evidence is available.

Google News RSS is used only for news discovery over the past 14 days. Titles and canonical URLs are deduplicated globally, including simple syndicated titles, before each article is assigned to one of Domestic Mill News, Import News, or All Other Steel News. Dates, publisher labels, expandable details and source links remain. RSS headlines are labeled unverified and do not become briefing facts.

`.github/workflows/update.yml` runs at approximately **7:17 AM America/Chicago**, handles both daylight-saving offsets, and supports manual runs. It also runs when collector, reviewed evidence or workflow code changes. GitHub schedules are best effort and can be delayed; inactive public repositories can have schedules disabled by GitHub. Check Actions for run failures. The workflow commits generated JSON with the built-in token and explicitly deploys a Pages artifact, because token-created commits do not trigger another branch-based Pages build. No secrets beyond GitHub's built-in token are needed.

Pages must allow the `github-pages` environment to deploy `main`. This repository uses GitHub Pages; choose GitHub Actions as the Pages source for the collector's explicit deployments. The workflow only publishes root application assets and generated JSON.

## Freshness, mobile & PWA

The app refreshes on opening, coming back into view, reconnecting and every 15 minutes while visible. Reports older than 36 hours show a warning. Failed fetches show an unavailable state instead of a cached briefing. The service worker upgrades immediately, removes prior Ranger caches, refreshes navigation from the network and never caches report JSON. The installable PWA shell remains available offline, while the report requires a connection. Existing home-screen installations receive the updated worker after they reconnect and reopen.

## Verification

`test_collect.py` checks expiry, source references, incomplete collection, rejection of unsupported/future evidence, news deduplication and safe category assignment. `--offline --output /tmp/report.json` is a deterministic fallback test, not a live collection. Live runs disclose source failures and retained evidence in the published data diagnostics.

The site contains public-source information only. Never add customer quotes, private inventory, confidential supplier pricing or credentials. This is not a verified price index or an official Ranger Steel IT system.


## Quarterly Forecast (replaces Sources navigation)

The third tab is now **Quarterly Forecast**. Briefing paragraphs and news articles retain their original source links. The forecast covers A36, A572 Grade 50 and A516 Grade 70 with a common directional framework; it does not estimate grade premiums or dollar prices.

`forecast.py` uses the current Chicago calendar quarter through Q4 of the following calendar year. In November 2026 that is Q4 2026 and Q1–Q4 2027. The dashboard shows a qualitative quarterly trend chart, detailed quarter analyses, bullish/base/bearish scenarios, availability assumptions, confidence, product-specific driver channels and indicators that could change the forecast. Bullish and bearish refer to higher and lower plate prices, not an investment recommendation.

### Monthly maintenance and permanent editions

The existing free daily GitHub Actions workflow calls `forecast.py` after refreshing the briefing. On the first successful run of each new Chicago calendar month, the generator appends one edition to `data/forecasts.json`. Further runs in that month preserve it byte-for-byte. This uses the daily 7:17 AM Central schedule, so monthly maintenance does not depend on a second independent deployment workflow. Missing runs are caught up at the next successful daily run.

The single `forecasts.json` file contains **all complete historical editions**, not just summary labels. Each edition saves its model version, dates, sources, inputs, scenarios, assumptions, original horizon and integrity hash. `validate()` rejects changed historical content. Git commits provide an additional version history. The first real edition is November 2026; no historical forecasts are fabricated. The edition selector displays preserved forecasts and the dashboard compares each quarter's direction and availability to the prior edition.

To revise within a month, manually dispatch **Collect plate market briefing** with a nonempty `revision_reason`. This appends a labeled `YYYY-MM-rN` revision, preserving the original and explaining the change. It never silently updates the existing edition. The client flags missing monthly updates and missing quarters when the calendar advances; it does not invent forecasts to fill them.

### Model and sources

No AI model is configured. This is a deterministic scenario framework, not a statistically fitted or backtested plate-price predictor. Its full thresholds, weights, quarterly decay, judgmental seasonal adjustments and stress scenarios appear inside every edition and in the dashboard's assumptions panel. Confidence is qualitative, not a probability.

Dated SSAB plate commentary supplies the main signal. Federal Reserve G.17 manufacturing output supplies a deliberately small indirect adjustment. AISI all-steel statistics, EIA energy outlooks and dated reviewed DOE and trade-policy context describe scenario channels; they do not automatically add plate price premiums. The generator attempts fresh Federal Reserve and EIA retrieval for each new monthly edition. The daily collector refreshes supported SSAB and AISI evidence first. Missing, stale or unrecognized inputs are omitted and retrieval failures are recorded. Missing plate-price evidence suppresses the directional base case and the chart displays gaps.

`data/forecast-context.json` stores dated manually reviewed policy and data-center context, with expiry windows. It is not a live legal database. The monthly model does not claim to verify every new tariff, mill shutdown, government policy, sector order or project announcement. Policy continuity, seasonality, historical inventory-cycle behavior and longer-horizon supply normalization are clearly labeled assumptions. Sources and retrieval/review dates are saved with each edition. Mutable source pages can change later; the archived edition preserves the extracted inputs and their dates.

Data centers primarily create demand for structural products, rebar and electrical equipment; plate exposure through tanks, skids and selected power equipment is identified separately. HRC futures, coil prices, all-steel output and electrical-steel demand are never used as direct plate-price forecasts. A516 Grade 70 specification, testing or normalized requirements may restrict availability differently from commodity A36 and Grade 50; no unsupported specification premium is estimated.

Run `python -m unittest discover -p 'test_*.py' -v` and `python forecast.py` to verify generation. `--offline` is for tests only. No paid services or keys are required. Pages publishes `data/forecasts.json` along with the existing PWA assets. All `/data/` fetches remain network-only, and the forecast worker version replaces the previous shell cache.

## Market Pulse, weekly changes and the light dashboard

The app has exactly three main tabs: **Morning Market Briefing**, **Latest News**, and **Quarterly Forecast**. The interface uses off-white backgrounds, white panels, dark navy/charcoal text and Ranger orange accents. Detailed briefing, scenarios, methodology, sources, history and industry context are expandable. Market direction uses muted red (increasing pressure), orange (stable/mixed), green (easing) and gray (insufficient). Arrows and text accompany colors. These are pressure signals, not judgments about good or bad conditions.

`intelligence.py` runs in the existing daily workflow after `collect.py` and monthly forecast maintenance. It writes `data/intelligence.json` and preserves append-only `data/pulse-history.json`. It does not change the existing forecast generator or old forecast editions. Daily source fetching, schema checks, monthly maintenance, history preservation and publication use only Python's standard library and GitHub's built-in Actions token.

### What is actually automated

* Market Pulse reads explicit dated plate observations. The currently recognized automatic pricing input is SSAB's dated plate-price trend from the briefing collector. Its eligibility is 45 days from the reporting period end, at Low confidence; it is quarterly commentary, not a current spot quote. Other metrics can use reviewed structured observations in `data/market-evidence.json` when qualified evidence becomes available.
* Low distributor inventory does **not** prove tightening supply. A strong market level does **not** prove strengthening demand. Aggregate imports, raw-steel utilization, coil/HRC lead times and other product markets cannot populate plate indicators. Missing, future-dated, conflicting or expired evidence is handled explicitly. Missing is never silently converted to Stable.
* The published pulse is fetched without caching. A pulse collection older than 36 hours is shown as gray Insufficient Data, even if the saved file contains earlier readings. Saved history is preserved.
* Readings save original evidence and integrity hashes. A same-day rerun with no new semantic evidence does not append another reading. Older snapshots are never rewritten. Changes in retrieval time alone do not manufacture market changes.
* The weekly baseline is the latest saved snapshot on or before seven days earlier, within a fourteen-day lookback. It compares actual saved readings and dated developments. Coverage loss/gain is separated from physical market changes. New AISI steel production/import releases provide labeled broad context, not plate availability conclusions. The first week has no comparison; no previous readings are backfilled.
* Nucor, SSAB Americas, JSW Baytown and Cleveland-Cliffs public pages are retrieved daily. The tracker displays recognized SSAB commentary and dated reviewed developments. Current operating conditions, allocations, lead times and restart dates are not inferred from capabilities pages, financial headlines or scheduled downtime. Reviewed JSW outage planning and Cleveland-Cliffs footprint changes retain their original dates and status limitations. This is a conservative source watch, not a comprehensive live plant-status service. New unsupported mill developments require review before they become assertions.
* Demand Drivers explain plate applications versus structural steel, rebar, electrical steel and coil. References are drawn from unexpired dated forecast evidence, refreshed during monthly forecasting. They are context, not measured daily plate order books.

### Weekly development and evidence records

`data/market-evidence.json` can hold `observations`, `market_developments`, `mill_developments`, and `quarterly_outcomes`. An indicator observation must have a valid metric and condition, `scope: discrete_plate`, `verified: true`, a source URL, evidence date, confidence and a documented basis. Unspecified freshness defaults to 30 days. Record a narrower window when appropriate. Reviewed records must be maintained with sources; never enter unsupported values simply to fill a gray cell.

Quarterly Forecast colors and arrows follow each stored direction automatically. Forecast editions and comparisons remain available through the selector. The base case stays concise, and assumptions, scenarios, evidence and history are expandable. Actual forecast numbers and historical editions are not altered by this visual redesign.

### Forecast Accuracy

The new Forecast Accuracy section is intentionally **Not yet evaluable** until a forecast quarter is complete and a suitable outcome is available. `quarterly_outcomes` must identify a reviewed, dated, verified discrete-plate observation on a **quarter-over-quarter** basis for quarters that were still in the future at issuance. A quarter already underway requires an observation of the matching remaining period versus the issue-date baseline (`remaining_period_vs_issue`, with matching `period_start` and `period_end`), not a full-quarter substitution. Each outcome needs its original source. HRC, all-steel output, within-quarter movements and unverified headlines are rejected. The system computes qualitative directional agreement only; it does not invent actual prices, magnitude accuracy, hit rates or probability calibration. No reliable automated actual plate-price series is configured. Reviewing appropriate outcome evidence is a separate required step before the comparison can be populated.

### Verification and publication

Run `python -m unittest discover -p 'test_*.py' -v`, `python collect.py`, `python forecast.py`, and `python intelligence.py`. The workflow runs the tests, collects the briefing/news, maintains monthly forecast editions, derives Market Pulse/weekly comparisons, commits generated data and publishes the root app plus full pulse/forecast history. `--offline` on the intelligence generator is only a test/fallback inspection mode. The PWA cache version is advanced; old Ranger caches are removed, navigation is network-first and every `/data/` request is network-only.
