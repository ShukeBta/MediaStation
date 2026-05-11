<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6 animate-in">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-[var(--text-primary)]">下载管理</h1>
      <div class="flex gap-2">
        <button @click="syncTasks" :disabled="syncing" class="btn-secondary flex items-center gap-2 text-sm">
          <svg :class="['w-4 h-4', syncing && 'animate-spin']" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
          同步
        </button>
        <button @click="organizeAllCompleted" :disabled="organizing" class="btn-secondary flex items-center gap-2 text-sm"
          :class="completedCount > 0 ? 'border-emerald-500/30 text-emerald-400 dark:text-emerald-300' : 'opacity-40'">
          <svg :class="['w-4 h-4', organizing && 'animate-pulse']" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 13h6m3 0V9a3 3 0 00-3-3H6a3 3 0 00-3 3v12a3 3 0 003 3h12a3 3 0 003-3v-3z"/></svg>
          整理入库
        </button>
        <button @click="showAddTask = true" class="btn-primary flex items-center gap-2 text-sm">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
          添加任务
        </button>
      </div>
    </div>

    <!-- 整理状态提示 -->
    <div v-if="organizeResult" class="rounded-lg p-3 text-sm flex items-center gap-2"
      :style="{ background: organizeResult.errors > 0 ? 'var(--error-subtle)' : 'var(--accent-subtle)', color: organizeResult.errors > 0 ? 'var(--error)' : 'var(--accent-hover)' }">
      <svg v-if="!organizeResult.errors" class="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
      <svg v-else class="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
      整理结果: {{ organizeResult.organized }} 个文件已入库, {{ organizeResult.skipped }} 个跳过
      <span v-if="organizeResult.errors > 0">, {{ organizeResult.errors }} 个错误</span>
    </div>

    <!-- 下载客户端状态 -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 stagger-in" :style="{ '--stagger': 50 }">
      <div v-for="client in clients" :key="client.id" class="card p-4">
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-2">
            <span :class="[
              'w-2 h-2 rounded-full',
              client.status === 'active' ? 'bg-[var(--success)]' : 'bg-[var(--text-faint)]',
            ]" />
            <span class="font-medium text-sm text-[var(--text-primary)]">{{ client.name }}</span>
          </div>
          <span class="text-xs px-2 py-0.5 rounded" style="color: var(--text-muted); background: var(--bg-input)">{{ client.client_type }}</span>
        </div>
        <div class="text-xs text-[var(--text-muted)]">{{ client.host }}:{{ client.port }}</div>
      </div>
      <div v-if="clients.length === 0" class="col-span-full">
        <AppEmpty message="暂无下载客户端，请先在设置中添加" />
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="flex items-center gap-3 flex-wrap">
      <button v-for="filter in statusFilters" :key="filter.value"
        @click="activeFilter = filter.value"
        :class="[
          'px-3 py-1.5 rounded-lg text-sm transition-colors',
          activeFilter === filter.value
            ? 'text-[var(--accent-hover)]'
            : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]',
        ]"
        :style="activeFilter === filter.value ? { background: 'var(--accent-subtle)' } : {}">
        {{ filter.label }}
        <span v-if="filter.count !== undefined" class="ml-1 opacity-60">({{ filter.count }})</span>
      </button>
    </div>

    <!-- 任务列表 -->
    <div class="space-y-2 stagger-in" :style="{ '--stagger': 30 }">
      <div v-for="task in filteredTasks" :key="task.id" class="card p-4 transition-colors">
        <div class="flex items-start gap-4">
          <!-- 状态图标 -->
          <div class="mt-0.5">
            <svg v-if="task.status === 'downloading'" class="w-5 h-5 animate-pulse" style="color: var(--accent-hover)" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
            <svg v-else-if="task.status === 'completed'" class="w-5 h-5" style="color: var(--success)" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
            <svg v-else-if="task.status === 'paused'" class="w-5 h-5" style="color: var(--warning)" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            <svg v-else-if="task.status === 'error'" class="w-5 h-5" style="color: var(--error)" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            <svg v-else class="w-5 h-5 text-[var(--text-muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4"/></svg>
          </div>

          <!-- 任务信息 -->
          <div class="flex-1 min-w-0">
            <div class="font-medium text-sm truncate text-[var(--text-primary)]">{{ task.torrent_name || task.name || '未知任务' }}</div>
            <div class="flex items-center gap-3 mt-1 text-xs text-[var(--text-muted)] flex-wrap">
              <span v-if="task.total_size">{{ formatFileSize(task.total_size) }}</span>
              <!-- 使用 downloaded（后端字段）而非 downloaded_size -->
              <span v-if="task.downloaded && task.total_size">
                已下载 {{ formatFileSize(task.downloaded) }} ({{ getProgressPct(task) }}%)
              </span>
              <span v-if="task.speed && task.status === 'downloading'" style="color: var(--success)">{{ formatSpeed(task.speed) }}</span>
              <span v-if="task.seeders != null && task.seeders > 0">做种 {{ task.seeders }}</span>
              <!-- 整理标记 -->
              <span v-if="isOrganized(task)" class="px-1.5 py-0.5 rounded text-emerald-600 dark:text-emerald-300 bg-emerald-500/10 text-xs">
                已入库
              </span>
            </div>

            <!-- 进度条：下载中才显示，使用 progress 字段（0-100） -->
            <div v-if="task.status === 'downloading'" class="progress-bar mt-2">
              <div :style="{ width: getProgressPct(task) + '%' }" />
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="flex items-center gap-1 shrink-0">
            <!-- 已完成任务显示整理按钮 -->
            <button v-if="task.status === 'completed'" @click="organizeSingleTask(task.id)" title="整理入库"
              class="p-1.5 rounded-lg transition-colors text-[var(--text-muted)] hover:text-emerald-500" style="background: transparent" onmouseenter="this.style.background='var(--bg-hover)'" onmouseleave="this.style.background='transparent'">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 13h6m3 0V9a3 3 0 00-3-3H6a3 3 0 00-3 3v12a3 3 0 003 3h12a3 3 0 003-3v-3z"/></svg>
            </button>
            <button v-if="task.status === 'downloading'" @click="pauseTask(task.id)" title="暂停"
              class="p-1.5 rounded-lg transition-colors text-[var(--text-muted)] hover:text-[var(--warning)]" style="background: transparent" onmouseenter="this.style.background='var(--bg-hover)'" onmouseleave="this.style.background='transparent'">
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
            </button>
            <button v-if="task.status === 'paused'" @click="resumeTask(task.id)" title="继续"
              class="p-1.5 rounded-lg transition-colors text-[var(--text-muted)] hover:text-[var(--success)]" style="background: transparent" onmouseenter="this.style.background='var(--bg-hover)'" onmouseleave="this.style.background='transparent'">
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
            </button>
            <button @click="handleDelete(task)" title="删除"
              class="p-1.5 rounded-lg transition-colors text-[var(--text-muted)] hover:text-[var(--error)]" style="background: transparent" onmouseenter="this.style.background='var(--bg-hover)'" onmouseleave="this.style.background='transparent'">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
            </button>
          </div>
        </div>
      </div>

      <div v-if="filteredTasks.length === 0">
        <AppEmpty :message="activeFilter === 'all' ? '暂无下载任务' : `暂无${statusFilters.find(f => f.value === activeFilter)?.label}的任务`" />
      </div>
    </div>

    <!-- 添加任务弹窗 -->
    <AppModal :show="showAddTask" title="添加下载任务" @close="showAddTask = false">
      <div class="space-y-4">
        <div>
          <label class="block text-sm text-[var(--text-muted)] mb-1">下载链接 / 磁力链接</label>
          <textarea v-model="newTaskUrl" rows="3" placeholder="支持 magnet: 链接、.torrent 文件 URL、种子文件"
            class="input resize-none" />
        </div>

        <div v-if="clients.length > 1">
          <label class="block text-sm text-[var(--text-muted)] mb-1">下载客户端</label>
          <select v-model="newTaskClient" class="input">
            <option v-for="c in clients" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </div>

        <div>
          <label class="block text-sm text-[var(--text-muted)] mb-1">保存目录（可选）</label>
          <input v-model="newTaskSavePath" placeholder="默认使用客户端配置的目录" class="input" />
        </div>
      </div>
      <template #footer>
        <div class="flex justify-end gap-2 pt-2">
          <button @click="showAddTask = false" class="btn-secondary text-sm">取消</button>
          <button @click="addTask" :disabled="!newTaskUrl.trim()" class="btn-primary text-sm disabled:opacity-50">添加</button>
        </div>
      </template>
    </AppModal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { downloadApi } from '@/api/download'
