import { getSession } from 'next-auth/react'

// Empty means "same origin": requests go to /api/... on whatever host is
// serving the page, and next.config.ts rewrites them to the backend. That is
// what makes a single public URL work when the app is shared — set
// NEXT_PUBLIC_API_URL only when the backend must be reached on its own host.
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? ''
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || ''

/**
 * A robust API client that handles authentication and base path resolution.
 * @param endpoint The API endpoint to call, e.g., '/api/test' or '/api/admin/dashboard'.
 *                 The endpoint should include the '/api' prefix.
 * @param options Standard fetch options (method, body, etc.).
 */
async function apiClientFetch<T = unknown>(endpoint: string, options: RequestInit = {}): Promise<T> {
  // Look up the session, but never let that failure block the request.
  //
  // NextAuth resolves its session endpoint against NEXTAUTH_URL. When the app
  // is reached on a different host — a tunnel, a deployment, anything but the
  // configured origin — that lookup throws, and an unguarded `await` here took
  // every data call down with it: the whole dashboard rendered empty while the
  // API itself was perfectly healthy. The token is optional (the backend runs
  // with AUTH_BYPASS in this environment), so a missing session degrades to an
  // unauthenticated call rather than to a blank page.
  const headers = new Headers(options.headers || {})

  try {
    const session = await getSession()
    if (session?.accessToken) {
      headers.set('Authorization', `Bearer ${session.accessToken}`)
    }
  } catch (error) {
    console.warn('[API] Session lookup failed; continuing without a token', error)
  }

  // Construct the full URL: http://localhost:8001/app1/api/test
  const fullUrl = `${API_URL}${BASE_PATH}${endpoint}`

  const response = await fetch(fullUrl, { ...options, headers })

  // If the backend returns a 401, log it but don't force redirect in dev mode
  if (response.status === 401) {
    console.warn('[API] 401 Unauthorized — check backend AUTH_BYPASS setting')
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({
      detail: response.statusText,
    }))
    throw new Error(errorData.detail || 'An API error occurred.')
  }

  // Handle responses with no content
  if (response.status === 204) {
    return null as T
  }

  return response.json() as Promise<T>
}

/**
 * API client with convenience methods for common HTTP operations.
 */
export const apiClient = {
  /**
   * Perform a GET request.
   */
  get: <T = unknown>(endpoint: string, options?: RequestInit): Promise<T> => {
    return apiClientFetch<T>(endpoint, { ...options, method: 'GET' })
  },

  /**
   * Perform a POST request.
   */
  post: <T = unknown>(endpoint: string, data?: unknown, options?: RequestInit): Promise<T> => {
    return apiClientFetch<T>(endpoint, {
      ...options,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      body: data ? JSON.stringify(data) : undefined,
    })
  },

  /**
   * Perform a PUT request.
   */
  put: <T = unknown>(endpoint: string, data?: unknown, options?: RequestInit): Promise<T> => {
    return apiClientFetch<T>(endpoint, {
      ...options,
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      body: data ? JSON.stringify(data) : undefined,
    })
  },

  /**
   * Perform a PATCH request.
   */
  patch: <T = unknown>(endpoint: string, data?: unknown, options?: RequestInit): Promise<T> => {
    return apiClientFetch<T>(endpoint, {
      ...options,
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      body: data ? JSON.stringify(data) : undefined,
    })
  },

  /**
   * Perform a DELETE request.
   */
  delete: <T = unknown>(endpoint: string, options?: RequestInit): Promise<T> => {
    return apiClientFetch<T>(endpoint, { ...options, method: 'DELETE' })
  },
}

// Default export for backward compatibility
export default apiClientFetch
