<template>
  <div class="flex flex-col h-screen max-h-screen" style="background: var(--bg-base)">
    <!-- 顶部标题栏 -->
    <div class="px-6 py-4 border-b flex items-center justify-between shrink-0" style="border-color: var(--border-color)">
      <div class="flex items-center gap-3">
        <!-- AI 图标 -->
        <div class="w-10 h-10 rounded-xl flex items-center justify-center bg-gradient-to-br from-brand-500 to-purple-600 shadow-lg">
          <svg class="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
          </svg>
        </div>
        <div>
          <h1 class="text-lg font-semibold">AI 助手</h1>
          <p class="text-xs" style="color: var(--text-muted)">智能媒体管理助手 · 自然语言操控系统</p>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <!-- 会话选择 -->
        <select
          v-model="currentSessionId"
          @change="loadSession"
          class="input text-sm py-1 px-3 rounded-lg min-w-[160px]"
        >
          <option value="">新建对话</option>
          <option v-for="s in sessions" :key="s.session_id" :value="s.session_id">
            {{ s.last_message ? s.last_message.slice(0, 24) + '…' : '新会话' }}
            ({{ s.message_count }} 条)
          </option>
        </select>
        <!-- 清空按钮 -->
        <button
          v-if="currentSessionId"
          @click="deleteSession"
          class="btn-ghost text-sm text-red-400 flex items-center gap-1"
          title="删除此会话"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
          </svg>
        </button>
        <!-- 历史记录 -->
        <button @click="showHistory = true" class="btn-secondary text-sm flex items-center gap-2">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          操作历史
        </button>
      </div>
    </div>

    <!-- 主体：聊天区 + 侧边操作历史 -->
    <div class="flex flex-1 overflow-hidden">

      <!-- 聊天主区域 -->
      <div class="flex flex-col flex-1 overflow-hidden">
        <!-- 消息列表 -->
        <div ref="msgContainer" class="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          <!-- 欢迎提示（空对话时显示） -->
          <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full gap-6 py-12">
            <div class="w-16 h-16 rounded-2xl flex items-center justify-center bg-gradient-to-br from-brand-500 to-purple-600 shadow-xl">
              <svg class="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                  d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
              </svg>
            </div>
            <div class="text-center max-w-md">
              <h2 class="text-xl font-semibold mb-2">你好！我是 MediaStation AI 助手</h2>
              <p class="text-sm" style="color: var(--text-muted)">我可以帮你管理媒体库、执行批量操作、获取统计报告等。试试对我说：</p>
            </div>
            <!-- 快捷提示 -->
            <div class="grid grid-cols-2 gap-3 w-full max-w-lg">
              <button
                v-for="hint in quickHints" :key="hint.text"
                @click="sendMessage(hint.text)"
                class="card p-3 text-left hover:border-brand-400 transition-colors cursor-pointer group"
              >
                <div class="text-lg mb-1">{{ hint.icon }}</div>
                <div class="text-sm font-medium">{{ hint.text }}</div>
                <div class="text-xs mt-0.5" style="color: var(--text-muted)">{{ hint.desc }}</div>
              </button>
            </div>
          </div>

          <!-- 消息气泡 -->
          <template v-for="(msg, i) in messages" :key="i">
            <!-- 用户消息 -->
            <div v-if="msg.role === 'user'" class="flex justify-end">
              <div class="max-w-[70%]">
                <div class="bg-brand-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed">
                  {{ msg.content }}
                </div>
                <div class="text-xs mt-1 text-right" style="color: var(--text-muted)">{{ formatTime(msg.timestamp) }}</div>
              </div>
            </div>

            <!-- AI 消息 -->
            <div v-else class="flex gap-3 max-w-[85%]">
              <div class="w-8 h-8 rounded-full bg-gradient-to-br from-brand-500 to-purple-600 flex items-center justify-center shrink-0 mt-1">
                <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M13 6a3 3 0 11-6 0 3 3 0 016 0zM18 8a2 2 0 11-4 0 2 2 0 014 0zM14 15a4 4 0 00-8 0v3h8v-3zM6 8a2 2 0 11-4 0 2 2 0 014 0zM16 18v-3a5.972 5.972 0 00-.75-2.906A3.005 3.005 0 0119 15v3h-3zM4.75 12.094A5.973 5.973 0 004 15v3H1v-3a3 3 0 013.75-2.906z"/>
                </svg>
              </div>
              <div>
                <div class="card px-4 py-3 text-sm leading-relaxed rounded-2xl rounded-tl-sm" style="background: var(--bg-card)">
                  <div v-html="renderMarkdown(msg.content)" class="prose-sm" />
                </div>

                <!-- 建议操作按钮 -->
                <div v-if="msg.suggested_action" class="mt-2 flex gap-2">
                  <button
                    @click="executeAction(msg.suggested_action)"
                    :disabled="executing"
                    class="btn-primary text-xs flex items-center gap-1.5 py-1.5 px-3"
                  >
                    <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3l14 9-14 9V3z"/>
                    </svg>
                    {{ msg.suggested_action.label || '执行操作' }}
                  </button>
                  <button
                    v-if="msg.suggested_action.requires_confirmation"
                    class="btn-ghost text-xs text-gray-400 py-1.5 px-3"
                  >
                    取消
                  </button>
                </div>

                <div class="text-xs mt-1.5" style="color: var(--text-muted)">{{ formatTime(msg.timestamp) }}</div>
              </div>
            </div>
          </template>

          <!-- 打字动画 -->
          <div v-if="thinking" class="flex gap-3 max-w-[85%]">
            <div class="w-8 h-8 rounded-full bg-gradient-to-br from-brand-500 to-purple-600 flex items-center justify-center shrink-0">
              <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path d="M13 6a3 3 0 11-6 0 3 3 0 016 0zM18 8a2 2 0 11-4 0 2 2 0 014 0zM14 15a4 4 0 00-8 0v3h8v-3zM6 8a2 2 0 11-4 0 2 2 0 014 0zM16 18v-3a5.972 5.972 0 00-.75-2.906A3.005 3.005 0 0119 15v3h-3zM4.75 12.094A5.973 5.973 0 004 15v3H1v-3a3 3 0 013.75-2.906z"/>
              </svg>
            </div>
            <div class="card px-4 py-3 rounded-2xl rounded-tl-sm" style="background: var(--bg-card)">
              <div class="flex gap-1 items-center h-5">
                <span v-for="j in 3" :key="j"
                  class="w-2 h-2 rounded-full bg-brand-400 animate-bounce"
                  :style="{ animationDelay: `${(j - 1) * 0.15}s` }" />
              </div>
            </div>
          </div>

          <!-- 执行结果提示 -->
          <Transition name="fade">
            <div v-if="lastResult" class="mx-auto max-w-lg">
              <div
                class="card px-4 py-3 text-sm rounded-xl flex items-start gap-2 border"
                :class="lastResult.success
                  ? 'border-green-500/30 bg-green-500/5 text-green-400'
                  : 'border-red-500/30 bg-red-500/5 text-red-400'"
              >
                <svg class="w-4 h-4 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path v-if="lastResult.success" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                  <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                <div>
                  <div class="font-medium">{{ lastResult.success ? '操作成功' : '操作失败' }}</div>
                  <div class="opacity-80 mt-0.5">{{ lastResult.message }}</div>
                  <button
                    v-if="lastResult.op_id && lastResult.undoable"
                    @click="undoOperation(lastResult.op_id)"
                    class="text-xs underline mt-1 opacity-70 hover:opacity-100"
                  >
                    撤销此操作
                  </button>
                </div>
              </div>
            </div>
          </Transition>
        </div>

        <!-- 输入区域 -->
        <div class="px-6 py-4 border-t shrink-0" style="border-color: var(--border-color); background: var(--bg-card)">
          <!-- 快捷操作栏 -->
          <div class="flex gap-2 mb-3 overflow-x-auto pb-1 scrollbar-hide">
            <button
              v-for="op in quickOps" :key="op.label"
              @click="sendMessage(op.message)"
              class="shrink-0 text-xs btn-ghost py-1 px-3 rounded-full border"
              style="border-color: var(--border-color)"
            >
              {{ op.icon }} {{ op.label }}
            </button>
          </div>
          <!-- 输入框 -->
          <div class="flex gap-3 items-end">
            <textarea
              v-model="inputText"
              @keydown.enter.exact.prevent="onEnterSend"
              @keydown.shift.enter="onShiftEnter"
              placeholder="输入消息…（Enter 发送，Shift+Enter 换行）"
              rows="1"
              ref="inputRef"
              class="input flex-1 resize-none rounded-xl text-sm py-3 px-4 leading-relaxed"
              style="min-height: 48px; max-height: 200px"
              @input="autoResize"
            />
            <button
              @click="onEnterSend"
              :disabled="!inputText.trim() || thinking"
              class="btn-primary rounded-xl w-12 h-12 flex items-center justify-center shrink-0"
            >
              <svg v-if="!thinking" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
              </svg>
              <svg v-else class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
            </button>
          </div>
          <div class="text-xs mt-2" style="color: var(--text-muted)">AI 助手基于规则引擎，不连接外部 AI 服务，数据完全本地处理</div>
        </div>
      </div>

    </div>

    <!-- 操作历史弹窗 -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showHistory" class="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="showHistory = false" />
          <div class="relative card rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col" style="background: var(--bg-card)">
            <div class="flex items-center justify-between px-6 py-4 border-b" style="border-color: var(--border-color)">
              <h3 class="font-semibold">操作历史</h3>
              <button @click="showHistory = false" class="btn-ghost text-gray-400">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </button>
            </div>
            <div class="flex-1 overflow-y-auto p-4 space-y-2">
              <div v-if="opHistory.length === 0" class="text-center py-8 text-sm" style="color: var(--text-muted)">
                暂无操作历史
              </div>
              <div
                v-for="op in opHistory" :key="op.id"
                class="card p-3 rounded-xl flex items-start gap-3"
              >
                <!-- 状态图标 -->
                <div class="mt-0.5 w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-sm"
                  :class="{
                    'bg-green-500/20 text-green-400': op.status === 'completed',
                    'bg-red-500/20 text-red-400': op.status === 'failed',
                    'bg-gray-500/20 text-gray-400': op.status === 'undone',
                  }"
                >
                  <svg v-if="op.status === 'completed'" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                  </svg>
                  <svg v-else-if="op.status === 'failed'" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                  </svg>
                  <svg v-else class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
                  </svg>
                </div>
                <div class="flex-1 min-w-0">
                  <div class="text-sm font-medium truncate">{{ op.description || op.operation }}</div>
                  <div class="text-xs mt-0.5" style="color: var(--text-muted)">{{ op.result_message }}</div>
                  <div class="text-xs mt-1" style="color: var(--text-muted)">{{ formatTime(op.executed_at) }}</div>
                </div>
                <button
                  v-if="op.undoable && op.status === 'completed'"
                  @click="undoOperation(op.id)"
                  class="btn-ghost text-xs text-brand-400 shrink-0"
                >
                  撤销
                </button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import api from '@/api/client'

