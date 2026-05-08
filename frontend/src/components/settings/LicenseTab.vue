<template>
  <div class="space-y-6">
    <p class="text-sm" style="color: var(--text-muted)">
      {{ isAdmin ? '管理 Plus 授权码，查看激活设备' : '查看授权状态，激活您的 Plus 授权' }}
    </p>

    <!-- 授权状态卡片 -->
    <div class="card p-5">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold flex items-center gap-2" style="color: var(--text-primary)">
          <span :class="statusIconClass">
            {{ licenseStatus?.is_plus ? '✦' : '○' }}
          </span>
          {{ statusTitle }}
        </h3>
        <div class="flex items-center gap-2">
          <!-- 验证模式标签 -->
          <span class="text-xs px-2.5 py-1 rounded-full font-medium"
            :class="modeTagClass">
            {{ modeTagText }}
          </span>
          <span v-if="licenseStatus?.is_plus" class="text-xs px-3 py-1 rounded-full bg-brand-500/10 text-brand-400 font-medium">
            {{ licenseStatus.license_type === 'permanent' ? '永久授权' : '订阅授权' }}
          </span>
        </div>
      </div>

      <!-- 宽限期警告 -->
      <div v-if="licenseStatus?.in_grace_period && licenseStatus?.grace_days_remaining != null"
        class="mb-4 p-3 rounded-lg border border-amber-500/30 bg-amber-500/5 text-sm">
        <span class="text-amber-400 font-medium">⚠ 宽限期中</span>
        <span style="color: var(--text-muted)"> — 授权服务器暂时无法连接，剩余 <strong class="text-amber-400">{{ licenseStatus.grace_days_remaining }}</strong> 天后降级为免费版</span>
      </div>

      <!-- 宽限期已过 -->
      <div v-if="!licenseStatus?.is_plus && licenseStatus?.verification_mode === 'online' && licenseStatus?.grace_days_remaining === 0"
        class="mb-4 p-3 rounded-lg border border-red-500/30 bg-red-500/5 text-sm">
        <span class="text-red-400 font-medium">✕ 宽限期已过期</span>
        <span style="color: var(--text-muted)"> — 授权已降级为免费版。请检查网络连接或重新激活授权。</span>
      </div>

      <div v-if="loadingStatus" class="text-sm" style="color: var(--text-muted)">加载中...</div>
      <div v-else-if="licenseStatus?.is_plus" class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        <div>
          <div class="text-xs mb-1" style="color: var(--text-faint)">授权类型</div>
          <div class="font-medium">{{ licenseStatus.license_type === 'permanent' ? '永久' : '订阅' }}</div>
        </div>
        <div v-if="licenseStatus.expiry_date">
          <div class="text-xs mb-1" style="color: var(--text-faint)">到期时间</div>
          <div class="font-medium">{{ formatDate(licenseStatus.expiry_date) }}</div>
        </div>
        <div v-if="licenseStatus.days_remaining != null">
          <div class="text-xs mb-1" style="color: var(--text-faint)">剩余天数</div>
          <div class="font-medium" :style="{ color: licenseStatus.days_remaining < 30 ? '#f87171' : '' }">
            {{ licenseStatus.days_remaining }} 天
          </div>
        </div>
        <div>
          <div class="text-xs mb-1" style="color: var(--text-faint)">绑定设备</div>
          <div class="font-medium">{{ licenseStatus.device_name || '未知设备' }}</div>
        </div>
      </div>
      <div v-else class="text-sm" style="color: var(--text-muted)">
        当前为免费版，最多 30 个用户。购买 Plus 版可解除限制并解锁所有功能。
      </div>
    </div>

    <!-- 心跳状态卡片（在线模式可见） -->
    <div v-if="licenseConfig?.verification_mode === 'online' && heartbeatStatus" class="card p-5">
      <div class="flex items-center justify-between mb-4">
        <h3 class="font-medium flex items-center gap-2" style="color: var(--text-primary)">
          <span class="text-emerald-400">↻</span> 在线授权心跳
        </h3>
        <button @click="refreshLicense" :disabled="refreshLoading"
          class="text-xs px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
          style="background: var(--bg-hover); color: var(--text-secondary)"
          @mouseenter="$event.target.style.background = 'rgba(16,185,129,0.15)'; $event.target.style.color = '#10b981'"
          @mouseleave="$event.target.style.background = 'var(--bg-hover)'; $event.target.style.color = 'var(--text-secondary)'">
          {{ refreshLoading ? '刷新中...' : '立即刷新' }}
        </button>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
        <div>
          <div class="text-xs mb-1" style="color: var(--text-faint)">最后验证时间</div>
          <div class="font-medium">{{ formatDateTime(heartbeatStatus.last_verified_at) || '—' }}</div>
        </div>
        <div>
          <div class="text-xs mb-1" style="color: var(--text-faint)">最后心跳时间</div>
          <div class="font-medium">{{ formatDateTime(heartbeatStatus.last_heartbeat_at) || '—' }}</div>
        </div>
        <div>
          <div class="text-xs mb-1" style="color: var(--text-faint)">下次心跳到期</div>
          <div class="font-medium" :class="{ 'text-amber-400': isHeartbeatOverdue }">
            {{ formatDateTime(heartbeatStatus.next_heartbeat_at) || '—' }}
            <span v-if="isHeartbeatOverdue" class="text-xs text-amber-400 ml-1">（已过期）</span>
          </div>
        </div>
      </div>
      <div v-if="heartbeatStatus.grace_period_ends" class="mt-3 text-sm" style="color: var(--text-muted)">
        宽限期截止: <span :class="{ 'text-red-400': (heartbeatStatus.days_in_grace ?? 0) < 3 }">{{ formatDateTime(heartbeatStatus.grace_period_ends) }}</span>
        <span v-if="heartbeatStatus.days_in_grace != null"> (剩余 {{ heartbeatStatus.days_in_grace }} 天)</span>
      </div>
    </div>

    <!-- 管理员视图 -->
    <template v-if="isAdmin">
      <!-- 验证模式配置 -->
      <div class="card p-5 space-y-5">
        <h3 class="font-medium flex items-center gap-2" style="color: var(--text-primary)">
          <span>⚙</span> 验证模式配置
        </h3>

        <div v-if="configLoading" class="text-sm" style="color: var(--text-muted)">加载配置中...</div>
        <div v-else class="space-y-4">
          <!-- 模式选择 -->
          <div>
            <label class="block text-sm mb-2" style="color: var(--text-muted)">验证模式</label>
            <div class="flex gap-3">
              <button @click="configForm.verification_mode = 'local'"
                class="flex-1 p-3 rounded-xl border text-sm text-center transition-all"
                :class="configForm.verification_mode === 'local'
                  ? 'border-brand-500/50 bg-brand-500/10 text-brand-400'
                  : 'border-[var(--border-primary)] bg-[var(--bg-input)]'"
                style="color: var(--text-secondary)">
                <div class="font-medium mb-1">本地模式</div>
                <div class="text-xs opacity-70">直接验证授权码，无需外部服务器</div>
              </button>
              <button @click="configForm.verification_mode = 'online'"
                class="flex-1 p-3 rounded-xl border text-sm text-center transition-all"
                :class="configForm.verification_mode === 'online'
                  ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-400'
                  : 'border-[var(--border-primary)] bg-[var(--bg-input)]'"
                style="color: var(--text-secondary)">
                <div class="font-medium mb-1">在线模式</div>
                <div class="text-xs opacity-70">远程服务器验证，支持心跳续期</div>
              </button>
            </div>
          </div>

          <!-- 在线模式配置（展开） -->
          <template v-if="configForm.verification_mode === 'online'">
            <div>
              <label class="block text-sm mb-1.5" style="color: var(--text-muted)">授权服务器 URL</label>
              <div class="flex gap-2">
                <input v-model="configForm.server_url" class="input flex-1 font-mono text-sm"
                  placeholder="https://license.example.com" />
                <button @click="testConnection" :disabled="!configForm.server_url || testingConn"
                  class="btn-secondary text-sm whitespace-nowrap disabled:opacity-50">
                  {{ testingConn ? '测试中...' : '测试连接' }}
                </button>
              </div>
              <div v-if="testResult" class="mt-1.5 text-xs"
                :class="testResult.success ? 'text-emerald-400' : 'text-red-400'">
                {{ testResult.message }}
              </div>
            </div>
            <div>
              <label class="block text-sm mb-1.5" style="color: var(--text-muted)">
                HMAC 签名密钥
                <span v-if="licenseConfig?.server_secret_set" class="text-xs text-emerald-400 ml-1">（已配置）</span>
              </label>
              <input v-model="configForm.server_secret" type="password" class="input font-mono text-sm"
                :placeholder="licenseConfig?.server_secret_set ? '留空保持不变' : '与服务器 LICENSE_HMAC_SECRET 一致'" />
              <div class="text-xs mt-1" style="color: var(--text-faint)">用于验证服务器响应的真实性</div>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm mb-1.5" style="color: var(--text-muted)">心跳间隔（天）</label>
                <input v-model.number="configForm.heartbeat_interval_days" type="number" min="1" max="30" class="input text-sm" />
              </div>
              <div>
                <label class="block text-sm mb-1.5" style="color: var(--text-muted)">离线宽限期（天）</label>
                <input v-model.number="configForm.grace_period_days" type="number" min="1" max="90" class="input text-sm" />
              </div>
            </div>
          </template>

          <div class="flex items-center gap-3">
            <button @click="saveConfig" :disabled="configSaving" class="btn-primary text-sm disabled:opacity-50">
              {{ configSaving ? '保存中...' : '保存配置' }}
            </button>
            <div v-if="licenseConfig?.instance_id" class="text-xs" style="color: var(--text-faint)">
              Instance ID: <span class="font-mono">{{ licenseConfig.instance_id.substring(0, 8) }}...</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 生成授权码 -->
      <div class="card p-5 space-y-4">
        <h3 class="font-medium flex items-center gap-2" style="color: var(--text-primary)">
          <span>＋</span> 生成授权码
        </h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm mb-1.5" style="color: var(--text-muted)">授权类型</label>
            <select v-model="genForm.license_type" class="input">
              <option value="permanent">永久授权</option>
              <option value="subscription">订阅授权</option>
            </select>
          </div>
          <div>
            <label class="block text-sm mb-1.5" style="color: var(--text-muted)">最大设备数</label>
            <input v-model.number="genForm.max_devices" type="number" min="1" max="100" class="input" />
          </div>
          <div v-if="genForm.license_type === 'subscription'">
            <label class="block text-sm mb-1.5" style="color: var(--text-muted)">有效期（天）</label>
            <input v-model.number="genForm.expiry_days" type="number" min="1" class="input" placeholder="如 365" />
          </div>
          <div>
            <label class="block text-sm mb-1.5" style="color: var(--text-muted)">备注</label>
            <input v-model="genForm.note" class="input" placeholder="可选备注" />
          </div>
        </div>
        <div class="flex items-center gap-3">
          <button @click="generateKey" :disabled="genLoading" class="btn-primary text-sm disabled:opacity-50">
            {{ genLoading ? '生成中...' : '生成授权码' }}
          </button>
        </div>
      </div>

      <!-- 生成的授权码展示（仅显示一次） -->
      <div v-if="generatedKey" class="card p-5 border border-emerald-500/30 bg-emerald-500/5">
        <h3 class="font-medium text-emerald-400 mb-3">✓ 授权码已生成</h3>
        <div class="bg-[var(--bg-input)] rounded-lg p-4 mb-3">
          <div class="text-xs mb-1" style="color: var(--text-faint)">授权码（请妥善保存，仅显示一次）</div>
          <div class="font-mono text-lg font-bold text-emerald-400 break-all">{{ generatedKey }}</div>
        </div>
        <button @click="copyKey" class="btn-secondary text-sm">
          {{ copied ? '已复制！' : '复制授权码' }}
        </button>
      </div>

      <!-- 授权码列表 -->
      <div class="card p-5">
        <h3 class="font-medium mb-4" style="color: var(--text-primary)">授权码列表</h3>
        <div v-if="loadingList" class="text-sm" style="color: var(--text-muted)">加载中...</div>
        <div v-else-if="licenseList.length === 0" class="text-sm py-8 text-center" style="color: var(--text-muted)">
          暂无授权码，请点击上方生成
        </div>
        <div v-else class="space-y-3">
          <div v-for="key in licenseList" :key="key.id"
            class="p-4 rounded-xl border transition-colors"
            :style="{
              borderColor: key.is_revoked ? 'rgba(248, 113, 113, 0.3)' : 'var(--border-primary)',
              background: key.is_revoked ? 'rgba(248, 113, 113, 0.05)' : 'var(--bg-input)',
            }">
            <div class="flex items-center justify-between">
              <div class="min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="font-mono font-medium text-sm">{{ key.key_display }}</span>
                  <span v-if="key.is_revoked" class="text-xs px-1.5 py-0.5 rounded bg-red-500/10 text-red-400">已吊销</span>
                  <span class="text-xs px-1.5 py-0.5 rounded"
                    :class="key.license_type === 'permanent' ? 'bg-brand-500/10 text-brand-400' : 'bg-amber-500/10 text-amber-400'">
                    {{ key.license_type === 'permanent' ? '永久' : '订阅' }}
                  </span>
                </div>
                <div class="text-xs mt-1" style="color: var(--text-muted)">
                  设备: {{ key.active_device_count }}/{{ key.max_devices }}
                  <span v-if="key.expiry_date"> · 到期: {{ formatDate(key.expiry_date) }}</span>
                  <span v-if="key.note"> · {{ key.note }}</span>
                </div>
              </div>
              <div class="flex items-center gap-1 shrink-0 ml-2">
                <button @click="viewActivations(key)" class="p-1.5 rounded-lg hover:bg-[var(--bg-hover)]"
                  style="color: var(--text-muted)" title="查看设备">
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                  </svg>
                </button>
                <button v-if="!key.is_revoked" @click="revokeKey(key)" class="p-1.5 rounded-lg hover:bg-red-500/10 hover:text-red-400"
                  style="color: var(--text-muted)" title="吊销">
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 普通用户视图：激活授权 -->
    <template v-else>
      <div class="card p-5 space-y-4">
        <h3 class="font-medium" style="color: var(--text-primary)">激活 Plus 授权</h3>
        <div v-if="licenseStatus?.is_plus && licenseStatus.device_name" class="text-sm" style="color: var(--text-muted)">
          当前设备「{{ licenseStatus.device_name }}」已激活 Plus 版。
          <button @click="unbindCurrent" class="text-red-400 hover:underline ml-2">解绑此设备</button>
        </div>
        <div v-else class="space-y-3">
          <div>
            <label class="block text-sm mb-1.5" style="color: var(--text-muted)">授权码</label>
            <input v-model="activateKey" class="input font-mono" placeholder="格式：MS-XXXX-XXXX-XXXX-XXXX" />
          </div>
          <button @click="activateLicense" :disabled="!activateKey || activateLoading"
            class="btn-primary text-sm disabled:opacity-50">
            {{ activateLoading ? '激活中...' : '激活授权' }}
          </button>
        </div>
      </div>
    </template>

    <!-- 激活设备列表弹窗（管理员） -->
    <AppModal v-model:show="activationModal.show" :title="`设备列表 - ${activationModal.keyDisplay}`">
      <div class="space-y-3 max-h-96 overflow-y-auto">
        <div v-if="activationModal.loading" class="text-sm" style="color: var(--text-muted)">加载中...</div>
        <div v-else-if="activationModal.activations.length === 0" class="text-sm py-4 text-center" style="color: var(--text-muted)">
          暂无激活设备
        </div>
        <div v-for="act in activationModal.activations" :key="act.id"
          class="p-3 rounded-lg flex items-center justify-between"
          :style="{ background: act.is_active ? 'var(--bg-input)' : 'rgba(255,255,255,0.02)' }">
          <div>
            <div class="font-medium text-sm">{{ act.device_name || '未知设备' }}</div>
            <div class="text-xs mt-0.5 font-mono" style="color: var(--text-faint)">
              指纹: {{ act.device_fingerprint_short }} · 最后活跃: {{ formatDate(act.last_seen_at) }}
            </div>
            <div v-if="!act.is_active" class="text-xs mt-0.5 text-red-400">
              已解绑 {{ formatDate(act.unbound_at) }}
            </div>
          </div>
          <button v-if="act.is_active && isAdmin" @click="unbindDevice(act.id)"
            class="p-1.5 rounded hover:bg-red-500/10 text-red-400" title="解绑">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
            </svg>
          </button>
        </div>
      </div>
    </AppModal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { licenseApi, type LicenseConfigOut, type LicenseHeartbeatStatus } from '@/api/license'
