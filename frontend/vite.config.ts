import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // SSE 事件流：需要禁用响应缓冲，保持长连接
      '/api/system/events': {
        target: 'http://localhost:3001',
        changeOrigin: true,
        // 关闭压缩，避免 SSE 数据被缓冲
        headers: { 'Accept-Encoding': 'identity' },
      },
      '/api': {
        target: 'http://localhost:3001',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:3001',
        changeOrigin: true,
      },
      '/api/health': {
        target: 'http://localhost:3001',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    // 提高警告阈值，避免控制台大量警告干扰
    chunkSizeWarningLimit: 1000,
    // 分包策略配置
    rollupOptions: {
      output: {
        // 手动分包策略 - 拆分为更小的块以利用 HTTP/2 并行加载
        manualChunks(id) {
          // Vue 全家桶：核心框架独立打包
          if (
            id.includes('node_modules/vue/') ||
            id.includes('node_modules/@vue/') ||
            id.includes('node_modules/pinia') ||
            id.includes('node_modules/vue-router')
          ) {
            return 'vue-vendor'
          }
          
          // 工具库：VueUse 等工具函数
          if (
            id.includes('node_modules/@vueuse') ||
            id.includes('node_modules/axios')
          ) {
            return 'utils-vendor'
          }
          
          // 可视化图表库：ECharts（体积较大）
          if (
            id.includes('node_modules/echarts') ||
            id.includes('node_modules/vue-echarts') ||
            id.includes('node_modules/zrender')
          ) {
            return 'echarts-vendor'
          }
          
          // 媒体播放器：HLS.js 和虚拟滚动
          if (
            id.includes('node_modules/hls.js') ||
            id.includes('node_modules/vue-virtual-scroller')
          ) {
            return 'media-vendor'
          }
          
          // UI 图标库
          if (id.includes('node_modules/@iconify')) {
            return 'icons-vendor'
          }
          
          // 其他第三方库（TailwindCSS、PostCSS 等不应进入 vendor）
          if (id.includes('node_modules')) {
            return 'vendor'
          }
        },
        // 块文件命名模板
        chunkFileNames: 'assets/js/[name]-[hash].js',
        entryFileNames: 'assets/js/[name]-[hash].js',
        assetFileNames: 'assets/[ext]/[name]-[hash].[ext]',
      },
    },
  },
  // 优化配置
  optimizeDeps: {
    // 预构建依赖项
    include: [
      'vue',
      'vue-router',
      'pinia',
      'axios',
      'echarts',
      'vue-echarts',
      'hls.js',
    ],
  },
})