// ── 状态 ──
const inputText = ref('')
const messages = ref<any[]>([])
const thinking = ref(false)
const executing = ref(false)
const currentSessionId = ref('')
const sessions = ref<any[]>([])
const opHistory = ref<any[]>([])
const showHistory = ref(false)
const lastResult = ref<any>(null)
const msgContainer = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)

// ── 快捷提示 ──
const quickHints = [
  { icon: '📚', text: '扫描所有媒体库', desc: '自动发现新文件' },
  { icon: '🎬', text: '查看系统统计报告', desc: '播放量、用户活跃度' },
  { icon: '🔍', text: '搜索动作片', desc: '智能本地搜索' },
  { icon: '⭐', text: '收藏评分最高的10部', desc: '按评分筛选收藏' },
]

const quickOps = [
  { icon: '📡', label: '扫描媒体库', message: '扫描所有媒体库' },
  { icon: '📊', label: '系统统计', message: '给我看一下系统统计报告' },
  { icon: '🔍', label: '搜索媒体', message: '搜索' },
  { icon: '🎯', label: '刮削元数据', message: '刮削最近添加的媒体元数据' },
  { icon: '🗑️', label: '清理重复文件', message: '检测并清理重复文件' },
]

// ── 时间格式化 ──
function formatTime(ts?: string): string {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

// ── Markdown 简易渲染 ──
function renderMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code class="bg-gray-500/20 px-1 rounded text-xs">$1</code>')
    .replace(/\n/g, '<br>')
}

