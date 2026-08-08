// In local dev, Vite's proxy (vite.config.js) forwards /api and /ws to
// http://localhost:8000, so relative paths work with zero config.
//
// In production the frontend and backend are deployed separately (e.g.
// frontend on Vercel, backend on Render) and there's no proxy — set
// VITE_API_URL / VITE_WS_URL (in Vercel project settings, or a local
// .env.production) to the deployed backend's origin and the build will talk
// to it directly instead of falling back to the relative dev-proxy paths.
//
//   VITE_API_URL=https://kanea-backend.onrender.com
//   VITE_WS_URL=wss://kanea-backend.onrender.com

const API_URL = import.meta.env.VITE_API_URL
const WS_BASE = import.meta.env.VITE_WS_URL

export const API = API_URL || '/api'

export const WS_URL = (id) =>
  WS_BASE ? `${WS_BASE}/ws/${id}` : `ws://${window.location.host}/ws/${id}`
