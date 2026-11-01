import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Production is served under /pimp-city/ by bot.py (staff-gated).
// Dev proxies snapshot to the localhost bridge (bridge.py).
export default defineConfig({
  plugins: [react()],
  base: '/pimp-city/',
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api/pimp-trading.json': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: false,
      },
    },
  },
})
