# Ranger Steel Intel

Mobile-friendly carbon steel plate market briefing and categorized news, hosted at https://bwerd44.github.io/ranger-steel-intel/ . The **root** files on `main` are the active application. The nested `ranger-steel-intel/` directory is legacy and is not updated or deployed by the collector workflow.

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

`test_collect.py` checks expiry, source references, incomplete collection, rejection of unsupported/future evidence, news deduplication and safe category assignment. `--offline --output /tmp/report.json` is a deterministic fallback test, not a live collection. Live runs disclose source failures and retained evidence in the Sources tab.

The site contains public-source information only. Never add customer quotes, private inventory, confidential supplier pricing or credentials. This is not a verified price index or an official Ranger Steel IT system.
