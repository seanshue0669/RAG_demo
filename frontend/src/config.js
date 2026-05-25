// Centralised frontend configuration.
//
// API_BASE_URL is read from the Vite env var VITE_API_BASE_URL at build/dev
// time, falling back to the local FastAPI dev server. Components that call
// the backend should import API_BASE_URL from here rather than hardcoding
// the URL, so deployment targets can be changed via a single .env.local
// file.
//
// Default is an empty base URL so all requests go through relative paths
// like `/api/...`. The Vite dev server proxies `/api/*` to the backend
// (see vite.config.js), and in production the same-origin reverse proxy
// handles it. This makes the demo work when the browser and backend run
// on different hosts (e.g. SSH-tunnelled DGX access), since no absolute
// `http://localhost:8000` URL leaks into the browser.
//
// Override only if the frontend is served from a different origin than
// the backend and no proxy is in place, e.g. `VITE_API_BASE_URL=http://dgx.example.com:8000`.

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export default {
  API_BASE_URL,
};
