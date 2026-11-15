# Deploying Gravity Gap

Three ways to run the app, from simplest to hosted. All commands run from the repo root unless noted.

| Option | Use it for | Needs |
|---|---|---|
| A. Local, no Docker | Development, the demo laptop | Python 3.13, Node 22 |
| B. `docker compose up` | One-command local stack; the **R13 fallback** if hosting fails at judging time | Docker Desktop |
| C. Render (API) + Vercel (web) | Public URL for judges | Render and Vercel accounts |
| **W. Website only on Vercel** | **Fastest public URL for judges (about 10 minutes)** | A Vercel account |

## W. Website only on Vercel (recommended for submission)

The web app ships every engine output it needs (`web/public/artifacts`, copied at build time), so it runs as a
static site with no backend. In this mode the six habitat presets, Compare, Briefing, Trust, Air map,
Detection, Planner, Ledger and the story page all work; the Ask drawer answers the saved demo questions only, and a
custom habitat (one that matches no preset) shows "needs the live API". Every page shows an "offline data" chip.

1. Sign up at vercel.com with **Continue with GitHub** (you do this).
2. **Add New > Project**, import `adi-btw/NASA-Hackathon-2026`. Vercel can deploy a private repo; the site it
   makes is public either way.
3. **Root Directory: `web`** (click Edit next to Root Directory). Framework preset: Next.js (auto-detected).
   Leave the build and install commands at their defaults.
4. **Environment Variables:** add `NEXT_PUBLIC_API_URL` with the value `off`. This tells the site not to look for
   an API, so pages load straight from the bundled data. (If you forget it, the site still detects that the API
   address points at `localhost` and skips it.)
5. **Deploy.** In the build log, check for `[copy-artifacts] copied N file(s)` and `Compiled successfully`.
6. Open the URL it gives you (for example `https://nasa-hackathon-2026.vercel.app`) in a **private window**, logged
   out, and click through `/`, `/bounds`, `/briefing?habitat=lunar_base` and `/trust`.
7. Optional, recommended by Space Apps: request a FortiGuard web filter classification for the URL so judges'
   networks do not block it (Category: Education or Web-based Application; Company Name: N/A).

Checked locally before handing over: `NEXT_PUBLIC_API_URL=off npx next build` prerenders every route as static
content, and the built site loads `/`, Bounds, Compare, Briefing, Trust, Air map, Detection, Planner and Ledger in
about 1.5 s each with zero requests to an API.

To add the live API later (custom habitats, live AI answers), follow C below and change `NEXT_PUBLIC_API_URL` to
the Render URL, then redeploy.

> **You do this part yourself.** Nothing in this repo creates accounts, stores credentials, or deploys
> anything. Someone on the team must sign up for Render and Vercel, connect the GitHub repo, paste the
> environment variables and press deploy. The files here (`Dockerfile.api`, `web.Dockerfile`,
> `docker-compose.yml`, `render.yaml`) are configuration only.

## Environment variables

| Variable | Where | Default | Purpose |
|---|---|---|---|
| `CORS_ORIGINS` | API | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated browser origins allowed to call the API. Set it to the Vercel URL in production. |
| `LEDGER_TEAM_TOKEN` | API | unset | Enables `POST /ledger` (header `X-Team-Token`). Unset means ledger writes return 403. |
| `ANTHROPIC_API_KEY` | API | unset | Live Claude answers in `/ask`. Unset means cached/template answers; the app still works. |
| `GRAVITY_GAP_MODEL` | API | `claude-sonnet-5-5` | Claude model for `/ask`. |
| `GRAVITY_GAP_ASK_RATE`, `GRAVITY_GAP_LEDGER_RATE` | API | 20, 10 | Per-IP requests per minute. |
| `PORT` | API container | 8000 | Render injects its own; the container honours it. |
| `NEXT_PUBLIC_API_URL` | web, **build time** | `http://localhost:8000` | URL the browser uses for the API. It is baked into the bundle, so rebuild after changing it. |

Never commit secrets. Locally, put them in a git-ignored `.env` (Docker Compose reads it) or export them in
your shell.

## A. Local without Docker (two terminals)

```bash
# Terminal 1: API on :8000
pip install -r requirements.txt          # optional: pip install -r requirements-ai.txt for live Claude
python -m uvicorn api.main:app --reload --port 8000

# Terminal 2: web on :3000
cd web
npm ci
npm run dev                              # or: npm run build && npm start
```

Open http://localhost:3000 (API docs at http://localhost:8000/docs). The `predev`/`prebuild` scripts copy
`artifacts/` and `ledger/predictions.jsonl` into `web/public/artifacts/`, so the web app keeps working
offline from static data if the API stops.

## B. Docker Compose (R13 local fallback)

