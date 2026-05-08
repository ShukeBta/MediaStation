<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <!-- 遮罩 -->
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="closable && handleClose()" />
        <!-- 弹窗内容 -->
        <div class="relative w-full rounded-2xl overflow-hidden animate-in flex flex-col"
          :style="{ maxWidth: maxWidth, maxHeight: maxHeight, background: 'var(--bg-card-solid)', borderColor: 'var(--border-secondary)', boxShadow: 'var(--shadow-lg)', border: '1px solid var(--border-secondary)' }">
          <!-- 标题栏 -->
          <div v-if="title" class="flex items-center justify-between px-6 py-4 shrink-0" style="border-bottom: 1px solid var(--border-primary)">
            <h2 class="text-lg font-semibold text-[var(--text-primary)]">{{ title }}</h2>
            <button v-if="closable" @click="handleClose()"
              class="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors rounded-lg p-1" style="background: transparent" onmouseenter="this.style.background='var(--bg-hover)'" onmouseleave="this.style.background='transparent'">
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>
          <!-- 内容（可滚动） -->
          <div class="p-6 overflow-y-auto min-h-0">
            <slot />
          </div>
          <!-- 底部 -->
          <div v-if="$slots.footer" class="px-6 py-4 flex justify-end gap-2 shrink-0" style="border-top: 1px solid var(--border-primary)">
            <slot name="footer" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  show: boolean
  title?: string
  maxWidth?: string
  maxHeight?: string
  closable?: boolean
}>(), {
  title: '',
  maxWidth: '28rem',
  maxHeight: '90vh',
  closable: true,
})

const emit = defineEmits<{
  close: []
  'update:show': [value: boolean]
}>()

function handleClose() {
  emit('close')
  emit('update:show', false)
}
</script>

<style scoped>
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

.animate-in {
  animation: modalIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes modalIn {
  from {
    opacity: 0;
    transform: scale(0.95) translateY(8px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}
</style>
