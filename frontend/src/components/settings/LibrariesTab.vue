<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-sm" style="color: var(--text-muted)">管理媒体文件扫描目录</p>
      <button @click="openModal()" class="btn-primary text-sm flex items-center gap-1">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
        添加媒体库
      </button>
    </div>

    <!-- 扫描进度条 -->
    <Transition name="slide-down">
      <div v-if="scanningLib" class="rounded-lg p-3 text-sm flex items-center gap-3 border bg-brand-600/10 border-brand-500/30 text-brand-400">
        <svg class="w-4 h-4 animate-spin shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
        </svg>
        <span>{{ scanMessage || '正在扫描媒体库...' }}</span>
      </div>
    </Transition>

    <!-- 扫描结果 -->
    <Transition name="slide-down">
      <div v-if="scanResult" class="rounded-lg p-3 text-sm flex items-center gap-2 border bg-emerald-500/10 border-emerald-500/30 text-emerald-400">
        <svg class="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
        </svg>
        <span>扫描完成：新增 {{ scanResult.added || 0 }} 个，更新 {{ scanResult.updated || 0 }} 个，移除 {{ scanResult.removed || 0 }} 个</span>
        <button @click="scanResult = null" class="ml-auto text-emerald-500/60 hover:text-emerald-400">
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
      </div>
    </Transition>

    <div class="space-y-3">
      <div v-for="lib in libraries" :key="lib.id" class="card p-4">
        <div class="flex items-start justify-between">
          <div class="space-y-1.5 min-w-0 flex-1">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="font-medium">{{ lib.name }}</span>
              <span class="text-xs px-2 py-0.5 rounded border border-[var(--border-primary)]"
                style="background: var(--bg-input); color: var(--text-secondary)">
                {{ mediaTypeLabel(lib.media_type) }}
              </span>
              <span v-if="lib.item_count !== undefined" class="text-xs"
                style="color: var(--text-faint)">
                {{ lib.item_count }} 个条目
              </span>
            </div>
            <div class="text-xs font-mono truncate" style="color: var(--text-muted)">{{ lib.path }}</div>
            <div class="flex flex-wrap gap-3 text-xs" style="color: var(--text-faint)">
              <span v-if="lib.last_scan">上次扫描: {{ formatDate(lib.last_scan) }}</span>
              <span v-else>尚未扫描</span>
            </div>
          </div>
          <div class="flex items-center gap-1 shrink-0 ml-3">
            <button @click="scanLibrary(lib)" :disabled="!!scanningLib"
              class="p-1.5 rounded-lg transition-colors hover:bg-[var(--bg-hover)] disabled:opacity-40"
              style="color: var(--text-muted)" title="立即扫描">
              <svg :class="['w-4 h-4', scanningLib === lib.id && 'animate-spin']" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
              </svg>
            </button>
            <button @click="openModal(lib)"
              class="p-1.5 rounded-lg transition-colors hover:bg-[var(--bg-hover)]" style="color: var(--text-muted)">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
            </button>
            <button @click="confirmDelete(lib)"
              class="p-1.5 rounded-lg transition-colors hover:bg-red-500/10 hover:text-red-400" style="color: var(--text-muted)">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <AppEmpty v-if="libraries.length === 0" message="暂无媒体库，请添加目录以开始扫描" />

    <!-- 弹窗 -->
    <AppModal v-model:show="modal.show" :title="modal.editing ? '编辑媒体库' : '添加媒体库'">
      <div class="space-y-4">
        <div>
          <label class="block text-sm mb-1" style="color: var(--text-muted)">名称</label>
          <input v-model="modal.name" placeholder="例如: 电影库" class="input" />
        </div>
        <div>
          <label class="block text-sm mb-1" style="color: var(--text-muted)">路径</label>
          <input v-model="modal.path" placeholder="D:\Movies" class="input" />
          <p class="text-xs mt-1" style="color: var(--text-faint)">服务器上的媒体文件绝对路径（Windows: D:\Movies，Linux: /media/movies）</p>
        </div>
        <div>
          <label class="block text-sm mb-1" style="color: var(--text-muted)">类型</label>
          <select v-model="modal.media_type" class="input">
            <option value="movie">电影</option>
            <option value="tv">电视剧/动漫</option>
            <option value="anime">动漫</option>
          </select>
        </div>
      </div>
      <template #footer>
        <button @click="modal.show = false" class="btn-secondary text-sm">取消</button>
        <button @click="save" :disabled="!modal.name.trim() || !modal.path.trim()" class="btn-primary text-sm disabled:opacity-50">保存</button>
      </template>
    </AppModal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { mediaApi } from '@/api/media'
