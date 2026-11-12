# Deploying Survey Insight for free

Total cost: **$0**. You need three free accounts: **GitHub** (done), **Render** and **Vercel**.
Total time: about 20 minutes.

```
GitHub repo ──► Render  (backend: Python web service, rebuilds on every push)
            └─► Vercel  (frontend: static site, rebuilds on every push)

The language model runs in each visitor's browser, so neither host needs a GPU or lots of RAM.
```

Why this setup: with the model on the server, the backend needed ~910 MB of RAM, and free
hosts without a credit card offer 512 MB (Hugging Face no longer offers free Docker Spaces).
Moving the model into the browser brought the backend down to ~200 MB.

---

## Step 1: Deploy the backend on Render

The repository contains a **`render.yaml`** "Blueprint" that tells Render exactly how to build
and run the backend, so you mostly click through.

1. Go to **dashboard.render.com** → **New +** → **Blueprint**.
2. **Connect GitHub** when asked and give Render access to the `survey-insight` repository
   (you can limit access to just that repository).
3. Select **veevedzee/survey-insight**. Render reads `render.yaml` and shows one service,
   **survey-insight-api**, on the **Free** plan.
4. It asks for the environment variables marked as "set on deploy":

   | Name | Value for now |
   |---|---|
   | `ALLOWED_ORIGINS` | `http://localhost:5173` (you'll replace it with your Vercel URL in step 3) |
   | `ALLOWED_ORIGIN_REGEX` | leave empty |

5. Click **Apply** / **Deploy Blueprint**. The first build takes ~3–5 minutes (installing
   pandas, SciPy, scikit-learn). Watch the **Logs** tab; it ends with
   `Uvicorn running on http://0.0.0.0:...`.
6. Open the service. Its URL is shown at the top, usually
   **`https://survey-insight-api.onrender.com`** (Render adds a suffix if the name is taken).
   Check it works:

   `https://survey-insight-api.onrender.com/api/health` → `{"status":"ok","version":"0.1.0"}`

   The interactive API docs are at `/docs`.

## Step 2: Deploy the frontend on Vercel

1. Go to **vercel.com** → sign in with GitHub → **Add New… → Project** → **Import**
   `veevedzee/survey-insight`.
2. Settings:
   - **Root Directory:** `frontend` (click *Edit* next to it)
   - Framework preset: **Vite** (detected automatically)
   - Build command `npm run build`, output directory `dist` (the defaults)
3. **Environment Variables:** add

   | Name | Value |
   |---|---|
   | `VITE_API_URL` | your Render URL, e.g. `https://survey-insight-api.onrender.com` (no trailing slash) |

4. Click **Deploy**. After about a minute you get your site URL, e.g.
   **`https://survey-insight.vercel.app`**. (Vite bakes `VITE_API_URL` into the build: if you
   change it later, redeploy.)

## Step 3: Allow the frontend to call the backend (CORS)

Browsers block a page on one domain (vercel.app) from reading an API on another (onrender.com)
unless the API says that page is allowed.

1. In Render: open **survey-insight-api** → **Environment**.
2. Set `ALLOWED_ORIGINS` to your Vercel URL, e.g. `https://survey-insight.vercel.app`
   (exact match: `https`, no trailing slash). To keep local development working too, use
   both, separated by a comma: `https://survey-insight.vercel.app,http://localhost:5173`
3. Optional, for Vercel preview deployments: `ALLOWED_ORIGIN_REGEX` =
   `https://survey-insight-.*\.vercel\.app`
4. **Save changes**. Render redeploys automatically (~1 minute).

## Step 4: Check it end to end

Open your Vercel URL:

1. The badge in the top-right says **Server online** (if it says offline, wait a minute: the
   free Render service may be waking up).
2. **Try with sample data** → Confirm → Continue to cleaning → Apply and continue.
3. Under *Themes*, the page downloads the language model to your browser the first time
   (~135 MB, progress shown), then reads the answers on your device. Later visits use the
   cached model.
4. Download the CSV and the HTML report.

## Step 5: Finish the README

- Replace the live demo link (`https://YOUR-PROJECT.vercel.app`) with your Vercel URL.
- Add screenshots to `docs/screenshots/` (`upload.png`, `cleaning.png`, `themes.png`,
  `charts.png`), or record a short GIF.
- Tick off the "Parts I implemented myself" list as you complete the TODOs.
- Commit and push: Render and Vercel both redeploy automatically.

## Updating later

Push to `main` on GitHub. Render rebuilds the backend and Vercel rebuilds the frontend
automatically. GitHub Actions runs the tests on every push.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Badge says **Server offline** | Free Render services sleep after 15 minutes without traffic. The first request wakes it (~1 minute); reload the page. |
| Browser console shows a **CORS** error | `ALLOWED_ORIGINS` on Render doesn't exactly match the page's address (check `https`, no trailing slash, the exact Vercel domain). |
| Works locally but not on Vercel | `VITE_API_URL` missing or wrong in Vercel; fix it and **redeploy**. |
| Themes say the model didn't download | The visitor's network blocked or interrupted the download from huggingface.co; reload to retry. Statistics and findings still work without themes. |
| Render build fails | Read the build log. The same install runs in GitHub Actions (CI tab), so a green CI means the requirements install cleanly. |
| "Session has expired" | Sessions live 30 minutes in memory, and a sleeping/restarted server forgets them. Upload again. |

## Free-tier limits worth knowing

- **Render Free:** 512 MB RAM, sleeps after 15 minutes idle, 750 free instance hours a month
  (enough for one always-available service).
- **Vercel Hobby:** generous bandwidth for a portfolio project; non-commercial use.
- **GitHub Actions:** free for public repositories.
- **Hugging Face Hub:** serves the model files to visitors' browsers for free.
