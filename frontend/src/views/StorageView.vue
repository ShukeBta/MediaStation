<template>
  <div class="p-4 md:p-6 max-w-4xl mx-auto space-y-6">
    <!-- 页面标题 -->
    <div>
      <h1 class="text-2xl font-bold">外部存储配置</h1>
      <p class="text-sm mt-1" style="color: var(--text-muted)">配置 WebDAV、Alist、S3 等外部存储，扩展媒体库来源</p>
    </div>

    <!-- 状态总览 -->
    <div class="grid grid-cols-3 gap-4">
      <div v-for="item in statusItems" :key="item.key" class="card p-4 rounded-2xl flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl flex items-center justify-center text-lg" :class="item.class">
          {{ item.icon }}
        </div>
        <div>
          <div class="text-sm font-semibold">{{ item.name }}</div>
          <div class="text-xs mt-0.5" :class="storageStatus[item.key]?.configured ? 'text-green-400' : 'text-gray-400'">
            {{ storageStatus[item.key]?.configured ? (storageStatus[item.key]?.enabled ? '已启用' : '已配置（未启用）') : '未配置' }}
          </div>
        </div>
      </div>
    </div>

    <!-- WebDAV 配置卡片 -->
    <div class="card rounded-2xl overflow-hidden">
      <div class="flex items-center justify-between px-6 py-4 border-b" style="border-color: var(--border-color)">
        <div class="flex items-center gap-3">
          <span class="text-xl">📂</span>
          <div>
            <h2 class="font-semibold">WebDAV</h2>
            <p class="text-xs" style="color: var(--text-muted)">支持 Nextcloud、OwnCloud、坚果云等</p>
          </div>
        </div>
        <div class="flex gap-2">
          <button @click="testStorage('webdav')" :disabled="testing.webdav" class="btn-ghost text-xs flex items-center gap-1">
            <svg class="w-3.5 h-3.5" :class="{ 'animate-spin': testing.webdav }" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
            </svg>
            测试连接
          </button>
          <button @click="saveStorage('webdav')" :disabled="saving.webdav" class="btn-primary text-xs">
            {{ saving.webdav ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
      <div class="p-6 grid grid-cols-2 gap-4">
        <div class="col-span-2">
          <label class="label">服务器 URL *</label>
          <input v-model="webdav.url" class="input w-full" placeholder="https://dav.example.com/dav/" />
        </div>
        <div>
          <label class="label">用户名 *</label>
          <input v-model="webdav.username" class="input w-full" placeholder="用户名" />
        </div>
        <div>
          <label class="label">密码 *</label>
          <input v-model="webdav.password" type="password" class="input w-full" placeholder="密码" />
        </div>
        <div>
          <label class="label">根路径</label>
          <input v-model="webdav.root_path" class="input w-full" placeholder="/" />
        </div>
        <div class="flex items-center gap-3 mt-4">
          <input type="checkbox" v-model="webdav.verify_ssl" id="webdav-ssl" />
          <label for="webdav-ssl" class="text-sm">验证 SSL 证书</label>
        </div>
        <div class="flex items-center gap-3 mt-4">
          <input type="checkbox" v-model="webdav.enabled" id="webdav-enabled" />
          <label for="webdav-enabled" class="text-sm font-medium">启用 WebDAV</label>
        </div>
      </div>
      <!-- 测试结果 -->
      <div v-if="testResults.webdav" class="px-6 pb-4">
        <div class="text-sm px-4 py-2 rounded-lg flex items-center gap-2"
          :class="testResults.webdav.success ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'">
          {{ testResults.webdav.success ? '✓' : '✗' }} {{ testResults.webdav.message }}
        </div>
      </div>
    </div>

    <!-- Alist 配置卡片 -->
    <div class="card rounded-2xl overflow-hidden">
      <div class="flex items-center justify-between px-6 py-4 border-b" style="border-color: var(--border-color)">
        <div class="flex items-center gap-3">
          <span class="text-xl">🔗</span>
          <div>
            <h2 class="font-semibold">Alist</h2>
            <p class="text-xs" style="color: var(--text-muted)">聚合网盘工具，支持阿里云盘、百度网盘、OneDrive 等</p>
          </div>
        </div>
        <div class="flex gap-2">
          <button @click="testStorage('alist')" :disabled="testing.alist" class="btn-ghost text-xs flex items-center gap-1">
            <svg class="w-3.5 h-3.5" :class="{ 'animate-spin': testing.alist }" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
            </svg>
            测试连接
          </button>
          <button @click="saveStorage('alist')" :disabled="saving.alist" class="btn-primary text-xs">
            {{ saving.alist ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
      <div class="p-6 grid grid-cols-2 gap-4">
        <div class="col-span-2">
          <label class="label">Alist 服务地址 *</label>
          <input v-model="alist.url" class="input w-full" placeholder="http://localhost:5244" />
        </div>
        <div class="col-span-2">
          <label class="label">API Token *</label>
          <input v-model="alist.token" type="password" class="input w-full" placeholder="在 Alist 管理后台获取" />
        </div>
        <div>
          <label class="label">根路径</label>
          <input v-model="alist.root_path" class="input w-full" placeholder="/" />
        </div>
        <div class="flex items-center gap-3 mt-4">
          <input type="checkbox" v-model="alist.enabled" id="alist-enabled" />
          <label for="alist-enabled" class="text-sm font-medium">启用 Alist</label>
        </div>
      </div>
      <div v-if="testResults.alist" class="px-6 pb-4">
        <div class="text-sm px-4 py-2 rounded-lg flex items-center gap-2"
          :class="testResults.alist.success ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'">
          {{ testResults.alist.success ? '✓' : '✗' }} {{ testResults.alist.message }}
        </div>
      </div>
    </div>

    <!-- S3 配置卡片 -->
    <div class="card rounded-2xl overflow-hidden">
      <div class="flex items-center justify-between px-6 py-4 border-b" style="border-color: var(--border-color)">
        <div class="flex items-center gap-3">
          <span class="text-xl">🪣</span>
          <div>
            <h2 class="font-semibold">S3 对象存储</h2>
            <p class="text-xs" style="color: var(--text-muted)">支持 AWS S3、MinIO、阿里云 OSS、腾讯云 COS 等</p>
          </div>
        </div>
        <div class="flex gap-2">
          <button @click="testStorage('s3')" :disabled="testing.s3" class="btn-ghost text-xs flex items-center gap-1">
            <svg class="w-3.5 h-3.5" :class="{ 'animate-spin': testing.s3 }" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
            </svg>
            测试连接
          </button>
          <button @click="saveStorage('s3')" :disabled="saving.s3" class="btn-primary text-xs">
            {{ saving.s3 ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
      <div class="p-6 grid grid-cols-2 gap-4">
        <div class="col-span-2">
          <label class="label">Endpoint *</label>
          <input v-model="s3.endpoint" class="input w-full" placeholder="https://s3.amazonaws.com 或 http://minio:9000" />
        </div>
        <div>
          <label class="label">Bucket 名称 *</label>
          <input v-model="s3.bucket" class="input w-full" placeholder="my-media-bucket" />
        </div>
        <div>
          <label class="label">区域</label>
          <input v-model="s3.region" class="input w-full" placeholder="us-east-1" />
        </div>
        <div>
          <label class="label">Access Key *</label>
          <input v-model="s3.access_key" class="input w-full" placeholder="Access Key ID" />
        </div>
        <div>
          <label class="label">Secret Key *</label>
          <input v-model="s3.secret_key" type="password" class="input w-full" placeholder="Secret Access Key" />
        </div>
        <div>
          <label class="label">路径前缀</label>
          <input v-model="s3.path_prefix" class="input w-full" placeholder="media/" />
        </div>
        <div class="flex items-center gap-3 mt-4">
          <input type="checkbox" v-model="s3.enabled" id="s3-enabled" />
          <label for="s3-enabled" class="text-sm font-medium">启用 S3</label>
        </div>
      </div>
      <div v-if="testResults.s3" class="px-6 pb-4">
        <div class="text-sm px-4 py-2 rounded-lg flex items-center gap-2"
          :class="testResults.s3.success ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'">
          {{ testResults.s3.success ? '✓' : '✗' }} {{ testResults.s3.message }}
        </div>
      </div>
    </div>

    <!-- Toast -->
    <Teleport to="body">
      <Transition name="toast">
        <div v-if="toast.show" class="fixed top-4 right-4 z-50 card px-4 py-3 rounded-xl text-sm shadow-xl flex items-center gap-2"
          :class="toast.success ? 'border-green-500/40 text-green-400' : 'border-red-500/40 text-red-400'">
          {{ toast.success ? '✓' : '✗' }} {{ toast.msg }}
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api/client'

const storageStatus = ref<Record<string, any>>({})
const testing = ref<Record<string, boolean>>({ webdav: false, alist: false, s3: false })
const saving = ref<Record<string, boolean>>({ webdav: false, alist: false, s3: false })
const testResults = ref<Record<string, any>>({})
const toast = ref({ show: false, msg: '', success: true })

const statusItems = [
  { key: 'webdav', name: 'WebDAV', icon: '📂', class: 'bg-blue-500/15 text-blue-400' },
  { key: 'alist', name: 'Alist', icon: '🔗', class: 'bg-purple-500/15 text-purple-400' },
  { key: 's3', name: 'S3 存储', icon: '🪣', class: 'bg-orange-500/15 text-orange-400' },
]

const webdav = ref({ url: '', username: '', password: '', root_path: '/', verify_ssl: true, enabled: true })
const alist = ref({ url: '', token: '', root_path: '/', enabled: true })
const s3 = ref({ endpoint: '', bucket: '', access_key: '', secret_key: '', region: 'us-east-1', path_prefix: '', enabled: true, use_ssl: true })

function showToast(msg: string, success = true) {
  toast.value = { show: true, msg, success }
  setTimeout(() => { toast.value.show = false }, 3000)
}

async function loadStatus() {
  try {
    const resp = await api.get('/api/admin/storage/status')
    const data = (resp.data as any)?.data || resp.data
    storageStatus.value = data
  } catch {}
}

async function loadConfigs() {
  try {
    const [wResp, aResp, sResp] = await Promise.all([
      api.get('/api/admin/storage/webdav').catch(() => null),
      api.get('/api/admin/storage/alist').catch(() => null),
      api.get('/api/admin/storage/s3').catch(() => null),
    ])
    if (wResp) {
      const d = (wResp.data as any)?.data
      if (d?.config) Object.assign(webdav.value, { ...d.config, password: '' })
    }
    if (aResp) {
      const d = (aResp.data as any)?.data
      if (d?.config) Object.assign(alist.value, { ...d.config, token: '' })
    }
    if (sResp) {
      const d = (sResp.data as any)?.data
      if (d?.config) Object.assign(s3.value, { ...d.config, secret_key: '' })
    }
  } catch {}
}

async function saveStorage(type: string) {
  saving.value[type] = true
  try {
    const configs: Record<string, any> = { webdav: webdav.value, alist: alist.value, s3: s3.value }
    await api.put(`/api/admin/storage/${type}`, configs[type])
    showToast(`${type.toUpperCase()} 配置已保存`)
    await loadStatus()
  } catch (e: any) {
    showToast(e.response?.data?.detail || '保存失败', false)
  } finally {
    saving.value[type] = false
  }
}

async function testStorage(type: string) {
  testing.value[type] = true
  testResults.value[type] = null
  try {
    const resp = await api.post(`/api/admin/storage/${type}/test`)
    testResults.value[type] = (resp.data as any)?.data || resp.data
  } catch (e: any) {
    testResults.value[type] = { success: false, message: e.message || '测试失败' }
  } finally {
    testing.value[type] = false
  }
}

onMounted(async () => {
  await Promise.all([loadStatus(), loadConfigs()])
})
</script>

<style scoped>
.label { display: block; font-size: 0.8rem; font-weight: 500; margin-bottom: 0.25rem; color: var(--text-muted); }
.toast-enter-active, .toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(-8px); }
</style>
