<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <p class="text-sm" style="color: var(--text-muted)">配置 TMDb、转码引擎等核心设置（保存后部分配置需重启生效）</p>
    </div>

    <div class="card p-5 space-y-4">
      <h3 class="font-medium flex items-center gap-2" style="color: var(--text-primary)">
        <span class="text-lg">🎬</span> TMDb 刮削器
      </h3>

      <p class="text-xs" style="color: var(--text-muted)">
        API Key 请在 <a @click="goToApiConfig" class="text-brand-400 hover:underline cursor-pointer">API 配置</a> 页面统一管理
      </p>

      <div>
        <label class="block text-sm mb-1.5" style="color: var(--text-muted)">元数据语言</label>
        <select v-model="form.tmdb_language" class="input !w-auto">
          <option value="zh-CN">简体中文</option>
          <option value="zh-TW">繁体中文</option>
          <option value="en-US">English</option>
          <option value="ja-JP">日本語</option>
          <option value="ko-KR">한국어</option>
        </select>
      </div>
    </div>

    <!-- FFmpeg 转码配置 -->
    <div class="card p-5 space-y-4">
      <h3 class="font-medium flex items-center gap-2" style="color: var(--text-primary)">
        <span class="text-lg">⚙️</span> 转码引擎
      </h3>

      <!-- 转码总开关 -->
      <div class="rounded-xl p-4 border transition-colors"
        :style="{
          background: form.transcode_enabled ? 'rgba(16, 185, 129, 0.05)' : 'var(--bg-input)',
          borderColor: form.transcode_enabled ? 'rgba(16, 185, 129, 0.25)' : 'var(--border-primary)',
        }">
        <div class="flex items-center justify-between">
          <div>
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium" style="color: var(--text-primary)">
                {{ form.transcode_enabled ? '转码已开启' : '转码已关闭（直连播放）' }}
              </span>
              <span v-if="form.transcode_enabled"
                class="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-medium">
                GPU 优先
              </span>
              <span v-else
                class="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-500/20 text-gray-400 font-medium">
                零延迟
              </span>
            </div>
            <p class="text-xs mt-1" style="color: var(--text-faint)">
              {{ form.transcode_enabled
                ? '不兼容格式将自动转码为 HLS，优先使用硬件加速'
                : '所有视频直接播放源文件，无需转码，零 CPU 开销'
              }}
            </p>
          </div>
          <!-- Toggle Switch -->
          <button @click="form.transcode_enabled = !form.transcode_enabled"
            type="button"
            role="switch"
            :aria-checked="form.transcode_enabled"
            :class="[
              'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full transition-colors duration-200 focus:outline-none',
              form.transcode_enabled ? 'bg-emerald-500' : 'bg-gray-600',
            ]">
            <span :class="[
              'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5 ml-0.5',
              form.transcode_enabled ? 'translate-x-5' : '',
            ]"></span>
          </button>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="block text-sm mb-1.5" style="color: var(--text-muted)">FFmpeg 路径</label>
          <input v-model="form.ffmpeg_path" placeholder="ffmpeg" class="input" />
          <p class="text-xs mt-1" style="color: var(--text-faint)">留空使用系统 PATH 中的 ffmpeg</p>
        </div>
        <div>
          <label class="block text-sm mb-1.5" style="color: var(--text-muted)">FFprobe 路径</label>
          <input v-model="form.ffprobe_path" placeholder="ffprobe" class="input" />
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="block text-sm mb-1.5" style="color: var(--text-muted)">硬件加速模式</label>
          <select v-model="form.hw_accel" class="input" :disabled="!form.transcode_enabled">
            <option value="auto">自动检测（推荐）</option>
            <option value="none">软件转码（兼容性最好）</option>
            <option value="nvenc">NVIDIA NVENC (CUDA)</option>
            <option value="qsv">Intel Quick Sync Video</option>
            <option value="vaapi">VAAPI（Linux）</option>
            <option value="videotoolbox">Apple VideoToolbox（macOS）</option>
          </select>
          <p class="text-xs mt-1" style="color: var(--text-faint)">
            {{ form.hw_accel === 'auto' ? '自动检测最优 GPU 编码器，Windows 支持 QSV/NVENC' :
               `固定使用 ${form.hw_accel.toUpperCase()} 硬件编码` }}
          </p>
        </div>
        <div>
          <label class="block text-sm mb-1.5" style="color: var(--text-muted)">最大并发转码任务</label>
          <input v-model.number="form.max_transcode_jobs" type="number" min="1" max="8" class="input" :disabled="!form.transcode_enabled" />
          <p class="text-xs mt-1" style="color: var(--text-faint)">并发过多会占用大量内存和 GPU</p>
        </div>
      </div>
    </div>

    <!-- 保存按钮 -->
    <div class="flex justify-end gap-3">
      <button @click="loadConfig" class="btn-secondary text-sm">重置</button>
      <button @click="save" :disabled="saving" class="btn-primary text-sm disabled:opacity-50 flex items-center gap-2">
        <svg v-if="saving" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
        </svg>
        {{ saving ? '保存中...' : '保存配置' }}
      </button>
    </div>

    <!-- 保存提示 -->
    <div v-if="savedMsg" class="rounded-lg p-3 text-sm flex items-center gap-2 border"
      :class="savedMsg.type === 'success'
        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
        : 'bg-red-500/10 border-red-500/30 text-red-400'">
      <svg v-if="savedMsg.type === 'success'" class="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
      </svg>
      <svg v-else class="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
      </svg>
      {{ savedMsg.text }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { systemApi } from '@/api/system'

const emit = defineEmits(['switch-tab'])

const config = ref<any>({})
const form = ref({
  tmdb_language: 'zh-CN',
  hw_accel: 'auto',
  max_transcode_jobs: 2,
  ffmpeg_path: 'ffmpeg',
  ffprobe_path: 'ffprobe',
  transcode_enabled: false,
})
const saving = ref(false)
const savedMsg = ref<{ type: 'success' | 'error'; text: string } | null>(null)

function goToApiConfig() {
  emit('switch-tab', 'apiconfig')
}

async function loadConfig() {
  try {
    const { data } = await systemApi.getConfig()
    config.value = data
    form.value = {
      tmdb_language: data.tmdb_language || 'zh-CN',
      hw_accel: data.hw_accel || 'auto',
      max_transcode_jobs: data.max_transcode_jobs || 2,
      ffmpeg_path: data.ffmpeg_path || 'ffmpeg',
      ffprobe_path: data.ffprobe_path || 'ffprobe',
      transcode_enabled: data.transcode_enabled ?? false,
    }
  } catch (e) {
    console.error('加载配置失败:', e)
  }
}

async function save() {
  saving.value = true
  savedMsg.value = null
  try {
    const payload: Record<string, any> = {
      tmdb_language: form.value.tmdb_language,
      hw_accel: form.value.hw_accel,
      max_transcode_jobs: form.value.max_transcode_jobs,
      ffmpeg_path: form.value.ffmpeg_path,
      ffprobe_path: form.value.ffprobe_path,
      transcode_enabled: form.value.transcode_enabled,
    }

    const { data } = await systemApi.updateConfig(payload)
    savedMsg.value = { type: 'success', text: data.message || '配置已保存' }
    await loadConfig()
    setTimeout(() => { savedMsg.value = null }, 4000)
  } catch (e: any) {
    savedMsg.value = {
      type: 'error',
      text: `保存失败: ${e.response?.data?.detail || e.message}`,
    }
  } finally {
    saving.value = false
  }
}

onMounted(() => loadConfig())
</script>
