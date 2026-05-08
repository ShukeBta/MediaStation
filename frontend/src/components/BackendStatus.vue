<script setup lang="ts">
import { backendOnline } from '@/api/client'
import { ref, watch } from 'vue'

const showBanner = ref(false)
let hideTimer: ReturnType<typeof setTimeout> | null = null

// 监听在线状态变化
watch(backendOnline, (online) => {
  if (!online) {
    // 后端离线，显示提示
    showBanner.value = true
    // 自动隐藏定时器（避免遮挡太久）
    if (hideTimer) clearTimeout(hideTimer)
    hideTimer = setTimeout(() => {
      showBanner.value = false
    }, 10000) // 10秒后自动隐藏
  } else {
    // 后端恢复，立即隐藏
    showBanner.value = false
    if (hideTimer) {
      clearTimeout(hideTimer)
      hideTimer = null
    }
  }
})

function dismiss() {
  showBanner.value = false
}
</script>

<template>
  <Transition name="slide-down">
    <div v-if="!backendOnline && showBanner" class="backend-offline-banner">
      <div class="banner-content">
        <span class="banner-icon">⚠️</span>
        <span class="banner-text">
          后端服务连接失败，正在自动重试...
        </span>
        <button class="banner-dismiss" @click="dismiss" title="关闭提示">
          ✕
        </button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.backend-offline-banner {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 9999;
  background: linear-gradient(90deg, #f59e0b, #d97706);
  color: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.banner-content {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 500;
}

.banner-icon {
  font-size: 18px;
}

.banner-text {
  flex: 1;
  text-align: center;
}

.banner-dismiss {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: white;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  transition: background 0.2s;
}

.banner-dismiss:hover {
  background: rgba(255, 255, 255, 0.3);
}

/* 过渡动画 */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease;
}

.slide-down-enter-from,
.slide-down-leave-to {
  transform: translateY(-100%);
  opacity: 0;
}
</style>
