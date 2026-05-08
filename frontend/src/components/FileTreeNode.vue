<template>
  <div class="ft-node" :style="{ paddingLeft: depth * 14 + 'px' }">
    <!-- 节点行 -->
    <div
      class="ft-node-row"
      :class="{ active: node.path === currentPath }"
      @click="handleClick"
    >
      <!-- 展开/折叠箭头 -->
      <span
        v-if="node.is_dir"
        class="ft-arrow"
        :class="{ expanded: isExpanded }"
        @click.stop="toggleExpand"
      >
        <svg viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"/>
        </svg>
      </span>
      <span v-else class="ft-arrow-placeholder"></span>

      <!-- 图标 -->
      <span class="ft-icon">
        <svg v-if="node.is_dir && isExpanded" viewBox="0 0 20 20" fill="currentColor">
          <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/>
        </svg>
        <svg v-else-if="node.is_dir" viewBox="0 0 20 20" fill="currentColor">
          <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/>
        </svg>
        <svg v-else viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd"/>
        </svg>
      </span>

      <!-- 名称 -->
      <span class="ft-name" :title="node.path">{{ node.name }}</span>

      <!-- 加载中指示 -->
      <span v-if="loadingChildren" class="ft-loading-dot"></span>
    </div>

    <!-- 子节点（展开状态） -->
    <div v-if="isExpanded && node.children">
      <div v-if="loadingChildren && !node.children.length" class="ft-loading-row" :style="{ paddingLeft: (depth + 1) * 14 + 8 + 'px' }">
        <span class="ft-spinner"></span>
        <span>加载中...</span>
      </div>
      <FileTreeNode
        v-for="child in node.children"
        :key="child.path"
        :node="child"
        :current-path="currentPath"
        :depth="depth + 1"
        @navigate="$emit('navigate', $event)"
      />
      <div v-if="!loadingChildren && !node.children.length" class="ft-empty-dir" :style="{ paddingLeft: (depth + 1) * 14 + 22 + 'px' }">
        空目录
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { adminApi } from '@/api/admin'

interface TreeNode {
  name: string
  path: string
  is_dir: boolean
  children?: TreeNode[]
  expanded?: boolean
  loaded?: boolean
}

const props = defineProps<{
  node: TreeNode
  currentPath: string
  depth: number
}>()

const emit = defineEmits<{
  (e: 'navigate', path: string): void
}>()

const isExpanded = ref(props.node.expanded || false)
const loadingChildren = ref(false)

async function loadChildren() {
  if (props.node.loaded) return
  loadingChildren.value = true
  try {
    const res = await adminApi.browseFiles(props.node.path)
    const items = res.data.data?.items || []
    props.node.children = items
      .filter((i: any) => i.is_dir)
      .map((i: any) => ({
        name: i.name,
        path: i.path,
        is_dir: true,
        children: undefined,
        expanded: false,
        loaded: false,
      }))
    props.node.loaded = true
  } catch {
    props.node.children = []
    props.node.loaded = true
  } finally {
    loadingChildren.value = false
  }
}

async function toggleExpand() {
  if (!props.node.is_dir) return
  isExpanded.value = !isExpanded.value
  if (isExpanded.value && !props.node.loaded) {
    await loadChildren()
  }
}

function handleClick() {
  emit('navigate', props.node.path)
  if (props.node.is_dir && !isExpanded.value) {
    toggleExpand()
  }
}

// 当外部 currentPath 变化时，自动展开包含当前路径的节点
watch(() => props.currentPath, (newPath) => {
  if (newPath && newPath.startsWith(props.node.path) && !isExpanded.value) {
    isExpanded.value = true
    if (!props.node.loaded) loadChildren()
  }
}, { immediate: true })
</script>

<style scoped>
.ft-node {
  user-select: none;
}
.ft-node-row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 6px 3px 0;
  border-radius: 5px;
  cursor: pointer;
  font-size: 12.5px;
  color: rgba(255,255,255,0.6);
  transition: all 0.1s;
  white-space: nowrap;
  overflow: hidden;
}
.ft-node-row:hover {
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.85);
}
.ft-node-row.active {
  background: rgba(96,165,250,0.15);
  color: #93c5fd;
}
.ft-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  color: rgba(255,255,255,0.35);
  transition: transform 0.15s;
}
.ft-arrow.expanded {
  transform: rotate(90deg);
}
.ft-arrow svg {
  width: 10px;
  height: 10px;
}
.ft-arrow-placeholder {
  width: 14px;
  flex-shrink: 0;
}
.ft-icon {
  display: flex;
  align-items: center;
  width: 15px;
  height: 15px;
  flex-shrink: 0;
  color: rgba(255,255,255,0.4);
}
.ft-node-row.active .ft-icon { color: #60a5fa; }
.ft-icon svg { width: 13px; height: 13px; }
.ft-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ft-loading-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #60a5fa;
  flex-shrink: 0;
  animation: pulse 1s ease-in-out infinite;
}
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
.ft-loading-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 0;
  font-size: 11px;
  color: rgba(255,255,255,0.3);
}
.ft-spinner {
  width: 10px;
  height: 10px;
  border: 1.5px solid rgba(255,255,255,0.15);
  border-top-color: #60a5fa;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }
.ft-empty-dir {
  font-size: 11px;
  color: rgba(255,255,255,0.25);
  padding: 2px 0;
}
</style>
