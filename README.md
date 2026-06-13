# Familie WK Poule 2026 — site + daily standings timeline

Two parts:

1. **`familie-wk-poule-2026.html`** — the website. Shows the live standings
   (the WKPooltjes widget) **and** a "Het Verloop" bump chart of the standings
   per day.
2. **A tiny daily job** that records the standings once a day into
   `standings-history.json`, which the bump chart reads.

The chart shows demo data when you just open the HTML locally, and switches to
your real data automatically once `standings-history.json` has snapshots and the
page is served over http(s) (e.g. GitHub Pages).

## Files

```
familie-wk-poule-2026.html          the website
standings-history.json              the growing history (starts empty)
snapshot_standings.py               fetches + parses + appends one day
.github/workflows/snapshot-standings.yml   runs the script daily, commits it
```

## Setup on GitHub (free)

1. Create a repo and drop all of these files in at the **root**, keeping the
   `.github/workflows/` folder structure intact.
2. **Settings → Pages** → deploy from the `main` branch, root. Your site is now
   live at `https://<user>.github.io/<repo>/familie-wk-poule-2026.html`.
3. **Settings → Actions → General → Workflow permissions** → set to
   **Read and write permissions** (so the job can commit the json back).
4. Go to the **Actions** tab, pick *Snapshot standings*, and hit **Run workflow**
   once to capture the first day. After that it runs automatically every morning.

Each run appends one dated entry. After two days you'll see the lines start to
move; over the tournament it becomes the full race chart.

## Adjusting things

- **Capture time:** edit the `cron:` line in the workflow (it's in UTC).
- **Different pool/widget:** set `WIDGET_URL` / `POOL_ID` as env vars, or edit the
  defaults at the top of `snapshot_standings.py`.
- **Run by hand:** `pip install requests beautifulsoup4 && python snapshot_standings.py`

## If the standings don't parse

The widget returns rendered HTML and the parser reads its table heuristically.
If a run reports *"No standings parsed"*, it saves the raw response to
`debug_widget.html`. Open that, look at the table's rows/columns, and the
column-picking logic in `parse_standings()` can be tuned to match.
