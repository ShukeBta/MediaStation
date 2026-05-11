<template>
  <div class="file-tree">
    <!-- 加载指示 -->
    <div v-if="loading && !flatNodes.length" class="ft-loading">
      <span class="ft-spinner"></span>
      <span>加载中...</span>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!flatNodes.length && !loading" class="ft-empty">
      <span>暂无目录</span>
    </div>

    <!-- 虚拟滚动列表 -->
    <RecycleScroller
      v-else
      class="ft-scroller"
      :items="flatNodes"
      :item-size="32"
      key-field="path"
      v-slot="{ item }"
    >
      <div
        :style="{ paddingLeft: item.depth * 16 + 'px' }"
        :class="[
          'ft-node',
          { 'ft-node-active': item.path === currentPath }
        ]"
        @click="handleClick(item)"
      >
        <!-- 展开/折叠箭头 -->
        <span
          v-if="item.is_dir"
          :class="['ft-arrow', { 'ft-arrow-expanded': item.expanded }]"
          @click.stop="toggleExpand(item)"
        >
          ▶
        </span>
        <span v-else class="ft-file-icon">📄</span>

        <!-- 节点名称 -->
        <span class="ft-node-name">{{ item.name }}</span>
      </div>
    </RecycleScroller>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { RecycleScroller } from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
import { adminApi } from '@/api/admin'

interface TreeNode {
  name: string
  path: string
  is_dir: boolean
  children?: TreeNode[]
  expanded?: boolean
  loaded?: boolean
  depth?: number
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

// 将树结构打平为列表（仅包含展开的节点）
const flatNodes = computed(() => {
  const result: (TreeNode & { depth: number })[] = []
  
  function flatten(node: TreeNode, depth: number) {
    result.push({ ...node, depth })
    
    if (node.expanded && node.children) {
      for (const child of node.children) {
        flatten(child, depth + 1)
      }
    }
  }
  
  for (const node of nodes.value) {
    flatten(node, 0)
  }
  
  return result
})

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
          depth: 1,
        })),
        expanded: true,
        loaded: true,
        depth: 0,
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
        depth: 0,
      })
    }
  }
  loading.value = false
}

async function toggleExpand(item: TreeNode & { depth: number }) {
  if (!item.is_dir) return
  
  // 查找节点在原始树中的位置
  const node = findNode(nodes.value, item.path)
  if (!node) return
  
  if (!node.expanded) {
    // 展开节点
    if (!node.loaded) {
      // 首次展开，加载子目录
      try {
        const res = await adminApi.browseFiles(node.path)
        const items = res.data.data?.items || []
        const dirs = items.filter((i: any) => i.is_dir)
        
        node.children = dirs.map((d: any) => ({
          name: d.name,
          path: d.path,
          is_dir: true,
          children: undefined,
          expanded: false,
          loaded: false,
          depth: (node.depth || 0) + 1,
        }))
        node.loaded = true
      } catch (e) {
        console.error('Failed to load directory:', e)
      }
    }
    node.expanded = true
  } else {
    // 折叠节点
    node.expanded = false
  }
}

function findNode(nodes: TreeNode[], path: string): TreeNode | null {
  for (const node of nodes) {
    if (node.path === path) return node
    if (node.children) {
      const found = findNode(node.children, path)
      if (found) return found
    }
  }
  return null
}

function handleClick(item: TreeNode & { depth: number }) {
  if (item.is_dir) {
    emit('navigate', item.path)
  }
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
  height: 100%;
  overflow: hidden;
}

.ft-scroller {
  height: 100%;
  overflow-y: auto;
}

.ft-loading,
.ft-empty {
  padding: 16px;
  text-align: center;
  color: var(--text-muted);
}

.ft-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid var(--border-primary);
  border-top-color: var(--accent-primary);
  border-radius: 50%;
  animation: ft-spin 0.8s linear infinite;
}

@keyframes ft-spin {
  to { transform: rotate(360deg); }
}

.ft-node {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  cursor: pointer;
  border-radius: 4px;
  transition: background-color 0.15s;
  height: 32px;
}

.ft-node:hover {
  background-color: var(--bg-hover);
}

.ft-node-active {
  background-color: var(--accent-primary) + '20';
  color: var(--accent-primary);
}

.ft-arrow {
  display: inline-block;
  font-size: 10px;
  transition: transform 0.15s;
  user-select: none;
}

.ft-arrow-expanded {
  transform: rotate(90deg);
}

.ft-file-icon {
  font-size: 12px;
}

.ft-node-name {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
