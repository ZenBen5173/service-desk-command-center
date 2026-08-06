# Getting a stable public URL

The Cloudflare quick tunnel we used for testing dies when the laptop shuts down
and hands out a different address every restart. That is fine for a five-minute
check and useless as a submitted link. This puts the same three containers on
Render instead, on a URL that survives the night.

Everything below is on Render's free tier. No card needed.

**Time:** about 30 minutes, most of it waiting for builds.

---

## Before you start

You need a Render account — sign in with GitHub, one click. Have your Supervity
API key to hand; it goes in by typing, never in the repo.

---

## 1 · The code is already on GitHub ✅

**https://github.com/ZenBen5173/service-desk-command-center** — public, and
`render.yaml` is in the root where Render expects it.

`.env` is gitignored, so the Supervity key is not in the repo. If you push more
work later, keep it that way: run `git status` and confirm `.env` is absent
before committing. A key in a public repo is a key you have to rotate.

## 2 · Point Render at the repo

Render dashboard → **New** → **Blueprint** → pick `service-desk-command-center`.

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

No trailing slashes. Save — both services redeploy automatically.

## 5 · Load the agent data

The new database starts empty. Migrations create the schema, but no agent runs
have been mirrored into it yet. Pull them from Supervity Auto:

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

If the numbers differ from your local instance, the sync in step 5 hasn't
finished — run it again and wait.

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
items — not just read them.

That is an accepted tradeoff for a judged demo, not an oversight. Keep the link
to the submission, and don't post it anywhere it will be crawled.

## If a build fails

- **Backend won't start** — check `DATABASE_URL` is wired from the database
  (the blueprint does this) and that `SUPERVITY_API_KEY` is set.
- **Frontend loads but every number is blank** — `INTERNAL_API_URL` is wrong or
  missing. It must be the backend's full `https://` URL, no trailing slash.
- **Pages 404** — the frontend deployed the dev stage. The Dockerfile's last
  stage is `prod`, which Render uses by default; don't set a target.
- **`sqlalchemy.exc.NoSuchModuleError: postgres`** — an older checkout. The
  current `app/core/database.py` rewrites the `postgres://` scheme that managed
  providers hand out; make sure Render is building the latest commit.

---

## Meanwhile: the quick tunnel

Still fine for testing and for recording, and it needs no account. From the
repo root, with the stack running:

```bash
docker run -d --name qtunnel --network autopilot-template_app-network cloudflare/cloudflared:latest tunnel --no-autoupdate --url http://frontend:3000
```

Then read the address out of the logs:

```bash
docker logs qtunnel 2>&1 | grep -o 'https://.*trycloudflare.com'
```

Note the network name — `autopilot-template_app-network`, not `_default`. An
earlier attempt failed for a while purely because of that, and the error it
gives you points at a firewall instead.
