import { NextRequest } from 'next/server'

/**
 * Runtime proxy from this origin to the FastAPI backend.
 *
 * This replaces what used to be a `rewrites()` entry in next.config.ts. That
 * looked equivalent and is not: Next calls `rewrites()` during `next build` and
 * writes the resolved destination into the routes manifest, so the backend
 * address is baked into the image. On a hosted deploy the build has no
 * INTERNAL_API_URL — platforms inject env vars at run time, not into `docker
 * build` — so every request was proxied to the docker-compose fallback and
 * failed with ENOTFOUND while the backend was healthy on its own URL.
 *
 * A route handler runs per request, so the variable is read when it actually
 * has a value. `/api/auth/*` has its own more specific handlers and is matched
 * ahead of this catch-all by the App Router.
 */

// Never prerender or cache: the whole point is to read the environment and the
// request as they are right now.
export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

const BACKEND = process.env.INTERNAL_API_URL || 'http://backend:8000'

/** Roughly a minute of patience, which is what a cold free-tier instance needs. */
const COLD_START_RETRIES = 4
const COLD_START_WAIT_MS = 15_000

/** Headers that describe the old hop and would mislead the backend or the client. */
const STRIP = new Set([
  'host',
  'connection',
  'content-length',
  'transfer-encoding',
  'accept-encoding',
])

async function proxy(request: NextRequest, path: string[]) {
  const target = new URL(`${BACKEND}/api/${path.join('/')}`)
  target.search = request.nextUrl.search

  const headers = new Headers()
  request.headers.forEach((value, key) => {
    if (!STRIP.has(key.toLowerCase())) headers.set(key, value)
  })

  const hasBody = !['GET', 'HEAD'].includes(request.method)
  // Read once: a request body is a stream and cannot be replayed on a retry.
  const body = hasBody ? await request.arrayBuffer() : undefined

  try {
    let upstream = await fetch(target, {
      method: request.method,
      headers,
      body,
      redirect: 'manual',
      cache: 'no-store',
    })

    // Free hosting tiers idle the backend out separately from this service, and
    // waking it takes the better part of a minute. Without this the first
    // visitor after a quiet spell gets a dashboard of dashes reading
    // "not connected", which looks like a broken deployment rather than a cold
    // start. Wait it out instead — a slow first load beats a wrong one.
    for (let attempt = 0; attempt < COLD_START_RETRIES && upstream.status >= 502; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, COLD_START_WAIT_MS))
      upstream = await fetch(target, {
        method: request.method,
        headers,
        body,
        redirect: 'manual',
        cache: 'no-store',
      })
    }

    const out = new Headers(upstream.headers)
    // Re-encoded by fetch; passing the original values through corrupts the body.
    out.delete('content-encoding')
    out.delete('content-length')

    return new Response(upstream.body, { status: upstream.status, headers: out })
  } catch (error) {
    // Say which address failed. The previous failure mode was a bare 500 that
    // gave no hint the destination itself was wrong.
    const detail = error instanceof Error ? error.message : String(error)
    console.error(`[api-proxy] ${request.method} ${target.href} failed: ${detail}`)
    return Response.json(
      { detail: `Could not reach the backend at ${BACKEND}: ${detail}` },
      { status: 502 }
    )
  }
}

type Ctx = { params: Promise<{ path: string[] }> }

export async function GET(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path)
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path)
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path)
}
export async function PATCH(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path)
}
export async function DELETE(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path)
}
export async function HEAD(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path)
}
