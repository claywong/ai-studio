import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/studio/',
  server: {
    port: 5173,
    proxy: {
      '/studio-api': {
        target: 'http://127.0.0.1:18081',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/studio-api/, ''),
      },
    },
  },
})
