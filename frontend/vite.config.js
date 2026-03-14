import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', 
    port: 5173,
    allowedHosts: ['pharmagpt.co', 'api.pharmagpt.co', 'www.pharmagpt.co', 'local.pharmagpt.co', 'dev.pharmagpt.co', '.trycloudflare.com'],
    hmr: {
      clientPort: 443 // Force HMR to use HTTPS port 443 (Client -> Cloudflared -> Vite)
    },
    proxy: {
      '/auth': 'http://backend:5001',
      '/products': 'http://backend:5001',
      '/invoices': 'http://backend:5001',
      '/reporting': 'http://backend:5001',
      '/inventory': 'http://backend:5001',
      '/system': 'http://backend:5001',
      '/config': 'http://backend:5001',
      '/feedback': 'http://backend:5001',
      '/activity-log': 'http://backend:5001',
      '/history': 'http://backend:5001',
      '/export-excel': 'http://backend:5001'
    }
  }
})
