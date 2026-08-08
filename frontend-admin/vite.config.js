import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,           // listen on 0.0.0.0 — accessible from any device on the network
    port: 5174,
    strictPort: true,
    historyApiFallback: true,
    proxy: {
      '/ws': { target: 'ws://localhost:8000', ws: true, changeOrigin: true },
      '/api': { target: 'http://localhost:8000', rewrite: p => p.replace(/^\/api/, ''), changeOrigin: true }
    }
  }
})

