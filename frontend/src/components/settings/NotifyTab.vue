<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-sm" style="color: var(--text-muted)">配置消息通知渠道（Telegram / 企业微信 / Bark / Webhook）</p>
      <button @click="openModal()" class="btn-primary text-sm flex items-center gap-1">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
        添加渠道
      </button>
    </div>

    <div class="space-y-3">
      <div v-for="ch in channels" :key="ch.id" class="card p-4">
        <div class="flex items-start justify-between">
          <div class="space-y-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="font-medium">{{ ch.name }}</span>
              <span class="text-xs bg-[var(--bg-input)] px-2 py-0.5 rounded border border-[var(--border-primary)]" style="color: var(--text-muted)">{{ typeLabel(ch.channel_type) }}</span>
            </div>
            <div class="text-xs truncate" style="color: var(--text-muted)">
              <template v-if="ch.channel_type === 'telegram'">Bot ID: {{ ch.config?.bot_id || ch.config?.bot_token?.slice(0, 10) }}</template>
              <template v-else-if="ch.channel_type === 'wechat'">SendKey: {{ ch.config?.sendkey?.slice(0, 8) }}...</template>
              <template v-else-if="ch.channel_type === 'bark'">设备: {{ ch.config?.device_key?.slice(0, 8) }}</template>
              <template v-else-if="ch.channel_type === 'webhook'">URL: {{ ch.config?.url }}</template>
            </div>
          </div>
          <div class="flex items-center gap-1 shrink-0 ml-2">
            <button @click="testNotify(ch.id)" :disabled="testingId === ch.id"
              class="btn-secondary text-xs disabled:opacity-50">
              {{ testingId === ch.id ? '发送中...' : '发送测试' }}
            </button>
            <button @click="openModal(ch)"
              class="p-1.5 rounded-lg transition-colors hover:bg-[var(--bg-hover)]" style="color: var(--text-muted)">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
            </button>
            <button @click="confirmDelete(ch)"
              class="p-1.5 rounded-lg transition-colors hover:bg-red-500/10 hover:text-red-400" style="color: var(--text-muted)">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <AppEmpty v-if="channels.length === 0" message="暂无通知渠道" />

    <!-- 弹窗 -->
    <AppModal v-model:show="modal.show" :title="modal.editing ? '编辑通知渠道' : '添加通知渠道'">
      <div class="space-y-4">
        <div>
          <label class="block text-sm mb-1" style="color: var(--text-muted)">名称</label>
          <input v-model="modal.name" placeholder="例如: Telegram 通知" class="input" />
        </div>
        <div>
          <label class="block text-sm mb-1" style="color: var(--text-muted)">渠道类型</label>
          <select v-model="modal.channel_type" class="input">
            <option value="telegram">Telegram</option>
            <option value="wechat">企业微信 (Server酱)</option>
            <option value="bark">Bark (iOS)</option>
            <option value="webhook">Webhook</option>
          </select>
        </div>

        <template v-if="modal.channel_type === 'telegram'">
          <div>
            <label class="block text-sm mb-1" style="color: var(--text-muted)">Bot Token</label>
            <input v-model="modal.config.bot_token" placeholder="123456:ABC-DEF..." class="input" />
          </div>
          <div>
            <label class="block text-sm mb-1" style="color: var(--text-muted)">Chat ID</label>
            <input v-model="modal.config.chat_id" placeholder="-100123456" class="input" />
          </div>
        </template>

        <template v-if="modal.channel_type === 'wechat'">
          <div>
            <label class="block text-sm mb-1" style="color: var(--text-muted)">SendKey</label>
            <input v-model="modal.config.sendkey" placeholder="SCT..." class="input" />
          </div>
        </template>

        <template v-if="modal.channel_type === 'bark'">
          <div>
            <label class="block text-sm mb-1" style="color: var(--text-muted)">设备 Key</label>
            <input v-model="modal.config.device_key" placeholder="https://api.day.app/xxx" class="input" />
          </div>
          <div>
            <label class="block text-sm mb-1" style="color: var(--text-muted)">服务器地址（可选）</label>
            <input v-model="modal.config.server" placeholder="https://api.day.app" class="input" />
          </div>
        </template>

        <template v-if="modal.channel_type === 'webhook'">
          <div>
            <label class="block text-sm mb-1" style="color: var(--text-muted)">URL</label>
            <input v-model="modal.config.url" placeholder="https://example.com/notify" class="input" />
          </div>
          <div>
            <label class="block text-sm mb-1" style="color: var(--text-muted)">Method</label>
            <select v-model="modal.config.method" class="input">
              <option value="POST">POST</option>
              <option value="GET">GET</option>
            </select>
          </div>
          <div>
            <label class="block text-sm mb-1" style="color: var(--text-muted)">Headers (JSON)</label>
            <textarea v-model="modal.config.headers" rows="2" placeholder='{"Content-Type": "application/json"}'
              class="input resize-none text-xs font-mono" />
          </div>
          <div>
            <label class="block text-sm mb-1" style="color: var(--text-muted)">Body 模板 (JSON)</label>
            <textarea v-model="modal.config.body_template" rows="3"
              placeholder='{"title": "{{title}}", "message": "{{message}}"}'
              class="input resize-none text-xs font-mono" />
          </div>
        </template>
      </div>
      <template #footer>
        <button @click="modal.show = false" class="btn-secondary text-sm">取消</button>
        <button @click="save" class="btn-primary text-sm">保存</button>
      </template>
    </AppModal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { subscribeApi } from '@/api/subscribe'
