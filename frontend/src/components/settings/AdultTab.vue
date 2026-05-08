<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <div>
        <h2 class="text-lg font-semibold">Adult Provider 配置</h2>
        <p class="text-sm" style="color: var(--text-muted)">
          18+ 番号刮削配置，支持 JavBus、JavDB 和 Python 微服务多层 Fallback
        </p>
      </div>
      <button @click="loadConfig" class="btn btn-outline btn-sm">
        <Icon icon="ph:arrow-clockwise" class="mr-1" />
        刷新
      </button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="flex justify-center py-12">
      <span class="loading loading-spinner loading-lg"></span>
    </div>

    <!-- 配置表单 -->
    <div v-else class="space-y-6">
      <!-- 启用开关 -->
      <div class="card bg-[var(--bg-secondary)] border border-[var(--border-primary)]">
        <div class="card-body p-4">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="font-medium flex items-center gap-2">
                <Icon icon="ph:shield-check" class="text-lg text-brand-400" />
                启用 Adult Provider
              </h3>
              <p class="text-xs mt-1" style="color: var(--text-muted)">
                启用后，系统将自动识别 18+ 内容并使用专用刮削源
              </p>
            </div>
            <input
              type="checkbox"
              class="toggle toggle-primary"
              v-model="form.enabled"
              @change="saveConfig"
            />
          </div>
        </div>
      </div>

      <!-- 18+ 目录配置 -->
      <div class="card bg-[var(--bg-secondary)] border border-[var(--border-primary)]">
        <div class="card-body p-4">
          <h3 class="font-medium flex items-center gap-2 mb-3">
            <Icon icon="ph:folder-open" class="text-lg" />
            18+ 目录
            <span class="badge badge-sm badge-ghost">可选</span>
          </h3>
          <p class="text-xs mb-3" style="color: var(--text-muted)">
            配置包含 18+ 内容的目录路径。不配置时，系统将根据文件名自动识别。
          </p>

          <!-- 已添加的目录 -->
          <div class="space-y-2 mb-3">
            <div
              v-for="(dir, index) in form.adult_dirs"
              :key="index"
              class="flex items-center gap-2 p-2 rounded bg-[var(--bg-primary)]"
            >
              <Icon icon="ph:folder" class="text-brand-400" />
              <span class="flex-1 text-sm">{{ dir }}</span>
              <button @click="removeDir(index)" class="btn btn-ghost btn-xs text-error">
                <Icon icon="ph:trash" />
              </button>
            </div>
          </div>

          <!-- 添加目录 -->
          <div class="flex gap-2">
            <input
              v-model="newDir"
              type="text"
              class="input input-sm flex-1 bg-[var(--bg-primary)]"
              placeholder="/path/to/adult/folder"
              @keyup.enter="addDir"
            />
            <button @click="addDir" class="btn btn-sm btn-outline" :disabled="!newDir.trim()">
              <Icon icon="ph:plus" class="mr-1" />
              添加
            </button>
          </div>
        </div>
      </div>

      <!-- 刮削源配置 -->
      <div class="card bg-[var(--bg-secondary)] border border-[var(--border-primary)]">
        <div class="card-body p-4">
          <h3 class="font-medium flex items-center gap-2 mb-3">
            <Icon icon="ph:globe" class="text-lg" />
            刮削源配置
          </h3>

          <!-- JavBus 配置 -->
          <div class="space-y-3 mb-4 p-3 rounded bg-[var(--bg-primary)]">
            <div class="flex items-center gap-2">
              <span class="badge badge-sm badge-primary">第1层</span>
              <span class="font-medium">JavBus</span>
              <span class="badge badge-xs badge-success">主刮削</span>
            </div>
            <div class="form-control">
              <label class="label py-1">
                <span class="label-text text-xs">JavBus 地址</span>
              </label>
              <input
                v-model="form.javbus_url"
                type="text"
                class="input input-sm bg-[var(--bg-secondary)]"
                placeholder="https://www.javbus.com"
                @change="saveConfig"
              />
            </div>
          </div>

          <!-- JavDB 配置 -->
          <div class="space-y-3 mb-4 p-3 rounded bg-[var(--bg-primary)]">
            <div class="flex items-center gap-2">
              <span class="badge badge-sm badge-secondary">第2层</span>
              <span class="font-medium">JavDB</span>
              <span class="badge badge-xs badge-ghost">Fallback</span>
            </div>
            <div class="form-control">
              <label class="label py-1">
                <span class="label-text text-xs">JavDB 地址</span>
              </label>
              <input
                v-model="form.javdb_url"
                type="text"
                class="input input-sm bg-[var(--bg-secondary)]"
                placeholder="https://javdb.com"
                @change="saveConfig"
              />
            </div>
            <div class="form-control">
              <label class="label py-1">
                <span class="label-text text-xs">JavDB Cookie</span>
                <span class="label-text-alt text-xs" style="color: var(--text-muted)">
                  可选，登录后获取
                </span>
              </label>
              <input
                v-model="form.javdb_cookie"
                type="password"
                class="input input-sm bg-[var(--bg-secondary)]"
                placeholder="输入 Cookie 以访问更多内容"
                @change="saveConfig"
              />
            </div>
          </div>

          <!-- Python 微服务配置 -->
          <div class="space-y-3 p-3 rounded bg-[var(--bg-primary)]">
            <div class="flex items-center gap-2">
              <span class="badge badge-sm badge-accent">第3层</span>
              <span class="font-medium">Python 微服务</span>
              <span class="badge badge-xs badge-ghost">最终兜底</span>
            </div>
            <div class="form-control">
              <label class="label py-1">
                <span class="label-text text-xs">微服务地址</span>
                <span class="label-text-alt text-xs" style="color: var(--text-muted)">
                  可选
                </span>
              </label>
              <input
                v-model="form.microservice_url"
                type="text"
                class="input input-sm bg-[var(--bg-secondary)]"
                placeholder="http://localhost:5000"
                @change="saveConfig"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- 代理配置 -->
      <div class="card bg-[var(--bg-secondary)] border border-[var(--border-primary)]">
        <div class="card-body p-4">
          <h3 class="font-medium flex items-center gap-2 mb-3">
            <Icon icon="ph:proxy" class="text-lg" />
            代理配置
            <span class="badge badge-xs badge-ghost">可选</span>
          </h3>
          <div class="flex items-center gap-2 mb-3 p-2 rounded bg-[var(--bg-primary)]">
            <Icon icon="ph:check-circle" class="text-success" />
            <span class="text-xs">默认自动使用系统代理（环境变量 HTTP_PROXY/HTTPS_PROXY）</span>
          </div>
          <div class="form-control">
            <label class="label py-1">
              <span class="label-text text-xs">自定义代理（可选）</span>
              <span class="label-text-alt text-xs" style="color: var(--text-muted)">
                留空则使用系统代理
              </span>
            </label>
            <input
              v-model="form.proxy"
              type="text"
              class="input input-sm bg-[var(--bg-primary)]"
              placeholder="http://proxy:8080"
              @change="saveConfig"
            />
          </div>
        </div>
      </div>

      <!-- 测试按钮 -->
      <div class="flex gap-3 justify-end">
        <button @click="testJavbus" class="btn btn-outline btn-sm" :disabled="testing.javbus">
          <span v-if="testing.javbus" class="loading loading-spinner loading-xs"></span>
          <Icon v-else icon="ph:plugs-connected" class="mr-1" />
          测试 JavBus
        </button>
        <button @click="testJavdb" class="btn btn-outline btn-sm" :disabled="testing.javdb">
          <span v-if="testing.javdb" class="loading loading-spinner loading-xs"></span>
          <Icon v-else icon="ph:plugs-connected" class="mr-1" />
          测试 JavDB
        </button>
      </div>

      <!-- 测试结果 -->
      <div v-if="testMessage" :class="['alert', testSuccess ? 'alert-success' : 'alert-error']">
        <Icon :icon="testSuccess ? 'ph:check-circle' : 'ph:x-circle'" class="text-xl" />
        <span>{{ testMessage }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import { apiConfigApi } from '@/api/config'
import { mediaApi } from '@/api/media'

interface AdultConfig {
  enabled: boolean
  adult_dirs: string[]
  javbus_url: string
  javdb_url: string
  javdb_cookie: string
  microservice_url: string
  proxy: string
}

const loading = ref(true)
const form = reactive<AdultConfig>({
  enabled: false,
  adult_dirs: [],
  javbus_url: 'https://www.javbus.com',
  javdb_url: 'https://javdb.com',
  javdb_cookie: '',
  microservice_url: '',
  proxy: '',
})

const newDir = ref('')
const testing = reactive({ javbus: false, javdb: false })
const testMessage = ref('')
const testSuccess = ref(false)

async function loadConfig() {
  loading.value = true
  try {
    const { data } = await apiConfigApi.getEffective('adult')
    // 解析 extra 字段
    const extra = data.extra || {}
    form.enabled = data.enabled ?? false
    form.adult_dirs = extra.adult_dirs || []
    form.javbus_url = extra.javbus_url || 'https://www.javbus.com'
    form.javdb_url = extra.javdb_url || 'https://javdb.com'
    form.javdb_cookie = extra.javdb_cookie || ''
    form.microservice_url = extra.microservice_url || ''
    form.proxy = extra.proxy || ''
  } catch (e) {
    console.error('Failed to load adult config:', e)
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  try {
    await apiConfigApi.update('adult', {
      enabled: form.enabled,
      extra: {
        adult_dirs: form.adult_dirs,
        javbus_url: form.javbus_url,
        javdb_url: form.javdb_url,
        javdb_cookie: form.javdb_cookie,
        microservice_url: form.microservice_url,
        proxy: form.proxy,
      },
    })
    showTestResult(true, '配置已保存')
  } catch (e) {
    console.error('Failed to save config:', e)
    showTestResult(false, '保存失败')
  }
}

function addDir() {
  const dir = newDir.value.trim()
  if (dir && !form.adult_dirs.includes(dir)) {
    form.adult_dirs.push(dir)
    saveConfig()
  }
  newDir.value = ''
}

function removeDir(index: number) {
  form.adult_dirs.splice(index, 1)
  saveConfig()
}

async function testJavbus() {
  testing.javbus = true
  testMessage.value = ''
  try {
    // 尝试刮削一个测试番号
    const { data } = await mediaApi.scrapeTest('FC2-PPV-1234')
    if (data.success) {
      showTestResult(true, `JavBus 测试成功！刮削到: ${data.title || '未知标题'}`)
    } else {
      showTestResult(false, `JavBus 测试失败: ${data.message || '未知错误'}`)
    }
  } catch (e: any) {
    showTestResult(false, `JavBus 连接失败: ${e.message || '网络错误'}`)
  } finally {
    testing.javbus = false
  }
}

async function testJavdb() {
  testing.javdb = true
  testMessage.value = ''
  try {
    // 测试 API config 连接
    const { data } = await apiConfigApi.test('adult')
    showTestResult(data.success, data.message)
  } catch (e: any) {
    showTestResult(false, `JavDB 连接失败: ${e.message || '网络错误'}`)
  } finally {
    testing.javdb = false
  }
}

function showTestResult(success: boolean, message: string) {
  testSuccess.value = success
  testMessage.value = message
  setTimeout(() => {
    testMessage.value = ''
  }, 5000)
}

onMounted(() => {
  loadConfig()
})
</script>
