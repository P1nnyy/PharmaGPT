import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    allowedHosts: ['pharmagpt.co', 'api.pharmagpt.co', 'www.pharmagpt.co', 'local.pharmagpt.co', 'dev.pharmagpt.co', '.trycloudflare.com'],
    proxy: {
      '^/(auth|analyze-invoice|confirm-invoice|report|activity-log|inventory|history|invoices|static|export-excel)': {
        target: 'http://127.0.0.1:5001',
        changeOrigin: true
      }
    }
  }
})
