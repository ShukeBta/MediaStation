<template>
  <div class="space-y-5">
    <p class="text-sm" style="color: var(--text-muted)">系统运行状态与版本信息</p>

    <!-- 基础信息卡片 -->
    <div class="card p-5">
      <h3 class="text-sm font-medium mb-3" style="color: var(--text-muted)">应用信息</h3>
      <div class="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-3 text-sm">
        <div>
          <div class="text-xs mb-0.5" style="color: var(--text-faint)">版本</div>
          <div class="font-medium">{{ systemInfo.version || '0.1.0' }}</div>
        </div>
        <div>
          <div class="text-xs mb-0.5" style="color: var(--text-faint)">运行时间</div>
          <div class="font-medium">{{ systemInfo.uptime || '-' }}</div>
        </div>
        <div>
          <div class="text-xs mb-0.5" style="color: var(--text-faint)">平台</div>
          <div class="font-medium">{{ systemInfo.platform }} / Python {{ systemInfo.python_version }}</div>
        </div>
        <div>
          <div class="text-xs mb-0.5" style="color: var(--text-faint)">数据库</div>
          <div class="font-medium">{{ systemInfo.db_type || 'SQLite' }}</div>
        </div>
        <div>
          <div class="text-xs mb-0.5" style="color: var(--text-faint)">数据目录</div>
          <div class="font-mono text-xs truncate" style="color: var(--text-secondary)">{{ systemInfo.data_dir || '-' }}</div>
        </div>
      </div>
    </div>

    <!-- 外部工具状态 -->
    <div class="card p-5">
      <h3 class="text-sm font-medium mb-3" style="color: var(--text-muted)">外部工具</h3>
      <div class="space-y-3">
        <!-- TMDb -->
        <div class="flex items-center justify-between">
          <div>
            <div class="text-sm font-medium">TMDb 刮削器</div>
            <div class="text-xs mt-0.5" style="color: var(--text-muted)">语言: {{ systemInfo.tmdb_language || 'zh-CN' }}</div>
          </div>
          <span :class="[
            'text-xs px-2.5 py-1 rounded-full font-medium',
            systemInfo.tmdb_configured
              ? 'bg-emerald-500/10 text-emerald-400'
              : 'bg-amber-500/10 text-amber-400',
          ]">
            {{ systemInfo.tmdb_configured ? '✓ 已配置' : '⚠ 未配置 API Key' }}
          </span>
        </div>

        <!-- FFmpeg -->
        <div class="flex items-center justify-between">
          <div>
            <div class="text-sm font-medium">FFmpeg</div>
            <div class="text-xs mt-0.5 font-mono" style="color: var(--text-muted)">{{ systemInfo.ffmpeg_path || 'ffmpeg' }}</div>
          </div>
          <span :class="[
            'text-xs px-2.5 py-1 rounded-full font-medium',
            systemInfo.ffmpeg_ok !== false
              ? 'bg-emerald-500/10 text-emerald-400'
              : 'bg-red-500/10 text-red-400',
          ]">
            {{ systemInfo.ffmpeg_ok !== false ? '✓ 可用' : '✗ 未找到' }}
          </span>
        </div>

        <!-- FFprobe -->
        <div class="flex items-center justify-between">
          <div>
            <div class="text-sm font-medium">FFprobe</div>
            <div class="text-xs mt-0.5 font-mono" style="color: var(--text-muted)">{{ systemInfo.ffprobe_path || 'ffprobe' }}</div>
          </div>
          <span :class="[
            'text-xs px-2.5 py-1 rounded-full font-medium',
            systemInfo.ffprobe_ok !== false
              ? 'bg-emerald-500/10 text-emerald-400'
              : 'bg-red-500/10 text-red-400',
          ]">
            {{ systemInfo.ffprobe_ok !== false ? '✓ 可用' : '✗ 未找到' }}
          </span>
        </div>

        <!-- 转码加速 -->
        <div class="flex items-center justify-between">
          <div>
            <div class="text-sm font-medium">硬件转码加速</div>
            <div class="text-xs mt-0.5" style="color: var(--text-muted)">最大并发任务: {{ systemInfo.max_transcode_jobs || 2 }}</div>
          </div>
          <span class="text-xs px-2.5 py-1 rounded-full font-medium bg-brand-600/10 text-brand-400">
            {{ accelLabel(systemInfo.hw_accel) }}
          </span>
        </div>
      </div>
    </div>

    <!-- 资源监控 -->
    <div class="card p-5">
      <h3 class="text-sm font-medium mb-3" style="color: var(--text-muted)">资源监控</h3>
      <div class="space-y-4">
        <div>
          <div class="flex justify-between text-sm mb-1.5">
            <span style="color: var(--text-muted)">CPU 使用率</span>
            <span class="font-medium">{{ status.cpu_percent?.toFixed(1) }}%</span>
          </div>
          <div class="progress-bar"><div :style="{ width: status.cpu_percent + '%' }" /></div>
        </div>
        <div>
          <div class="flex justify-between text-sm mb-1.5">
            <span style="color: var(--text-muted)">内存</span>
            <span class="font-medium">{{ formatBytes(status.memory?.used) }} / {{ formatBytes(status.memory?.total) }} ({{ status.memory?.percent?.toFixed(1) }}%)</span>
          </div>
          <div class="progress-bar"><div :style="{ width: status.memory?.percent + '%' }" /></div>
        </div>
        <div>
          <div class="flex justify-between text-sm mb-1.5">
            <span style="color: var(--text-muted)">磁盘</span>
            <span class="font-medium">{{ formatBytesLarge(status.disk?.used) }} / {{ formatBytesLarge(status.disk?.total) }} ({{ status.disk?.percent?.toFixed(1) }}%)</span>
          </div>
          <div class="progress-bar"><div :style="{ width: status.disk?.percent + '%' }" /></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { systemApi } from '@/api/system'

const systemInfo = ref<any>({})
const status = ref<any>({})

const ACCEL_LABELS: Record<string, string> = {
  auto: '自动检测',
  qsv: 'Intel QSV',
  vaapi: 'VAAPI (Linux)',
  nvenc: 'NVIDIA NVENC',
  videotoolbox: 'Apple VideoToolbox',
  none: '软件转码',
}

function accelLabel(val: string) {
  return ACCEL_LABELS[val] || val || '自动检测'
}

function formatBytes(bytes: number): string {
  if (!bytes) return '0 B'
  const gb = bytes / (1024 ** 3)
  if (gb >= 1) return `${gb.toFixed(1)} GB`
  const mb = bytes / (1024 ** 2)
  return `${mb.toFixed(0)} MB`
}

function formatBytesLarge(bytes: number): string {
  if (!bytes) return '0 B'
  const tb = bytes / (1024 ** 4)
  if (tb >= 1) return `${tb.toFixed(1)} TB`
  return formatBytes(bytes)
}

onMounted(async () => {
  try {
    const [infoRes, statusRes] = await Promise.allSettled([
      systemApi.getInfo(),
      systemApi.getStatus(),
    ])
    if (infoRes.status === 'fulfilled') systemInfo.value = infoRes.value.data
    if (statusRes.status === 'fulfilled') status.value = statusRes.value.data
  } catch (e) {
    console.error('加载系统信息失败:', e)
  }
})
</script>
