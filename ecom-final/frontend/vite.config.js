import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // Proxy tất cả /api/* → Nginx Gateway (port 80)
      '/api': {
        target: 'http://localhost:80',
        changeOrigin: true,
      }
    }
  }
})
