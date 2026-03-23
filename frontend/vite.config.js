import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
console.log('VITE_CONFIG: DOCKER_ENV =', process.env.DOCKER_ENV);
console.log('VITE_CONFIG: VITE_CLIENT_PORT =', process.env.VITE_CLIENT_PORT);

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', 
    port: 5174,
    allowedHosts: ['pharmagpt.co', 'api.pharmagpt.co', 'www.pharmagpt.co', 'local.pharmagpt.co', 'dev.pharmagpt.co', '.trycloudflare.com'],
    hmr: {
      // Use 443 for Cloudflare Tunnel/Proxies, 
      // but only if we are in a DOCKER_ENV or accessing via a public domain.
      clientPort: process.env.VITE_CLIENT_PORT ? parseInt(process.env.VITE_CLIENT_PORT) : (process.env.DOCKER_ENV ? 443 : 5173),
      protocol: process.env.DOCKER_ENV ? 'wss' : 'ws'
    },
    proxy: {
      '/auth': 'http://127.0.0.1:5005',
      '/products': 'http://127.0.0.1:5005',
      '/invoices': 'http://127.0.0.1:5005',
      '/reporting': 'http://127.0.0.1:5005',
      '/inventory': 'http://127.0.0.1:5005',
      '/system': 'http://127.0.0.1:5005',
      '/config': 'http://127.0.0.1:5005',
      '/feedback': 'http://127.0.0.1:5005',
      '/activity-log': 'http://127.0.0.1:5005',
      '/history': 'http://127.0.0.1:5005',
      '/export-excel': 'http://127.0.0.1:5005',
      '/invitations': 'http://127.0.0.1:5005'
    }
  }
})
