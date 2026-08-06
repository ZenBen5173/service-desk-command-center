# Getting a stable public URL

The Cloudflare quick tunnel we used for testing dies when the laptop shuts down
and hands out a different address every restart. That is fine for a five-minute
check and useless as a submitted link. This puts the same three containers on
Render instead, on a URL that survives the night.

Everything below is on Render's free tier. No card needed.

**Time:** about 40 minutes, most of it waiting for builds.

---

## Before you start

You need a GitHub account and a Render account (sign in with GitHub — one
click). Have your Supervity API key to hand; it goes in by typing, never in the
repo.

---

## 1 · Put the code in your own GitHub repo

The `origin` remote currently points at the template
(`digitamizers/AutoPilot-Template`) — you can't push there.

Create an empty repo on GitHub (private is fine), then:

```bash
git remote set-url origin https://github.com/YOUR-USERNAME/YOUR-REPO.git
git add -A
git commit -m "Round 2 Command Center"
git push -u origin HEAD
```

**Check before pushing:** `git status` must not list `.env`. It is gitignored,
so it shouldn't — but your Supervity key is in that file, and a key in a repo is
a key you have to rotate.

## 2 · Point Render at the repo

Render dashboard → **New** → **Blueprint** → pick your repo.

It reads `render.yaml` and offers to create three things:

| Service | What it is |
|---|---|
| `autopilot-db` | PostgreSQL |
| `autopilot-backend` | The FastAPI API |
| `autopilot-frontend` | The Command Center |

Click **Apply**. The first build takes 5–10 minutes.

## 3 · Add the Supervity key

`autopilot-backend` → **Environment** → set:

| Key | Value |
|---|---|
| `SUPERVITY_API_KEY` | your key from auto.supervity.ai/u/api-keys |

The blueprint marks it `sync: false` precisely so it is never in the repo.

## 4 · Wire the two services together

Once both have deployed, Render shows each service's URL. Fill in the three
placeholders:

**On `autopilot-frontend` → Environment:**

| Key | Value |
|---|---|
| `INTERNAL_API_URL` | the backend's URL, e.g. `https://autopilot-backend.onrender.com` |
| `NEXTAUTH_URL` | the frontend's own URL |

**On `autopilot-backend` → Environment:**

| Key | Value |
|---|---|
| `FRONTEND_URL` | the frontend's URL (this is the CORS allowlist) |

Save. Both services redeploy automatically.

## 5 · Load the agent data

The new database starts empty — the schema is created by migrations, but no
agent runs have been mirrored into it yet. Pull them from Supervity Auto:

```bash
curl -X POST "https://YOUR-FRONTEND.onrender.com/api/agent/sync?timeline_limit=60"
```

Give it a few minutes; it walks every workflow, run and timeline. Then open the
site — the Elimination Backlog should show your ticket classes.

## 6 · Check every page

| Page | Should show |
|---|---|
| `/` | Business outcomes, agent runs, the roster |
| `/elimination` | 17 ticket classes with proposed fixes |
| `/workbench` | The human queue |
| `/ai/insights` | 13 insights |
| `/ai/policies` | 4 policies and the evaluation log |
| `/data-manager` | 8 integrations |

---

## Two things to know about the free tier

**It sleeps after 15 minutes idle.** The first visit after that takes about 50
seconds to wake. A judge clicking a cold link will wait. Open the site yourself
shortly before judging, or point a free uptime pinger at it.

**The free database is deleted after 30 days.** Long past the deadline, but note
it if this outlives the hackathon.

---

## The security tradeoff, stated plainly

`AUTH_BYPASS=true` is set on purpose: the brief requires a demo with no login
wall. It means anyone who has the URL can also edit policies and clear Workbench
items — not just read.

That is an accepted tradeoff for a judged demo, not a mistake. Keep the link to
the submission, and don't post it anywhere it will be crawled.

## If a build fails

- **Backend won't start** — check `DATABASE_URL` is wired from the database
  (the blueprint does this) and that `SUPERVITY_API_KEY` is set.
- **Frontend loads but every number is blank** — `INTERNAL_API_URL` is wrong or
  missing. It must be the backend's full `https://` URL, no trailing slash.
- **Pages 404** — the frontend deployed the dev stage. The Dockerfile's last
  stage is `prod`, which Render uses by default; don't set a target.