import { useToast } from '@/composables/useToast'
import AppModal from '@/components/AppModal.vue'

const props = defineProps<{ isAdmin?: boolean }>()
const toast = useToast()

// ── 状态 ──
const licenseStatus = ref<any>(null)
const loadingStatus = ref(false)
const licenseList = ref<any[]>([])
const loadingList = ref(false)
const generatedKey = ref('')
const genLoading = ref(false)
const copied = ref(false)
const activateKey = ref('')
const activateLoading = ref(false)

// ── 配置 ──
const licenseConfig = ref<LicenseConfigOut | null>(null)
const configLoading = ref(false)
const configSaving = ref(false)
const testResult = ref<{ success: boolean; message: string } | null>(null)
const testingConn = ref(false)
const configForm = ref({
  verification_mode: 'local' as string,
  server_url: '',
  server_secret: '',
  heartbeat_interval_days: 7,
  grace_period_days: 14,
})

// ── 心跳 ──
const heartbeatStatus = ref<LicenseHeartbeatStatus | null>(null)
const refreshLoading = ref(false)

const genForm = ref({
  license_type: 'permanent',
  max_devices: 3,
  expiry_days: null as number | null,
  note: '',
})

const activationModal = ref({
  show: false,
  keyDisplay: '',
  activations: [] as any[],
  loading: false,
  keyId: null as number | null,
})

