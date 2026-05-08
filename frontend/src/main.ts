import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')

// ---- 全局图片加载失败处理 ----
// 拦截所有图片加载错误，自动替换为占位符
document.addEventListener('error', (e) => {
  const target = e.target as HTMLElement
  if (target && target.tagName === 'IMG') {
    const img = target as HTMLImageElement
    // 避免无限循环：如果已经是占位符，不再替换
    if (!img.src.includes('placeholder.svg')) {
      img.src = '/placeholder.svg'
    }
  }
}, true) // 使用捕获阶段，确保能捕获到所有图片错误
