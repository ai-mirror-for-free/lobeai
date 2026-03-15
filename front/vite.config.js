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
    port: 5173,
    proxy: {
      // 直接代理到OpenWebUI服务器，保持路径不变
      '/api/v1': {
        target: 'https://chat.yang-sjq.cn', // 使用真实的OpenWebUI服务器地址
        changeOrigin: true,
        secure: false, // 如果是HTTPS但证书有问题，设为false
        rewrite: (path) => path // 不重写路径，保持原始路径
      },
      // 保留原有配置作为备用
      '/api': {
        target: 'https://chat.yang-sjq.cn',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path
      }
    }
  }
})