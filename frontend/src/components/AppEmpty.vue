<template>
  <div class="flex flex-col items-center justify-center py-16 text-center">
    <div class="w-16 h-16 rounded-2xl flex items-center justify-center mb-4" style="background: var(--bg-hover)">
      <!-- 默认空盒子图标 -->
      <svg v-if="!icon" class="w-8 h-8" style="color: var(--text-faint)" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
          d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>
      </svg>
      <!-- 自定义 slot -->
      <slot name="icon" />
    </div>
    <p class="text-sm" style="color: var(--text-muted)">{{ message }}</p>
    <div v-if="$slots.action" class="mt-4">
      <slot name="action" />
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  message?: string
  icon?: boolean
}>(), {
  message: '暂无数据',
  icon: false,
})
</script>
