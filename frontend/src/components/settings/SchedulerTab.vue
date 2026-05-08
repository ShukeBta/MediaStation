<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-sm" style="color: var(--text-muted)">后台自动运行的定时任务，支持手动立即触发</p>
      <button @click="loadJobs" :disabled="loading"
        class="p-1.5 rounded-lg transition-colors hover:bg-[var(--bg-hover)]" style="color: var(--text-muted)" title="刷新">
        <svg :class="['w-4 h-4', loading && 'animate-spin']" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
        </svg>
      </button>
    </div>

    <div class="space-y-2">
      <div v-for="job in jobs" :key="job.id" class="card p-4">
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0 space-y-1.5">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="font-medium text-sm">{{ jobLabel(job.id) }}</span>
              <span :class="[
                'text-xs px-2 py-0.5 rounded',
                job.status === 'running'
                  ? 'bg-emerald-500/10 text-emerald-400'
                  : 'bg-[var(--bg-input)] text-[var(--text-muted)] border border-[var(--border-primary)]',
              ]">
                {{ job.status === 'running' ? '运行中' : '空闲' }}
              </span>
            </div>
            <div class="text-xs space-y-0.5" style="color: var(--text-muted)">
              <div>下次运行: <span style="color: var(--text-secondary)">{{ job.next_run_time ? formatDate(job.next_run_time) : '未计划' }}</span></div>
              <div v-if="job.trigger" class="font-mono opacity-60">{{ formatTrigger(job.trigger) }}</div>
            </div>
          </div>
          <button
            @click="triggerJob(job.id)"
            :disabled="triggeringId === job.id"
            title="立即运行"
            class="shrink-0 flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg transition-colors disabled:opacity-50"
            style="color: var(--accent-hover); background: var(--accent-subtle)">
            <svg v-if="triggeringId !== job.id" class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z"/>
            </svg>
            <svg v-else class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
            </svg>
            {{ triggeringId === job.id ? '触发中...' : '立即运行' }}
          </button>
        </div>
      </div>
    </div>

    <AppEmpty v-if="jobs.length === 0 && !loading" message="暂无定时任务" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { systemApi } from '@/api/system'
import { useFormat } from '@/composables/useFormat'
import { useToast } from '@/composables/useToast'
import AppEmpty from '@/components/AppEmpty.vue'

const { formatDate } = useFormat()
const toast = useToast()

const jobs = ref<any[]>([])
const loading = ref(false)
const triggeringId = ref<string | null>(null)

const JOB_LABELS: Record<string, string> = {
  media_scan: '媒体库扫描',
  subscription_search: '订阅搜索',
  download_sync: '下载状态同步',
  rss_pull: 'RSS 拉取',
  cache_cleanup: '转码缓存清理',
}

function jobLabel(id: string) {
  return JOB_LABELS[id] || id
}

function formatTrigger(trigger: string): string {
  // 把 APScheduler 的触发器字符串转为可读格式
  if (!trigger) return ''
  // interval[0:30:00] → 每 30 分钟
  const intervalMatch = trigger.match(/interval\[(\d+):(\d+):(\d+)\]/)
  if (intervalMatch) {
    const h = parseInt(intervalMatch[1])
    const m = parseInt(intervalMatch[2])
    const s = parseInt(intervalMatch[3])
    if (h > 0) return `每 ${h} 小时`
    if (m > 0) return `每 ${m} 分钟`
    if (s > 0) return `每 ${s} 秒`
  }
  // cron[hour='3', minute='0'] → 每天 03:00
  const cronMatch = trigger.match(/cron\[(.+)\]/)
  if (cronMatch) return `定时: ${cronMatch[1]}`
  return trigger
}

async function loadJobs() {
  loading.value = true
  try {
    const { data } = await systemApi.getScheduledJobs()
    jobs.value = Array.isArray(data) ? data : data.jobs || data.items || []
  } catch (e) {
    console.error('加载定时任务失败:', e)
  } finally {
    loading.value = false
  }
}

async function triggerJob(jobId: string) {
  triggeringId.value = jobId
  try {
    await systemApi.triggerJob(jobId)
    toast.success(`已触发「${jobLabel(jobId)}」，任务将在调度器下一轮执行`)
    // 延迟刷新列表
    setTimeout(() => loadJobs(), 1500)
  } catch (e: any) {
    toast.error(`触发失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    triggeringId.value = null
  }
}

onMounted(() => loadJobs())
</script>
