<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-sm" style="color: var(--text-muted)">配置 qBittorrent / Transmission / Aria2 下载客户端</p>
      <button @click="openModal()" class="btn-primary text-sm flex items-center gap-1">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
        添加客户端
      </button>
    </div>

    <div class="space-y-3">
      <div v-for="client in clients" :key="client.id" class="card p-4">
        <div class="flex items-start justify-between">
          <div class="space-y-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="font-medium">{{ client.name }}</span>
              <span :class="[
                'text-xs px-2 py-0.5 rounded font-medium',
                clientTypeClass(client.client_type),
              ]">{{ clientTypeLabel(client.client_type) }}</span>
            </div>
            <div class="text-xs" style="color: var(--text-muted)">{{ client.host }}:{{ client.port }}</div>
            <div v-if="client.client_type === 'aria2' && aria2Stats[client.id]" class="text-xs mt-1 flex gap-3" style="color: var(--text-muted)">
              <span>⬇ {{ formatSpeed(aria2Stats[client.id].downloadSpeed) }}</span>
              <span>⬆ {{ formatSpeed(aria2Stats[client.id].uploadSpeed) }}</span>
              <span>活跃: {{ aria2Stats[client.id].numActive }}</span>
            </div>
          </div>
          <div class="flex items-center gap-1 shrink-0 ml-2">
            <button v-if="client.client_type === 'aria2'" @click="loadAria2Stats(client.id)" :disabled="statsLoadingId === client.id"
              class="btn-secondary text-xs disabled:opacity-50">
              {{ statsLoadingId === client.id ? '...' : '统计' }}
            </button>
            <button @click="testClient(client.id)" :disabled="testingId === client.id"
              class="btn-secondary text-xs disabled:opacity-50">
              {{ testingId === client.id ? '测试中...' : '测试连接' }}
            </button>
            <button @click="openModal(client)"
              class="p-1.5 rounded-lg transition-colors hover:bg-[var(--bg-hover)]" style="color: var(--text-muted)">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
            </button>
            <button @click="confirmDelete(client)"
              class="p-1.5 rounded-lg transition-colors hover:bg-red-500/10 hover:text-red-400" style="color: var(--text-muted)">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <AppEmpty v-if="clients.length === 0" message="暂无下载客户端" />

    <!-- 弹窗：移除不存在的 :wide prop，改用 :maxWidth -->
    <AppModal v-model:show="modal.show" :title="modal.editing ? '编辑客户端' : '添加下载客户端'" maxWidth="42rem">
      <div class="space-y-4">
        <div>
          <label class="block text-sm mb-1" style="color: var(--text-muted)">名称</label>
          <input v-model="modal.name" placeholder="例如: NAS-Aria2" class="input" />
        </div>
        <div>
          <label class="block text-sm mb-1" style="color: var(--text-muted)">类型</label>
          <select v-model="modal.client_type" class="input" @change="onTypeChange">
            <option value="qbittorrent">qBittorrent</option>
            <option value="transmission">Transmission</option>
            <option value="aria2">Aria2 (JSON-RPC)</option>
          </select>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-sm mb-1" style="color: var(--text-muted)">{{ hostLabel }}</label>
            <input v-model="modal.host" :placeholder="hostPlaceholder" class="input" />
          </div>
          <div>
            <label class="block text-sm mb-1" style="color: var(--text-muted)">端口</label>
            <input v-model.number="modal.port" :placeholder="portPlaceholder" class="input" type="number" />
          </div>
        </div>
        <div v-if="modal.client_type !== 'aria2'">
          <label class="block text-sm mb-1" style="color: var(--text-muted)">用户名（可选）</label>
          <input v-model="modal.username" class="input" />
        </div>
        <div>
          <label class="block text-sm mb-1" style="color: var(--text-muted)">{{ passwordLabel }}</label>
          <input v-model="modal.password" type="password" class="input" />
          <p v-if="modal.client_type === 'aria2'" class="mt-1 text-xs" style="color: var(--text-muted)">
            Aria2 的 RPC Secret Token（在 aria2.conf 中 --rpc-secret 设置）
          </p>
        </div>
        <div>
          <label class="block text-sm mb-1" style="color: var(--text-muted)">分类/保存目录（可选）</label>
          <input v-model="modal.save_path" placeholder="/downloads" class="input" />
        </div>
      </div>
      <template #footer>
        <button @click="modal.show = false" class="btn-secondary text-sm">取消</button>
        <button @click="save" class="btn-primary text-sm">保存</button>
      </template>
    </AppModal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { downloadApi } from '@/api/download'
import { useToast } from '@/composables/useToast'
import AppModal from '@/components/AppModal.vue'
import AppEmpty from '@/components/AppEmpty.vue'

