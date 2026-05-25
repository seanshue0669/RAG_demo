import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite config for the Cloud RAG Security Demo frontend.
// - React plugin enables JSX/Fast Refresh.
// - Dev server runs on port 5173.
// - /api is proxied to the FastAPI backend at http://localhost:8000 so the
//   browser does not need to deal with CORS during development. Components
//   may also import API_BASE_URL from src/config.js when calling the backend
//   directly (e.g. for non-/api paths).
export default defineConfig({
  plugins: [react()],
  server: {
    // Bind localhost only. External access is provided exclusively through
    // the cloudflared tunnel (which connects from the same host). This keeps
    // the dev server off the LAN and minimizes attack surface.
    host: '127.0.0.1',
    port: 5173,
    strictPort: false,
    // Cloudflared proxies the request with the *.trycloudflare.com Host
    // header. Vite 5 rejects unknown Host headers by default; allow the
    // tunnel domain (and localhost for direct testing).
    allowedHosts: ['.trycloudflare.com', 'localhost', '127.0.0.1'],
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