import { useFormat } from '@/composables/useFormat'
import { useToast } from '@/composables/useToast'
import AppModal from '@/components/AppModal.vue'
import AppEmpty from '@/components/AppEmpty.vue'

const { formatDate } = useFormat()
const toast = useToast()

const libraries = ref<any[]>([])
const scanningLib = ref<number | null>(null)
const scanMessage = ref('')
const scanResult = ref<any>(null)

const modal = ref({
  show: false, editing: null as any,
  name: '', path: '', media_type: 'movie',
})

function mediaTypeLabel(type: string) {
  const map: Record<string, string> = { movie: '电影', tv: '电视剧', anime: '动漫', mixed: '混合' }
  return map[type] || type
}
function openModal(lib?: any) {
  modal.value = lib
    ? { show: true, editing: lib, name: lib.name, path: lib.path, media_type: lib.media_type }
    : { show: true, editing: null, name: '', path: '', media_type: 'movie' }
}

async function save() {
  try {
    const payload = { name: modal.value.name, path: modal.value.path, media_type: modal.value.media_type }
    if (modal.value.editing) {
      await mediaApi.updateLibrary(modal.value.editing.id, payload)
      modal.value.show = false
      toast.success('保存成功')
      await loadLibraries()
    } else {
      const { data: newLib } = await mediaApi.createLibrary(payload)
      modal.value.show = false
      toast.success('媒体库已创建，正在扫描...')
      // 创建后立即自动扫描
      await scanLibrary(newLib)
    }
  } catch (e: any) {
    toast.error(`保存失败: ${e.response?.data?.detail || e.message}`)
  }
}

async function scanLibrary(lib: any) {
  scanningLib.value = lib.id
  scanResult.value = null
  scanMessage.value = `正在扫描「${lib.name}」...`

  try {
    const { data } = await mediaApi.scanLibrary(lib.id)
    // 后端返回 ScanResult 对象
    const result = data?.result || data
    if (result && typeof result === 'object') {
      scanResult.value = result
    } else {
      toast.success('扫描已启动，请稍后查看结果')
    }
    // 刷新媒体库列表（更新 item_count）
    await loadLibraries()
  } catch (e: any) {
    toast.error(`扫描失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    scanningLib.value = null
    scanMessage.value = ''
  }

  // 10秒后自动消失
  setTimeout(() => { scanResult.value = null }, 10000)
}

async function confirmDelete(lib: any) {
  const ok = await toast.confirm({
    title: '删除媒体库',
    message: `确定要删除媒体库「${lib.name}」吗？这不会删除实际的媒体文件，但会清除数据库中的相关记录。`,
    confirmText: '删除',
    danger: true,
  })
  if (!ok) return
  try {
    await mediaApi.deleteLibrary(lib.id)
    toast.success('已删除')
    await loadLibraries()
  } catch (e: any) {
    toast.error(`删除失败: ${e.response?.data?.detail || e.message}`)
  }
}

async function loadLibraries() {
  try {
    const { data } = await mediaApi.getLibraries()
    libraries.value = Array.isArray(data) ? data : data.items || []
  } catch (e) {
    console.error('加载媒体库失败:', e)
  }
}

onMounted(() => loadLibraries())
</script>

<style scoped>
.slide-down-enter-active, .slide-down-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.slide-down-enter-from, .slide-down-leave-to {
  max-height: 0;
  opacity: 0;
  transform: translateY(-4px);
}
.slide-down-enter-to, .slide-down-leave-from {
  max-height: 60px;
  opacity: 1;
  transform: translateY(0);
}
</style>