import { useFormat } from '@/composables/useFormat'
import { useSSE } from '@/composables/useSSE'
import { useToast } from '@/composables/useToast'
import AppModal from '@/components/AppModal.vue'
import AppEmpty from '@/components/AppEmpty.vue'

const { formatFileSize, formatSpeed } = useFormat()
const { connect: connectSSE, disconnect: disconnectSSE, getEventsByType } = useSSE()
const toast = useToast()

// 数据
const clients = ref<any[]>([])
const tasks = ref<any[]>([])
const activeFilter = ref('all')
const syncing = ref(false)
const organizing = ref(false)
const loading = ref(true)

// 整理结果
const organizeResult = ref<{ organized: number; skipped: number; errors: number } | null>(null)

// 添加任务
const showAddTask = ref(false)
const newTaskUrl = ref('')
const newTaskClient = ref<number | null>(null)
const newTaskSavePath = ref('')

// 计算已完成但未整理的任务数
const completedCount = computed(() => {
  return tasks.value.filter(t => t.status === 'completed' && !isOrganized(t)).length
})

// 判断是否已整理
function isOrganized(task: any): boolean {
  return !!(task.message && task.message.includes('[organized]'))
}

/**
 * 获取任务进度百分比（0-100）
 * 优先使用 progress 字段（后端已计算），回退用 downloaded/total_size 计算
 */