```bash
docker compose up --build                # first run builds both images (a few minutes)
docker compose down                      # stop
```

- web: http://localhost:3000, API: http://localhost:8000/health
- `web` waits until the API health check passes.
- Secrets are optional: `LEDGER_TEAM_TOKEN=... ANTHROPIC_API_KEY=... docker compose up` or a `.env` file.
- Ledger writes made inside the container are lost when the container is removed. The canonical ledger is
  `ledger/predictions.jsonl` in git.

Images on their own:

```bash
docker build -f Dockerfile.api -t gravity-gap-api .
docker build -f web.Dockerfile --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000 -t gravity-gap-web .
```

Docker is not installed on the team laptops; CI (`docker` job) builds both images and smoke-tests the API
image's `/health` on every push, so a broken Dockerfile shows up there.

## C. Hosted: Render (API) + Vercel (web)

Deploy the API first: the web build needs its URL.

### C1. API on Render

1. Create a Render account and connect GitHub with access to `NASA-Hackathon-2026` (you do this).
2. **New > Blueprint**, pick the repo. Render reads `render.yaml` and proposes the `gravity-gap-api`
   web service (Docker runtime, `Dockerfile.api`, health check `/health`, free plan).
3. Fill in the env vars it asks for (all `sync: false`, so they are never stored in git):
   - `CORS_ORIGINS`: leave as `http://localhost:3000` for now; you set the Vercel URL in step C3.
   - `LEDGER_TEAM_TOKEN`: a long random string, or leave empty to keep the hosted ledger read-only
     (recommended for a public demo).
   - `ANTHROPIC_API_KEY`: optional.
4. Apply. When the deploy is live, open `https://<service>.onrender.com/health` and check `"status": "ok"`.

Notes: the free plan sleeps after inactivity and the first request takes ~1 minute to wake it up; open
`/health` a few minutes before judging. The filesystem is ephemeral, so `POST /ledger` appends on Render
disappear on the next deploy. Freeze real predictions locally and commit them instead.

### C2. Web on Vercel

1. Create a Vercel account and import the GitHub repo (you do this).
2. **Root Directory: `web`**. Framework preset: Next.js (auto-detected). Leave build/install commands at
   their defaults (`npm ci`, `npm run build`).
3. Environment variable (Production and Preview): `NEXT_PUBLIC_API_URL = https://<service>.onrender.com`
   (no trailing slash).
4. **Include files outside the root directory**: the `prebuild` script copies `../artifacts` and
   `../ledger` into `web/public/artifacts`. Vercel clones the whole repo, so this works as long as the
   project setting "Include source files outside of the Root Directory in the Build Step" stays enabled
   (the default). Check the build log for `[copy-artifacts] copied N file(s)`.
5. Deploy and note the URL, e.g. `https://gravity-gap.vercel.app`.

### C3. Connect them (CORS)

The API only answers browsers from origins listed in `CORS_ORIGINS` (`api/main.py`,
`parse_cors_origins`). In Render, set:

```
CORS_ORIGINS=https://gravity-gap.vercel.app,http://localhost:3000
```

Use the exact origin (scheme + host, no path; a trailing slash is stripped). Vercel preview deployments
have their own URLs; add the ones you need. Save; Render restarts the service. Then load the Vercel site and
check the browser's network tab: calls to the Render URL should return 200 without CORS errors. If the API is
down, the site falls back to the static artifacts (offline mode).

## Rebuilding artifacts before a deploy

Order matters, because each step hashes the outputs of the previous one:

1. Engine artifacts:
   ```bash
   python -m engine.catalog        # artifacts/catalog.json
   python -m engine.rules          # artifacts/rules.json
   python -m engine.bounds         # artifacts/bounds/*.json
   python -m engine.regime_grid    # artifacts/regime_grid.json
   python -m engine.planner        # artifacts/planner.json
   python -m engine.validation     # artifacts/validation_report.md
   python -m engine.hindcast       # artifacts/hindcast_saffire.json, validation_saffire.md
   ```
2. `python -m engine.ai.answer --build-cache` (AI answer cache; it records artifact hashes).
3. `python scripts/build_manifest.py` (always last: `artifacts/MANIFEST.json`; `/health` reports
   `degraded` if any artifact changed after it).

Then commit, push, and redeploy both services: the API image and the web bundle each contain a copy of
`artifacts/`.

## Pre-judging checklist

- [ ] `https://<api>/health` returns `"status": "ok"` and `"manifest_ok": true`.
- [ ] The Vercel site loads presets and physics without CORS errors.
- [ ] Offline mode works (block the API URL in devtools; pages still render from static artifacts).
- [ ] Fallback ready: `docker compose up --build` tested on the demo laptop, plus the recorded video.
