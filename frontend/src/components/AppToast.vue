<template>
  <!-- Toast 通知容器 -->
  <Teleport to="body">
    <div class="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none max-w-sm w-full">
      <TransitionGroup name="toast">
        <div v-for="toast in toasts" :key="toast.id"
          :class="[
            'pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg border backdrop-blur-md',
            'animate-in',
            typeStyles[toast.type],
          ]"
          style="background: var(--bg-card-solid); color: var(--text-primary);">
          <!-- 图标 -->
          <div class="shrink-0">
            <!-- 成功 -->
            <svg v-if="toast.type === 'success'" class="w-5 h-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            <!-- 错误 -->
            <svg v-else-if="toast.type === 'error'" class="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            <!-- 警告 -->
            <svg v-else-if="toast.type === 'warning'" class="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"/>
            </svg>
            <!-- 信息 -->
            <svg v-else class="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
          </div>
          <!-- 消息 -->
          <p class="flex-1 text-sm leading-snug">{{ toast.message }}</p>
          <!-- 关闭 -->
          <button @click="removeToast(toast.id)"
            class="shrink-0 opacity-60 hover:opacity-100 transition-opacity">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
      </TransitionGroup>
    </div>

    <!-- 确认弹窗 -->
    <Transition name="modal">
      <div v-if="confirmState.show"
        class="fixed inset-0 z-[110] flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="resolveConfirm(false)" />
        <div class="relative w-full max-w-sm rounded-2xl shadow-2xl border p-6 space-y-4 animate-in"
          style="background: var(--bg-card-solid); border-color: var(--border-primary);"
          :style="confirmState.options.danger ? 'border-color: rgba(239,68,68,0.3)' : ''">
          <div>
            <h3 class="text-lg font-semibold" :class="confirmState.options.danger ? 'text-red-400' : ''" style="color: var(--text-primary)">
              {{ confirmState.options.title }}
            </h3>
            <p class="mt-2 text-sm leading-relaxed" style="color: var(--text-muted)">{{ confirmState.options.message }}</p>
          </div>
          <div class="flex justify-end gap-2">
            <button @click="resolveConfirm(false)" class="btn-secondary text-sm">
              {{ confirmState.options.cancelText }}
            </button>
            <button @click="resolveConfirm(true)"
              :class="confirmState.options.danger ? 'btn-danger' : 'btn-primary'"
              class="text-sm">
              {{ confirmState.options.confirmText }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
const { toasts, confirmState, removeToast, resolveConfirm } = useToast()
import { useToast } from '@/composables/useToast'

const typeStyles: Record<string, string> = {
  success: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-600 dark:text-emerald-300',
  error: 'bg-red-500/10 border-red-500/20 text-red-600 dark:text-red-300',
  warning: 'bg-amber-500/10 border-amber-500/20 text-amber-600 dark:text-amber-300',
  info: 'bg-blue-500/10 border-blue-500/20 text-blue-600 dark:text-blue-300',
}
</script>

<style scoped>
/* Toast 动画 */
.toast-enter-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.toast-leave-active {
  transition: all 0.2s ease-in;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(100%) scale(0.95);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(40px) scale(0.95);
}
.toast-move {
  transition: transform 0.3s ease;
}

/* Modal 动画 */
.modal-enter-active {
  transition: all 0.2s ease-out;
}
.modal-leave-active {
  transition: all 0.15s ease-in;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

/* 入场动画 */
.animate-in {
  animation: fadeScaleIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes fadeScaleIn {
  from {
    opacity: 0;
    transform: scale(0.95) translateY(4px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}
</style>
