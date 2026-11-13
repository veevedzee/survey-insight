# Deploying Survey Insight for free

The hosted version needs **no server, no credit card and no extra accounts**: the whole
analysis runs in the visitor's browser, and **GitHub Pages** serves the static files.

```
GitHub repo ──(push to main)──► GitHub Actions builds the site ──► GitHub Pages
                                                                     │
Visitor's browser: React app + Python (Pyodide) + language model ◄───┘
(the survey file never leaves the visitor's device)
```

## One-time setup (2 minutes)

1. Open the repository on GitHub → **Settings** → **Pages** (left sidebar).
2. Under **Build and deployment → Source**, choose **GitHub Actions**.
3. Go to the **Actions** tab → **Deploy to GitHub Pages** → **Run workflow** (or just push a
   commit). The first deploy takes about 2–3 minutes.
4. Your site is live at **https://veevedzee.github.io/survey-insight/**
   (the URL is also shown in the workflow run and under Settings → Pages).

That's it. Every push to `main` rebuilds and redeploys the site automatically.

## What visitors experience

- **First visit:** the page downloads Python and its data libraries (~40 MB, about 20 seconds
  on a decent connection) in the background while the visitor reads the upload screen. The
  language model for themes (~135 MB) downloads when the dashboard first needs it. Progress is
  shown for both.
- **Later visits:** everything loads from the browser's cache in a few seconds.
- Works in current Chrome, Edge, Firefox and Safari on desktop. Phones work too, but the first
  download is large on mobile data and theme detection is slower.

## Checking it works

Open the site, wait for the badge to say **Runs on your device**, then **Try with sample
data** → Confirm → Continue to cleaning → Apply and continue. Themes appear after the model has
downloaded. Download the CSV and the HTML report.

## Optional: run as a server instead

The same Python package can run as a normal FastAPI server (`backend/survey_insight/api.py`),
for example to analyse very large files. Set `VITE_API_URL` to the server's address when
building the frontend and the app talks to it over HTTP instead of using Python in the
browser. `render.yaml` describes such a server for Render (whose free tier asks for a card).

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| The Pages workflow fails at "configure-pages" | Pages isn't enabled yet: Settings → Pages → Source: **GitHub Actions**, then re-run the workflow. |
| Site shows a blank page or 404s for assets | The site must be built with `VITE_BASE=/survey-insight/` (the workflow does this). If you rename the repository, it adapts automatically. |
| Badge says **Engine failed to load** | The browser couldn't download Python from the jsDelivr CDN (offline, firewall or ad blocker). Reload once connected. |
| Themes show an error with **Try again** | The language model download from Hugging Face was interrupted. Click **Try again**; finished parts are cached. |
| Very large surveys are slow | Everything runs on the visitor's device. Thousands of rows are fine; for much larger files use the server mode above. |

## Cost and limits

- **GitHub Pages:** free for public repositories (1 GB site size, 100 GB bandwidth a month,
  which is plenty for a portfolio).
- **jsDelivr** (serves Pyodide) and the **Hugging Face Hub** (serves the model files) are
  free public CDNs.
- No server means no cold starts, no sleeping, and nothing to keep running.