function getProgressPct(task: any): string {
  if (task.progress != null && task.progress > 0) {
    return task.progress.toFixed(1)
  }
  if (task.downloaded && task.total_size && task.total_size > 0) {
    return ((task.downloaded / task.total_size) * 100).toFixed(1)
  }
  return '0.0'
}

// 状态筛选
const statusFilters = computed(() => {
  const counts: Record<string, number> = {}
  tasks.value.forEach(t => {
    counts[t.status] = (counts[t.status] || 0) + 1
  })
  return [
    { label: '全部', value: 'all', count: tasks.value.length },
    { label: '下载中', value: 'downloading', count: counts['downloading'] || 0 },
    { label: '已完成', value: 'completed', count: counts['completed'] || 0 },
    { label: '暂停', value: 'paused', count: counts['paused'] || 0 },
    { label: '错误', value: 'error', count: counts['error'] || 0 },
  ]
})

const filteredTasks = computed(() => {
  if (activeFilter.value === 'all') return tasks.value
  return tasks.value.filter(t => t.status === activeFilter.value)
})

// 加载数据
async function loadClients() {
  try {
    const { data } = await downloadApi.getClients()
    clients.value = Array.isArray(data) ? data : data.items || []
    if (clients.value.length > 0 && !newTaskClient.value) {
      newTaskClient.value = clients.value[0].id
    }
  } catch (e) {
    toast.error('加载下载客户端失败')
  }
}

async function loadTasks() {
  try {
    const { data } = await downloadApi.getTasks()
    tasks.value = Array.isArray(data) ? data : data.items || []
  } catch (e) {
    toast.error('加载下载任务失败')
  } finally {
    loading.value = false
  }
}

async function syncTasks() {
  syncing.value = true
  try {
    await downloadApi.syncTasks()
    await loadTasks()
    toast.success('同步完成')
  } catch (e) {
    toast.error('同步下载任务失败')
  } finally {
    syncing.value = false
  }
}

// ── 整理入库 ──

async function organizeAllCompleted() {
  if (completedCount.value === 0) {
    toast.info('没有需要整理的已完成任务')
    return
  }

  const confirmed = await toast.confirm({
    title: '整理入库',
    message: `将 ${completedCount.value} 个已完成任务的文件整理到媒体库并自动刮削，确定执行？`,
    confirmText: '开始整理',
  })
  if (!confirmed) return

  organizing.value = true
  organizeResult.value = null
  try {
    const { data } = await downloadApi.organizeAll()
    organizeResult.value = data as any
    if (data.organized > 0) {
      toast.success(`成功整理 ${data.organized} 个文件入库`)
    } else if (data.skipped > 0) {
      toast.info(`${data.skipped} 个文件已跳过（可能已存在）`)
    } else if (data.errors > 0) {
      toast.error(`整理过程中出现 ${data.errors} 个错误`)
    } else {
      toast.info('没有需要整理的文件')
    }
    await loadTasks()
  } catch (e) {
    toast.error('整理失败')
  } finally {
    organizing.value = false
  }
}

