# Deploying Survey Insight for free

Total cost: **$0**. You need three free accounts: **GitHub**, **Hugging Face** and **Vercel**.
Total time: about 30–40 minutes, most of it waiting for the first backend build.

```
GitHub repo ──► Vercel (frontend, rebuilds on every push)
     │
     └─ copy of backend ──► Hugging Face Space (Docker backend)
```

Replace these placeholders as you go:

| Placeholder | Example |
|---|---|
| `YOUR_GITHUB_USERNAME` | `ahmedsherif` |
| `YOUR_HF_USERNAME` | `ahmedsherif` |
| `YOUR_VERCEL_URL` | `https://survey-insight.vercel.app` |

---

## Step 0: Check your git identity

Every commit shows a name and email on GitHub. Check them:

```bash
git config --global user.name
```

```bash
git config --global user.email
```

To change them (use the email of your GitHub account, or GitHub's private
`ID+username@users.noreply.github.com` address from GitHub → Settings → Emails):

```bash
git config --global user.name "Ahmed Sherif"
```

```bash
git config --global user.email "you@example.com"
```

Commits already made keep their old author. That's fine for a portfolio, but if you want
them updated, ask before rewriting history.

## Step 1: Put the code on GitHub

1. On github.com click **New repository**. Name: `survey-insight`, **Public**, and do *not*
   add a README, .gitignore or license (the project already has them).
2. In a terminal inside the `survey-insight` folder:

```bash
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/survey-insight.git
```

```bash
git push -u origin main
```

3. Open the **Actions** tab on GitHub. The **CI** workflow runs the backend tests, the
   frontend tests and a Docker build of the backend. The first run takes ~10 minutes because
   the Docker job downloads PyTorch and the model. A green tick means the image the Space
   will build is known to work.

## Step 2: Deploy the backend on Hugging Face Spaces

Why Hugging Face and not Render: once the embedding model is loaded the backend uses about
1 GB of memory. Render's free tier has 512 MB; a free CPU Space has 16 GB.

1. **Create the Space.** On huggingface.co: your avatar → **New Space**.
   - Space name: `survey-insight-api`
   - License: MIT
   - SDK: **Docker** → template **Blank**
   - Hardware: **CPU basic · free**
   - Visibility: **Public**

2. **Create an access token** (used instead of a password when pushing): avatar →
   **Settings → Access Tokens → Create new token** → type **Write** → copy it somewhere safe.
   Never commit it or paste it into code.

3. **Clone the empty Space next to the project folder** (from the folder that *contains*
   `survey-insight`):

```bash
git clone https://huggingface.co/spaces/YOUR_HF_USERNAME/survey-insight-api
```

4. **Copy the backend files into it** (from inside `survey-insight`, in PowerShell):

```powershell
.\deploy\huggingface\prepare_space.ps1 -SpaceDir ..\survey-insight-api
```

   This copies only what the Space needs: `Dockerfile`, `backend/` code and requirements, the
   sample CSV, and a Space `README.md` whose header tells Hugging Face to use Docker on port 7860.

5. **Push to the Space:**

```bash
cd ..\survey-insight-api
```

```bash
git add -A
```

```bash
git commit -m "Deploy Survey Insight API"
```

```bash
git push
```

   When asked, the username is your Hugging Face username and the password is the
   **access token** from step 2.

6. **Wait for the build** (about 5–10 minutes). Watch the Space's **Logs** tab. When the status
   is **Running**, open:

   `https://YOUR_HF_USERNAME-survey-insight-api.hf.space/api/health`

   You should see `{"status":"ok","version":"0.1.0"}`. The interactive docs are at `/docs`.

   (The Space URL is your username and Space name joined by `-`, in lower case. If yours
   differs, use the one shown under the Space's **⋮ → Embed this Space** menu.)

## Step 3: Deploy the frontend on Vercel

1. On vercel.com: **Add New… → Project → Import** your `survey-insight` GitHub repository.
2. Settings:
   - **Root Directory:** `frontend`
   - Framework preset: **Vite** (detected automatically)
   - Build command `npm run build`, output directory `dist` (the defaults)
3. **Environment Variables:** add

   | Name | Value |
   |---|---|
   | `VITE_API_URL` | `https://YOUR_HF_USERNAME-survey-insight-api.hf.space` |

   (No trailing slash. Vite bakes this into the build, so if you change it later,
   redeploy.)
4. Click **Deploy**. After about a minute you get `YOUR_VERCEL_URL`.

## Step 4: Allow the frontend to call the backend (CORS)

Browsers block a page on one domain from calling an API on another unless the API says the
page is allowed. Tell the backend about your Vercel URL:

1. In the Space: **Settings → Variables and secrets → New variable**

   | Name | Value |
   |---|---|
   | `ALLOWED_ORIGINS` | `YOUR_VERCEL_URL` (e.g. `https://survey-insight.vercel.app`, no trailing slash) |
   | `ALLOWED_ORIGIN_REGEX` *(optional)* | `https://survey-insight-.*\.vercel\.app` (allows Vercel preview deployments) |

2. The Space restarts automatically. If not: **Settings → Factory rebuild** or **Restart**.

## Step 5: Check it end to end

Open `YOUR_VERCEL_URL`. The badge in the top-right should say **Server online**. Click
**Try with sample data** and go through every step to the dashboard; themes appear after a few
seconds. Download the CSV and the HTML report.

## Step 6: Finish the README

- Replace `YOUR_GITHUB_USERNAME` (CI badge) and the live demo link.
- Add screenshots to `docs/screenshots/` with the names the README uses
  (`upload.png`, `cleaning.png`, `themes.png`, `charts.png`), or record a short GIF.
- Tick off the "Parts I implemented myself" list as you complete the TODOs.
- Commit and push; Vercel redeploys automatically.

## Updating later

- **Frontend:** push to GitHub; Vercel rebuilds on every push to `main`.
- **Backend:** run `prepare_space.ps1` again and push the Space repo. (A possible next step is
  a GitHub Action that syncs the Space automatically using an `HF_TOKEN` secret.)

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Badge says **Server offline** | Free Spaces sleep after ~48 h without visits. Open the Space page to wake it; the first request takes ~1 minute. |
| Browser console shows a **CORS** error | `ALLOWED_ORIGINS` doesn't exactly match the page's origin (check `https`, no trailing slash, the exact Vercel domain). |
| Everything works locally but not on Vercel | `VITE_API_URL` missing or wrong; fix it in Vercel and **redeploy**. |
| Space build fails | Read the **Logs** tab. If the CI Docker job on GitHub is green, the Dockerfile itself works; check that `prepare_space.ps1` copied all files. |
| Themes show "unavailable" | The model failed to load; check the Space logs for memory or download errors. |

## Free-tier limits worth knowing

- **Hugging Face Spaces (CPU basic):** 2 vCPU, 16 GB RAM, sleeps when unused, public by default.
- **Vercel Hobby:** generous bandwidth for a portfolio project; non-commercial use.
- **GitHub Actions:** free for public repositories.
- Uploaded surveys live only in the backend's memory, so a Space restart clears every session.
