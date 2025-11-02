import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  envPrefix: ['VITE_', 'PREFECT_', 'OPENLINEAGE_', 'HOTPASS_'],
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3001,
    fs: {
      allow: [
        path.resolve(__dirname),
        path.resolve(__dirname, '..', '..'),
      ],
    },
    proxy: {
      '/api/marquez': {
        target: process.env.OPENLINEAGE_URL || process.env.VITE_MARQUEZ_API_URL || 'http://localhost:5000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/marquez/, '/api/v1'),
      },
      '/api/prefect': {
        target: process.env.PREFECT_API_URL || process.env.VITE_PREFECT_API_URL || 'http://localhost:4200',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/prefect/, '/api'),
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 1024,
  },
})