// ── 滚动到底部 ──
async function scrollToBottom() {
  await nextTick()
  if (msgContainer.value) {
    msgContainer.value.scrollTop = msgContainer.value.scrollHeight
  }
}

// ── 自动调整输入框高度 ──
function autoResize(e: Event) {
  const el = e.target as HTMLTextAreaElement
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 200) + 'px'
}

// ── 发送消息 ──
async function sendMessage(text?: string) {
  const msg = (text || inputText.value).trim()
  if (!msg) return

  inputText.value = ''
  if (inputRef.value) {
    inputRef.value.style.height = '48px'
  }

  messages.value.push({
    role: 'user',
    content: msg,
    timestamp: new Date().toISOString(),
  })

  thinking.value = true
  lastResult.value = null
  await scrollToBottom()

  try {
    const resp = await api.post('/api/admin/assistant/chat', {
      message: msg,
      session_id: currentSessionId.value || undefined,
    })
    const data = (resp.data as any)?.data || resp.data
    currentSessionId.value = data.session_id

    messages.value.push({
      role: 'assistant',
      content: data.reply,
      timestamp: new Date().toISOString(),
      suggested_action: data.suggested_action,
      intent: data.intent,
    })
  } catch (err: any) {
    messages.value.push({
      role: 'assistant',
      content: `❌ 抱歉，出现了错误：${err.message || '请求失败'}`,
      timestamp: new Date().toISOString(),
    })
  } finally {
    thinking.value = false
    await scrollToBottom()
    await loadSessions()
  }
}

