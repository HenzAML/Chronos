import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // Flask dev server (5001: macOS AirPlay Receiver owns 5000).
        target: 'http://127.0.0.1:5001',
        changeOrigin: true,
      },
    },
  },
})
