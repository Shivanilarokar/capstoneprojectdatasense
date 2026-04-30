import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "^/admin/(overview|access/.*)$": "http://127.0.0.1:8002",
      "^/auth/me$": "http://127.0.0.1:8002",
      "/google": "http://127.0.0.1:8002",
      "/health": "http://127.0.0.1:8002",
      "^/query/ask$": "http://127.0.0.1:8002",
      "^/tenants/me$": "http://127.0.0.1:8002",
    },
  },
})