// ── 计算属性 ──
const statusIconClass = computed(() => {
  if (!licenseStatus.value?.is_plus) return 'text-amber-400'
  if (licenseStatus.value.in_grace_period) return 'text-amber-400'
  return 'text-emerald-400'
})

const statusTitle = computed(() => {
  if (!licenseStatus.value?.is_plus) return '免费版'
  if (licenseStatus.value.in_grace_period) return 'Plus 版（宽限期）'
  return 'Plus 版已激活'
})

const modeTagText = computed(() => {
  const mode = licenseStatus.value?.verification_mode || 'local'
  return mode === 'online' ? 'Online' : 'Local'
})

const modeTagClass = computed(() => {
  const mode = licenseStatus.value?.verification_mode || 'local'
  return mode === 'online'
    ? 'bg-emerald-500/10 text-emerald-400'
    : 'bg-[var(--bg-hover)] text-[var(--text-secondary)]'
})

const isHeartbeatOverdue = computed(() => {
  if (!heartbeatStatus.value?.next_heartbeat_at) return false
  return new Date(heartbeatStatus.value.next_heartbeat_at) < new Date()
})

// ── 数据加载 ──
async function fetchStatus() {
  loadingStatus.value = true
  try {
    const { data } = await licenseApi.getStatus()
    licenseStatus.value = data
  } catch (e: any) {
    console.error('获取授权状态失败:', e)
  } finally {
    loadingStatus.value = false
  }
}