async function organizeSingleTask(id: number) {
  try {
    const { data } = await downloadApi.organizeTask(id)
    if (data.organized > 0) {
      toast.success(`已整理 ${data.organized} 个文件入库`)
    } else if (data.skipped > 0) {
      toast.info('文件已存在或无需整理')
    } else if (data.errors?.length) {
      toast.error(`整理失败: ${(data.errors as string[]).join(', ')}`)
    } else {
      toast.info('无需整理')
    }
    await loadTasks()
  } catch (e) {
    toast.error('整理失败')
  }
}

async function addTask() {
  if (!newTaskUrl.value.trim()) return
  try {
    await downloadApi.addTask({
      torrent_url: newTaskUrl.value.trim(),
      client_id: newTaskClient.value,
      save_path: newTaskSavePath.value || undefined,
    })
    showAddTask.value = false
    newTaskUrl.value = ''
    newTaskSavePath.value = ''
    toast.success('已添加下载任务')
    await loadTasks()
  } catch (e) {
    toast.error('添加下载任务失败')
  }
}

async function pauseTask(id: number) {
  try {
    await downloadApi.pauseTask(id)
    await loadTasks()
  } catch (e) {
    toast.error('暂停任务失败')
  }
}

async function resumeTask(id: number) {
  try {
    await downloadApi.resumeTask(id)
    await loadTasks()
  } catch (e) {
    toast.error('恢复任务失败')
  }
}

async function handleDelete(task: any) {
  const confirmed = await toast.confirm({
    title: '确认删除',
    message: `确定要删除「${task.torrent_name || task.name}」吗？`,
    confirmText: '删除',
    danger: true,
  })
  if (!confirmed) return
  try {
    await downloadApi.deleteTask(task.id, false)
    toast.success('已删除下载任务')
    // 给底层下载器 I/O 操作留出时间，避免瞬间刷新拉取到旧数据（僵尸任务复活）
    setTimeout(() => {
      loadTasks()
    }, 400)
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.response?.data?.message || e?.message || '未知错误'
    toast.error(`删除下载任务失败：${detail}`)
  }
}

// ── SSE 实时进度更新 ──
// 使用 SSE 接收后端推送的进度事件，直接更新对应任务数据，无需重新请求整个列表

function applySSEProgressUpdate() {
  const events = getEventsByType('download_progress')
  if (events.length === 0) return

  const latest = events[0]  // events 按时间倒序，第一个最新
  if (!latest?.data?.tasks || !Array.isArray(latest.data.tasks)) return

  let hasNewCompleted = false
  for (const update of latest.data.tasks) {
    const idx = tasks.value.findIndex((t: any) => t.id === update.id)
    if (idx !== -1) {
      const oldStatus = tasks.value[idx].status
      // 原地更新，保留其他字段（如 message、subscription_id 等）
      tasks.value[idx] = {
        ...tasks.value[idx],
        status: update.status,
        progress: update.progress,
        total_size: update.total_size,
        downloaded: update.downloaded,      // 后端字段名是 downloaded
        speed: update.speed,
        upload_speed: update.upload_speed,
        seeders: update.seeders,
        eta: update.eta,
      }
      // 检测是否有任务刚完成
      if (update.status === 'completed' && oldStatus !== 'completed') {
        hasNewCompleted = true
      }
    }
  }

  // 如果有任务刚完成，完整刷新一次（获取最新 message/subscription_id 等字段）
  if (hasNewCompleted) {
    loadTasks().catch(() => {})
  }
}

// ── 定时刷新逻辑 ──
// 每 3 秒应用一次 SSE 进度数据；每 10 秒完整刷新一次任务列表
let progressTimer: ReturnType<typeof setInterval> | null = null
let refreshTimer: ReturnType<typeof setInterval> | null = null
let fullRefreshCounter = 0

function startPolling() {
  // 每 3 秒从 SSE 应用最新进度
  progressTimer = setInterval(() => {
    applySSEProgressUpdate()
    // 每 ~10 秒完整刷新一次（3次 * 3s = 9s）
    fullRefreshCounter++
    if (fullRefreshCounter >= 3) {
      fullRefreshCounter = 0
      loadTasks().catch(() => {})
    }
  }, 3000)
}

function stopPolling() {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  fullRefreshCounter = 0
}

onMounted(async () => {
  await Promise.all([loadClients(), loadTasks()])
  connectSSE()
  startPolling()
})

onUnmounted(() => {
  disconnectSSE()
  stopPolling()
})
</script>
