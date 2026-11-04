# Ranger Steel Intel — free iPhone PWA

This is a **free, installable web app**, not a native iOS app or native widget. It displays steel-industry headlines from public Google News RSS results and topic-based notes about how to interpret them for Ranger. It **does not** generate AI summaries or reliably deliver at exactly 7 AM. GitHub Actions scheduled workflows can be delayed or skipped, and third-party RSS results may be incomplete.

## Publish for free from Windows
1. Create a free account at https://github.com and create a **public** repository named `ranger-steel-intel`. Do not add private company data to this repository.
2. Upload the contents of this folder, including `.github/workflows/update.yml` (the dot-folder may be hidden in Windows Explorer; enable hidden items). Alternatively use Git to push all files.
3. In GitHub repository **Settings → Pages**, choose **Deploy from a branch**, branch **main**, folder **/(root)**, and save.
4. Visit `https://YOUR-USERNAME.github.io/ranger-steel-intel/` after Pages deploys.
5. In the repository **Actions** tab, run **Collect steel headlines** manually once using **Run workflow**. Wait for it to finish, then refresh the site. If Actions are disabled, enable them in the repository settings.
6. On iPhone open the site in **Safari**, tap **Share → Add to Home Screen → Add**.

## Scheduled updates
The workflow runs at 12:00 and 13:00 UTC and only collects when the current time in America/Chicago is 07:00. This handles daylight saving time, but GitHub schedules are best effort, not guaranteed to run at 7 AM. The app itself refreshes data on opening; it does not send push notifications.

## Security and costs
GitHub Pages and GitHub Actions have free usage for qualifying public repositories subject to GitHub limits. The public site and generated news JSON are visible to everyone. Never upload customer quotes, private supplier prices, confidential allocations, credentials or API keys. Google News RSS is an unofficial dependency and may change or fail.

## Next upgrade
Add a genuine AI analysis backend only after choosing a provider and understanding its pricing/free limits. Current notes are **generic topic prompts**, not evidence-based assessments of individual stories.


## News categories (updated November 2026)
The Latest news tab now groups articles into Domestic Mill News, Import News (all countries), and All Other Steel News. Older data files without category fields are classified by their topic labels. The collector writes an explicit category for new articles. The page remains informational and does not include sales takeaways.
