import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    allowedHosts: ['pharmagpt.co', 'api.pharmagpt.co', 'www.pharmagpt.co', 'local.pharmagpt.co', 'dev.pharmagpt.co', '.trycloudflare.com'],
    hmr: {
      clientPort: 443 // Force HMR to use HTTPS port 443 (Client -> Cloudflared -> Vite)
    },
    proxy: {
      '^/(auth|analyze-invoice|confirm-invoice|report|activity-log|inventory|history|invoices|static|export-excel|products|feedback)': {
        target: 'http://127.0.0.1:5001',
        changeOrigin: true,
        secure: false
      }
    }
  }
})
