import { ref, onUnmounted } from 'vue'
import api from '@/api/client'

export interface SSEEvent {
  type: string
  data: any
  timestamp: string
}

export function useSSE() {
  const events = ref<SSEEvent[]>([])
  const connected = ref(false)
  const error = ref<string | null>(null)
  let eventSource: EventSource | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectAttempts = 0
  const MAX_RECONNECT_ATTEMPTS = 10
  const BASE_RECONNECT_DELAY = 1000

  async function connect() {
    if (eventSource) {
      eventSource.close()
    }

    const baseUrl = import.meta.env.VITE_API_URL || ''

    // ── SSE Ticket 机制：避免 JWT 出现在 URL 中被 Nginx 日志记录 ──
    // 1. 通过标准 Authorization Header 请求一次性票据（10秒有效）
    try {
      const { data } = await api.get('/api/system/events/ticket', { timeout: 5000 })
      const ticket = data.ticket
      const url = `${baseUrl}/api/system/events?ticket=${encodeURIComponent(ticket)}`
      eventSource = new EventSource(url)
    } catch (err) {
      // Ticket 请求失败时降级到 URL token 方式（兼容）
      console.warn('[SSE] Ticket 获取失败，降级使用 token 参数:', err)
      const token = localStorage.getItem('access_token') || ''
      if (!token) {
        error.value = '未登录，无法建立 SSE 连接'
        return
      }
      const url = `${baseUrl}/api/system/events?token=${encodeURIComponent(token)}`
      eventSource = new EventSource(url)
    }

    eventSource.onopen = () => {
      connected.value = true
      error.value = null
      reconnectAttempts = 0
    }

    eventSource.onmessage = (e) => {
      try {
        const event: SSEEvent = JSON.parse(e.data)
        events.value.unshift(event)
        // 最多保留 200 条事件
        if (events.value.length > 200) {
          events.value = events.value.slice(0, 200)
        }
      } catch {
        // 忽略非 JSON 消息
      }
    }

    eventSource.onerror = () => {
      connected.value = false
      eventSource?.close()
      eventSource = null

      if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++
        // 指数退避：1000ms, 1500ms, 2250ms, 3375ms...
        const backoff = BASE_RECONNECT_DELAY * Math.pow(1.5, reconnectAttempts - 1)
        // 添加 0~2000ms 随机抖动，防止惊群效应
        const jitter = Math.random() * 2000
        const delay = Math.min(backoff + jitter, 30000)  // 最大30秒
        
        error.value = `连接断开，${Math.round(delay / 1000)}秒后重试... (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`
        reconnectTimer = setTimeout(() => connect(), delay)
      } else {
        error.value = 'SSE 连接失败，请检查网络或刷新页面'
      }
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
    connected.value = false
    reconnectAttempts = 0
  }

  // 按类型过滤事件
  function getEventsByType(type: string): SSEEvent[] {
    return events.value.filter(e => e.type === type)
  }

  // 获取最近 N 条事件
  function getRecent(count: number = 20): SSEEvent[] {
    return events.value.slice(0, count)
  }

  // 清空事件
  function clearEvents() {
    events.value = []
  }

  onUnmounted(() => {
    disconnect()
  })

  return {
    events,
    connected,
    error,
    connect,
    disconnect,
    getEventsByType,
    getRecent,
    clearEvents,
  }
}