async function fetchList() {
  if (!props.isAdmin) return
  loadingList.value = true
  try {
    const { data } = await licenseApi.list()
    licenseList.value = data
  } catch (e: any) {
    console.error('获取授权列表失败:', e)
  } finally {
    loadingList.value = false
  }
}

async function fetchConfig() {
  if (!props.isAdmin) return
  configLoading.value = true
  try {
    const { data } = await licenseApi.getConfig()
    licenseConfig.value = data
    configForm.value = {
      verification_mode: data.verification_mode,
      server_url: data.server_url || '',
      server_secret: '', // 不回显密钥
      heartbeat_interval_days: data.heartbeat_interval_days,
      grace_period_days: data.grace_period_days,
    }
  } catch (e: any) {
    console.error('获取配置失败:', e)
  } finally {
    configLoading.value = false
  }
}

async function fetchHeartbeatStatus() {
  try {
    const { data } = await licenseApi.getHeartbeatStatus()
    heartbeatStatus.value = data
  } catch {
    heartbeatStatus.value = null
  }
}

// ── 配置操作 ──
async function testConnection() {
  if (!configForm.value.server_url) return
  testingConn.value = true
  testResult.value = null
  try {
    const { data } = await licenseApi.testConnection(configForm.value.server_url)
    testResult.value = data
  } catch (e: any) {
    testResult.value = { success: false, message: '请求失败' }
  } finally {
    testingConn.value = false
  }
}

