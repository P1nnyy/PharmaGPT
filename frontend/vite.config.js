import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
console.log('VITE_CONFIG: DOCKER_ENV =', process.env.DOCKER_ENV);
console.log('VITE_CONFIG: VITE_CLIENT_PORT =', process.env.VITE_CLIENT_PORT);

export default defineConfig({
  mode: 'development',
  plugins: [react()],
  resolve: {
    dedupe: ['react', 'react-dom'],
    alias: {
      'react': path.resolve(__dirname, './node_modules/react'),
      'react-dom': path.resolve(__dirname, './node_modules/react-dom')
    }
  },
  server: {
    host: '0.0.0.0', 
    port: 3000,
    strictPort: true,
    allowedHosts: true,
    hmr: {
      clientPort: 443,
      protocol: 'wss'
    },
    proxy: {
      '/auth': process.env.DOCKER_ENV === 'true' ? 'http://backend:5005' : 'http://127.0.0.1:5005',
      '/products': process.env.DOCKER_ENV === 'true' ? 'http://backend:5005' : 'http://127.0.0.1:5005',
      '/invoices': process.env.DOCKER_ENV === 'true' ? 'http://backend:5005' : 'http://127.0.0.1:5005',
      '/reporting': process.env.DOCKER_ENV === 'true' ? 'http://backend:5005' : 'http://127.0.0.1:5005',
      '/inventory': process.env.DOCKER_ENV === 'true' ? 'http://backend:5005' : 'http://127.0.0.1:5005',
      '/system': process.env.DOCKER_ENV === 'true' ? 'http://backend:5005' : 'http://127.0.0.1:5005',
      '/config': process.env.DOCKER_ENV === 'true' ? 'http://backend:5005' : 'http://127.0.0.1:5005',
      '/feedback': process.env.DOCKER_ENV === 'true' ? 'http://backend:5005' : 'http://127.0.0.1:5005',
      '/activity-log': process.env.DOCKER_ENV === 'true' ? 'http://backend:5005' : 'http://127.0.0.1:5005',
      '/history': process.env.DOCKER_ENV === 'true' ? 'http://backend:5005' : 'http://127.0.0.1:5005',
      '/export-excel': process.env.DOCKER_ENV === 'true' ? 'http://backend:5005' : 'http://127.0.0.1:5005',
      '/invitations': process.env.DOCKER_ENV === 'true' ? 'http://backend:5005' : 'http://127.0.0.1:5005'
    }
  }
})
