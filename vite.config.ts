import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/app/ai/',
  server: {
    port: 5173,
    proxy: {
      '/app/ai-api': {
        target: 'http://127.0.0.1:18081',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/app\/ai-api/, ''),
      },
    },
  },
})