async function saveConfig() {
  configSaving.value = true
  try {
    const payload: any = {
      verification_mode: configForm.value.verification_mode,
    }
    if (configForm.value.verification_mode === 'online') {
      payload.server_url = configForm.value.server_url || null
      if (configForm.value.server_secret) {
        payload.server_secret = configForm.value.server_secret
      }
      payload.heartbeat_interval_days = configForm.value.heartbeat_interval_days
      payload.grace_period_days = configForm.value.grace_period_days
    }
    await licenseApi.updateConfig(payload)
    toast.success('配置已保存')
    // 重新加载配置和状态
    await fetchConfig()
    await fetchStatus()
    if (licenseConfig.value?.verification_mode === 'online') {
      await fetchHeartbeatStatus()
    }
  } catch (e: any) {
    toast.error(`保存失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    configSaving.value = false
  }
}

async function refreshLicense() {
  refreshLoading.value = true
  try {
    await licenseApi.refreshLicense()
    toast.success('授权已刷新')
    await fetchStatus()
    await fetchHeartbeatStatus()
  } catch (e: any) {
    toast.error(`刷新失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    refreshLoading.value = false
  }
}

// ── 授权码管理 ──
async function generateKey() {
  genLoading.value = true
  generatedKey.value = ''
  try {
    const payload: any = {
      license_type: genForm.value.license_type,
      max_devices: genForm.value.max_devices,
    }
    if (genForm.value.expiry_days) payload.expiry_days = genForm.value.expiry_days
    if (genForm.value.note) payload.note = genForm.value.note

    const { data } = await licenseApi.generate(payload)
    generatedKey.value = data.key_display
    toast.success('授权码已生成')
    await fetchList()
  } catch (e: any) {
    toast.error(`生成失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    genLoading.value = false
  }
}

async function revokeKey(key: any) {
  if (!await toast.confirm({ title: '吊销授权码', message: `确定要吊销「${key.key_display}」吗？已激活设备将失效。`, danger: true })) return
  try {
    await licenseApi.revoke(key.id)
    toast.success('授权码已吊销')
    await fetchList()
    await fetchStatus()
  } catch (e: any) {
    toast.error(`吊销失败: ${e.response?.data?.detail || e.message}`)
  }
}

async function viewActivations(key: any) {
  activationModal.value = {
    show: true,
    keyDisplay: key.key_display,
    activations: [],
    loading: true,
    keyId: key.id,
  }
  try {
    const { data } = await licenseApi.getActivations(key.id)
    activationModal.value.activations = data
  } catch (e: any) {
    toast.error('获取设备列表失败')
  } finally {
    activationModal.value.loading = false
  }
}

async function unbindDevice(activationId: number) {
  if (!await toast.confirm({ title: '解绑设备', message: '确定要解绑此设备吗？该设备需要重新激活才能使用 Plus 功能。', danger: true })) return
  try {
    await licenseApi.unbindDevice(activationId)
    toast.success('设备已解绑')
    if (activationModal.value.keyId) {
      const { data } = await licenseApi.getActivations(activationModal.value.keyId)
      activationModal.value.activations = data
    }
    await fetchList()
    await fetchStatus()
  } catch (e: any) {
    toast.error(`解绑失败: ${e.response?.data?.detail || e.message}`)
  }
}

async function activateLicense() {
  activateLoading.value = true
  try {
    await licenseApi.activate(activateKey.value)
    toast.success('授权激活成功！系统已升级为 Plus 版')
    activateKey.value = ''
    await fetchStatus()
  } catch (e: any) {
    toast.error(`激活失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    activateLoading.value = false
  }
}

async function unbindCurrent() {
  if (!await toast.confirm({ title: '解绑设备', message: '确定要解绑当前设备吗？解绑后将退回免费版。', danger: true })) return
  try {
    await licenseApi.unbindCurrent()
    toast.success('当前设备已解绑')
    await fetchStatus()
  } catch (e: any) {
    toast.error(`解绑失败: ${e.response?.data?.detail || e.message}`)
  }
}

function copyKey() {
  navigator.clipboard.writeText(generatedKey.value)
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

function formatDate(d: string) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

function formatDateTime(d: string | null) {
  if (!d) return ''
  return new Date(d).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

onMounted(() => {
  fetchStatus()
  fetchList()
  if (props.isAdmin) {
    fetchConfig()
  }
  // 如果是 online 模式，加载心跳状态
  fetchHeartbeatStatus().then(() => {
    if (heartbeatStatus.value?.verification_mode === 'online') {
      // 已经加载了
    }
  })
})
</script>
