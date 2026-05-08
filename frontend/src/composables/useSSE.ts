import { ref, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

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

  function connect() {
    if (eventSource) {
      eventSource.close()
    }

    const auth = useAuthStore()
    const baseUrl = import.meta.env.VITE_API_URL || ''
    // SSE URL 带上 token 作为查询参数（EventSource 不支持自定义 header）
    const token = localStorage.getItem('access_token') || ''
    const url = `${baseUrl}/api/system/events?token=${encodeURIComponent(token)}`

    eventSource = new EventSource(url)

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
        const delay = BASE_RECONNECT_DELAY * Math.pow(1.5, reconnectAttempts - 1)
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
