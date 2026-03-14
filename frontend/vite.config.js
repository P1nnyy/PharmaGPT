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
    }
  }
})
