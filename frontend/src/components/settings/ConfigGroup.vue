<template>
  <div class="border border-[var(--border-primary)] rounded-lg overflow-hidden">
    <!-- 分组标题 -->
    <button
      @click="expanded = !expanded"
      class="w-full flex items-center justify-between px-4 py-3 bg-[var(--bg-secondary)] hover:bg-[var(--bg-hover)] transition-colors"
    >
      <div class="flex items-center gap-2">
        <Icon :icon="icon" class="text-lg text-primary" />
        <span class="font-medium">{{ title }}</span>
        <span class="text-xs px-2 py-0.5 rounded-full" :style="{ background: 'var(--bg-tertiary)' }">
          {{ count }}
        </span>
      </div>
      <Icon
        :icon="expanded ? 'ph:caret-up' : 'ph:caret-down'"
        class="text-sm transition-transform"
      />
    </button>

    <!-- 分组内容 -->
    <div v-show="expanded" class="divide-y divide-[var(--border-primary)]">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Icon } from '@iconify/vue'

const props = withDefaults(defineProps<{
  title: string
  icon?: string
  defaultExpanded?: boolean
}>(), {
  icon: 'ph:folder',
  defaultExpanded: true,
})

const expanded = ref(props.defaultExpanded)

// 统计子元素数量
const count = computed(() => {
  // 通过 slot 中的 ConfigRow 数量
  return 0 // 简化处理
})
</script>
