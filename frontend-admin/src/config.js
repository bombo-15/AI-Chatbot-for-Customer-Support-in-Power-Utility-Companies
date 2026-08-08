// All API calls go through the Vite dev-server proxy.
// /api/*  → http://localhost:8000/*   (REST)
// This works from any device/IP because Vite proxies server-side.

export const API = '/api'

const TOKEN_KEY = 'kanea_admin_token'

/**
 * Authenticated fetch — attaches Bearer token to every admin request.
 * Replaces plain fetch() in all admin components.
 */
export function adminFetch(url, options = {}) {
  const token = sessionStorage.getItem(TOKEN_KEY) || ''
  return fetch(url, {
    ...options,
    headers: { ...(options.headers || {}), Authorization: `Bearer ${token}` },
  })
}

