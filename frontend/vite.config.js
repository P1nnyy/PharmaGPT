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
      // Use 443 for Cloudflare Tunnel, but allow fallback for local dev
      clientPort: process.env.VITE_CLIENT_PORT ? parseInt(process.env.VITE_HMR_PORT) : (process.env.DOCKER_ENV ? 443 : 5173)
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