import { useToast } from '@/composables/useToast'
import AppModal from '@/components/AppModal.vue'
import AppEmpty from '@/components/AppEmpty.vue'

const toast = useToast()
const channels = ref<any[]>([])
const testingId = ref<number | null>(null)
const modal = ref({
  show: false, editing: null as any,
  name: '', channel_type: 'telegram', config: {} as any,
})

function typeLabel(type: string) {
  const map: Record<string, string> = { telegram: 'Telegram', wechat: '企业微信', bark: 'Bark', webhook: 'Webhook' }
  return map[type] || type
}

function openModal(ch?: any) {
  modal.value = ch
    ? { show: true, editing: ch, name: ch.name, channel_type: ch.channel_type, config: { ...ch.config } }
    : { show: true, editing: null, name: '', channel_type: 'telegram', config: {} }
}

async function save() {
  try {
    const payload = { name: modal.value.name, channel_type: modal.value.channel_type, config: modal.value.config }
    if (modal.value.editing) {
      await subscribeApi.updateNotifyChannel(modal.value.editing.id, payload)
    } else {
      await subscribeApi.createNotifyChannel(payload)
    }
    modal.value.show = false
    toast.success('保存成功')
    await loadChannels()
  } catch (e: any) {
    toast.error(`保存失败: ${e.response?.data?.detail || e.message}`)
  }
}

async function testNotify(id: number) {
  testingId.value = id
  try {
    await subscribeApi.testNotifyChannel(id)
    toast.success('测试消息已发送！')
  } catch (e: any) {
    toast.error(`发送失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    testingId.value = null
  }
}

async function confirmDelete(ch: any) {
  const ok = await toast.confirm({
    title: '删除通知渠道',
    message: `确定要删除通知渠道「${ch.name}」吗？`,
    confirmText: '删除',
    danger: true,
  })
  if (!ok) return
  try {
    await subscribeApi.deleteNotifyChannel(ch.id)
    toast.success('已删除')
    await loadChannels()
  } catch (e: any) {
    toast.error(`删除失败: ${e.response?.data?.detail || e.message}`)
  }
}

async function loadChannels() {
  try {
    const { data } = await subscribeApi.getNotifyChannels()
    channels.value = Array.isArray(data) ? data : data.items || []
  } catch (e) {
    console.error('加载通知渠道失败:', e)
  }
}

onMounted(() => loadChannels())
</script>
