import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
    allowedHosts: [
      '.ngrok-free.dev',
      '.ngrok.io'
    ],
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true
      }
    },
    hmr: {
      protocol: 'ws',
      host: 'localhost'
    }
  },
  // 解决 Windows 文件锁定问题
  optimizeDeps: {
    force: true
  },
  // 清除缓存
  clearScreen: false
})

