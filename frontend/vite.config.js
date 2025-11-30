import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    watch: {
      usePolling: true,
    },
    host: true,
    allowedHosts: true,
    strictPort: true,
    port: 5173,
    proxy: {
      '/socket.io': {
        target: process.env.API_PROXY_TARGET || process.env.VITE_API_TARGET || 'http://localhost:5000',
        ws: true,
        changeOrigin: true
      },
      '/api': {
        target: process.env.API_PROXY_TARGET || process.env.VITE_API_TARGET || 'http://localhost:5000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    emptyOutDir: true,
  }
})