const toast = useToast()
const clients = ref<any[]>([])
const testingId = ref<number | null>(null)
const statsLoadingId = ref<number | null>(null)
const aria2Stats = reactive<Record<number, any>>({})

const modal = ref({
  show: false, editing: null as any,
  name: '', client_type: 'qbittorrent', host: '', port: 8080,
  username: '', password: '', save_path: '',
})

// 动态标签
const hostLabel = computed(() => {
  switch (modal.value.client_type) {
    case 'aria2': return 'RPC 地址'
    case 'transmission': return '主机地址'
    default: return '主机地址'
  }
})
const hostPlaceholder = computed(() => {
  return modal.value.client_type === 'aria2' ? 'http://192.168.1.100' : '192.168.1.100'
})
const portPlaceholder = computed(() => {
  return modal.value.client_type === 'aria2' ? '6800' : '8080'
})
const passwordLabel = computed(() => {
  return modal.value.client_type === 'aria2' ? 'RPC Secret Token' : '密码'
})

function clientTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    qbittorrent: 'qBittorrent',
    transmission: 'Transmission',
    aria2: 'Aria2',
  }
  return labels[type] || type
}

function clientTypeClass(type: string): string {
  const classes: Record<string, string> = {
    qbittorrent: 'bg-blue-500/10 text-blue-400',
    transmission: 'bg-green-500/10 text-green-400',
    aria2: 'bg-purple-500/10 text-purple-400',
  }
  return classes[type] || 'bg-gray-500/10 text-gray-400'
}

function formatSpeed(bytesPerSec: number): string {
  if (!bytesPerSec) return '0 B/s'
  if (bytesPerSec < 1024) return `${bytesPerSec} B/s`
  if (bytesPerSec < 1048576) return `${(bytesPerSec / 1024).toFixed(1)} KB/s`
  return `${(bytesPerSec / 1048576).toFixed(1)} MB/s`
}

function onTypeChange() {
  // 切换类型时自动调整默认端口和清空不相关字段
  if (modal.value.client_type === 'aria2') {
    modal.value.port = 6800
    modal.value.username = ''
  } else if (modal.value.client_type === 'qbittorrent') {
    modal.value.port = 8080
  } else {
    modal.value.port = 9091
  }
}

function openModal(client?: any) {
  modal.value = client
    ? {
        show: true, editing: client,
        name: client.name, client_type: client.client_type,
        host: client.host, port: client.port,
        username: client.username || '', password: '',
        save_path: client.save_path || '',
      }
    : {
        show: true, editing: null,
        name: '', client_type: 'qbittorrent', host: '',
        port: 8080, username: '', password: '', save_path: '',
      }
}

async function save() {
  try {
    const payload: any = {
      name: modal.value.name, client_type: modal.value.client_type,
      host: modal.value.host, port: modal.value.port,
      category: modal.value.save_path || undefined,
    }
    // Aria2 不传 username，用 password 当 secret
    if (modal.value.client_type !== 'aria2') {
      payload.username = modal.value.username || undefined
    }
    if (modal.value.password) {
      payload.password = modal.value.password
    }

    if (modal.value.editing) {
      await downloadApi.updateClient(modal.value.editing.id, payload)
    } else {
      await downloadApi.createClient(payload)
    }
    modal.value.show = false
    toast.success('保存成功')
    await loadClients()
  } catch (e: any) {
    toast.error(`保存失败: ${e.response?.data?.detail || e.message}`)
  }
}

async function testClient(id: number) {
  testingId.value = id
  try {
    await downloadApi.testClient(id)
    toast.success('连接测试成功！')
  } catch (e: any) {
    toast.error(`连接测试失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    testingId.value = null
  }
}

async function loadAria2Stats(id: number) {
  statsLoadingId.value = id
  try {
    const { data } = await downloadApi.getAria2Stats(id)
    aria2Stats[id] = data
  } catch (e: any) {
    toast.error(`获取统计失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    statsLoadingId.value = null
  }
}

async function confirmDelete(client: any) {
  const ok = await toast.confirm({
    title: '删除下载客户端',
    message: `确定要删除客户端「${client.name}」吗？`,
    confirmText: '删除',
    danger: true,
  })
  if (!ok) return
  try {
    await downloadApi.deleteClient(client.id)
    delete aria2Stats[client.id]
    toast.success('已删除')
    await loadClients()
  } catch (e: any) {
    toast.error(`删除失败: ${e.response?.data?.detail || e.message}`)
  }
}

async function loadClients() {
  try {
    const { data } = await downloadApi.getClients()
    clients.value = Array.isArray(data) ? data : data.items || []
  } catch (e) {
    console.error('加载客户端失败:', e)
  }
}

onMounted(() => loadClients())
</script>
