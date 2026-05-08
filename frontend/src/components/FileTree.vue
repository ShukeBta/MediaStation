<template>
  <div class="file-tree">
    <!-- 加载指示 -->
    <div v-if="loading && !nodes.length" class="ft-loading">
      <span class="ft-spinner"></span>
      <span>加载中...</span>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!nodes.length && !loading" class="ft-empty">
      <span>暂无目录</span>
    </div>

    <!-- 树节点列表 -->
    <FileTreeNode
      v-for="node in nodes"
      :key="node.path"
      :node="node"
      :current-path="currentPath"
      :depth="0"
      @navigate="$emit('navigate', $event)"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import FileTreeNode from './FileTreeNode.vue'
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
  rootPaths: string[]
  currentPath: string
}>()

const emit = defineEmits<{
  (e: 'navigate', path: string): void
}>()

const nodes = ref<TreeNode[]>([])
const loading = ref(false)

async function buildRootNodes() {
  loading.value = true
  nodes.value = []

  for (const rootPath of props.rootPaths) {
    try {
      const res = await adminApi.browseFiles(rootPath)
      const items = res.data.data?.items || []
      const dirs = items.filter((i: any) => i.is_dir)

      const node: TreeNode = {
        name: rootPath.replace(/\\/g, '/').split('/').filter(Boolean).pop() || rootPath,
        path: rootPath,
        is_dir: true,
        children: dirs.map((d: any) => ({
          name: d.name,
          path: d.path,
          is_dir: true,
          children: undefined,
          expanded: false,
          loaded: false,
        })),
        expanded: true,
        loaded: true,
      }
      nodes.value.push(node)
    } catch {
      nodes.value.push({
        name: rootPath.split('/').filter(Boolean).pop() || rootPath,
        path: rootPath,
        is_dir: true,
        children: [],
        expanded: false,
        loaded: false,
      })
    }
  }
  loading.value = false
}

onMounted(() => {
  if (props.rootPaths.length > 0) {
    buildRootNodes()
  }
})

watch(() => props.rootPaths, (newPaths) => {
  if (newPaths.length > 0) buildRootNodes()
}, { deep: true })
</script>

<style scoped>
.file-tree {
  width: 100%;
  overflow-y: auto;
  overflow-x: hidden;
}
.ft-loading {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 8px;
  font-size: 12px;
  color: rgba(255,255,255,0.4);
}
.ft-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255,255,255,0.15);
  border-top-color: #60a5fa;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }
.ft-empty {
  padding: 12px 8px;
  font-size: 12px;
  color: rgba(255,255,255,0.3);
}
</style>