// ── Enter 发送 ──
function onEnterSend() {
  if (!inputText.value.trim() || thinking.value) return
  sendMessage()
}

function onShiftEnter() {
  // 允许换行，不需要处理
}

// ── 执行建议操作 ──
async function executeAction(action: any) {
  if (!action || executing.value) return
  executing.value = true
  lastResult.value = null

  try {
    const resp = await api.post('/api/admin/assistant/execute', {
      operation: action.operation,
      params: action.params || {},
      session_id: currentSessionId.value || undefined,
      description: action.label,
    })
    const data = (resp.data as any)?.data || resp.data
    lastResult.value = {
      ...data.result,
      op_id: data.op_id,
      undoable: data.undoable,
    }
    await loadHistory()
    await scrollToBottom()
  } catch (err: any) {
    lastResult.value = {
      success: false,
      message: err.message || '操作执行失败',
    }
  } finally {
    executing.value = false
    // 5 秒后自动清除结果提示
    setTimeout(() => { lastResult.value = null }, 6000)
  }
}

// ── 撤销操作 ──
async function undoOperation(opId: string) {
  try {
    await api.post(`/api/admin/assistant/undo/${opId}`)
    await loadHistory()
    lastResult.value = { success: true, message: '操作已撤销' }
    setTimeout(() => { lastResult.value = null }, 4000)
  } catch (err: any) {
    lastResult.value = { success: false, message: `撤销失败: ${err.message}` }
  }
}

// ── 加载会话列表 ──
async function loadSessions() {
  try {
    const resp = await api.get('/api/admin/assistant/sessions')
    const data = (resp.data as any)?.data || resp.data
    sessions.value = data.sessions || []
  } catch {}
}

// ── 加载会话历史 ──
async function loadSession() {
  if (!currentSessionId.value) {
    messages.value = []
    return
  }
  try {
    const resp = await api.get(`/api/admin/assistant/session/${currentSessionId.value}`)
    const data = (resp.data as any)?.data || resp.data
    messages.value = data.messages || []
    await scrollToBottom()
  } catch {}
}

// ── 删除会话 ──
async function deleteSession() {
  if (!currentSessionId.value) return
  try {
    await api.delete(`/api/admin/assistant/session/${currentSessionId.value}`)
    currentSessionId.value = ''
    messages.value = []
    await loadSessions()
  } catch {}
}

// ── 加载操作历史 ──
async function loadHistory() {
  try {
    const resp = await api.get('/api/admin/assistant/history')
    const data = (resp.data as any)?.data || resp.data
    opHistory.value = data.history || []
  } catch {}
}

onMounted(async () => {
  await Promise.all([loadSessions(), loadHistory()])
})
</script>

<style scoped>
.prose-sm strong { font-weight: 600; }
.prose-sm em { font-style: italic; opacity: 0.85; }

.fade-enter-active, .fade-leave-active { transition: all 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; transform: translateY(8px); }

.modal-enter-active, .modal-leave-active { transition: all 0.2s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from .card, .modal-leave-to .card { transform: scale(0.95); }
</style>
