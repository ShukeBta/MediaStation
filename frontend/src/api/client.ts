import axios from 'axios'
import { ref, watch } from 'vue'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

// ---- 后端连接状态管理 ----
export const backendOnline = ref(true)
export const backendChecking = ref(false)

let checkTimer: ReturnType<typeof setTimeout> | null = null
let consecutiveFailures = 0
const MAX_CONSECUTIVE_FAILURES = 3 // 连续失败3次才判定离线，避免暂时性网络波动误报

// 检查后端是否在线
async function checkBackendHealth() {
  if (backendChecking.value) return

  backendChecking.value = true
  try {
    await axios.get(`${import.meta.env.VITE_API_URL || ''}/api/health`, { timeout: 5000 })
    consecutiveFailures = 0
    if (!backendOnline.value) {
      backendOnline.value = true
      console.log('[API] 后端已恢复连接')
    }
  } catch {
    consecutiveFailures++
    if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES && backendOnline.value) {
      backendOnline.value = false
      console.warn(`[API] 后端连接断开（连续 ${consecutiveFailures} 次健康检查失败）`)
    }
  } finally {
    backendChecking.value = false
  }
}

// 定期健康检查
function startHealthCheck() {
  if (checkTimer) return
  checkTimer = setInterval(() => {
    checkBackendHealth()
  }, 10000) // 每 10 秒检查一次
}

// 停止健康检查
export function stopHealthCheck() {
  if (checkTimer) {
    clearInterval(checkTimer)
    checkTimer = null
  }
}

// 启动健康检查
startHealthCheck()

// ---- Token 自动刷新 + 竞态保护 ----
let isRefreshing = false
let pendingRequests: Array<{ resolve: (token: string) => void; reject: (err: unknown) => void }> = []

function onRefreshed(newToken: string) {
  pendingRequests.forEach(({ resolve }) => resolve(newToken))
  pendingRequests = []
}

function onRefreshFailed(err: unknown) {
  pendingRequests.forEach(({ reject }) => reject(err))
  pendingRequests = []
}

// ---- 请求重试逻辑 ----
const MAX_RETRIES = 2
const RETRY_DELAY = 1000 // 1秒

// 需要重试的错误类型
function shouldRetry(error: any): boolean {
  // 网络错误
  if (!error.response) return true
  // 超时错误
  if (error.code === 'ECONNABORTED') return true
  // 5xx 服务器错误
  if (error.response.status >= 500 && error.response.status < 600) return true
  return false
}

// 延迟函数
function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

// 请求拦截：添加重试计数
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // 初始化重试计数（使用类型断言避免 TS 错误）
  const configAny = config as any
  if (!configAny._retryCount) {
    configAny._retryCount = 0
  }
  return config
})

// 响应拦截：处理网络错误、重试、401 认证
api.interceptors.response.use(
  (res) => {
    // 成功响应，确保在线状态
    if (!backendOnline.value) {
      backendOnline.value = true
    }
    return res
  },
  async (error) => {
    const originalRequest = error.config
    const status = error.response?.status

    // ---- 网络错误处理 ----
    if (!error.response) {
      // 更新后端状态为离线
      if (backendOnline.value) {
        backendOnline.value = false
        console.warn('[API] 后端连接断开，将自动重试...')
      }

      // 检查是否需要重试
      const originalAny = originalRequest as any
      if (originalAny._retryCount < MAX_RETRIES) {
        originalAny._retryCount++
        console.log(`[API] 第 ${originalAny._retryCount} 次重试: ${originalRequest.method?.toUpperCase()} ${originalRequest.url}`)
        
        // 指数退避延迟
        const delayTime = RETRY_DELAY * Math.pow(2, originalAny._retryCount - 1)
        await delay(delayTime)
        
        return api(originalRequest)
      }

      // 达到最大重试次数
      console.error(`[API] 请求失败（已重试 ${MAX_RETRIES} 次）: ${originalRequest.method?.toUpperCase()} ${originalRequest.url}`)
      return Promise.reject(error)
    }

    // ---- 401 认证错误处理 ----
    if (status === 401) {
      // 已经是 refresh 请求本身失败，或已经重试过，直接退出
      const originalAny = originalRequest as any
      if (originalAny._retry || originalRequest.url?.includes('/auth/refresh')) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/login'
        return Promise.reject(error)
      }

      // 竞态保护：如果正在刷新，排队等待
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          pendingRequests.push({
            resolve: (newToken: string) => {
              originalRequest.headers.Authorization = `Bearer ${newToken}`
              resolve(api(originalRequest))
            },
            reject,
          })
        })
      }

      originalAny._retry = true
      isRefreshing = true

      try {
        const refreshToken = localStorage.getItem('refresh_token')
        if (!refreshToken) {
          throw new Error('No refresh token')
        }

        // 使用独立的 axios 实例发送 refresh 请求，避免被拦截器递归捕获
        const { data } = await axios.post(
          `${import.meta.env.VITE_API_URL || ''}/api/auth/refresh`,
          { refresh_token: refreshToken },
          { timeout: 10000 },
        )

        // 更新 token
        localStorage.setItem('access_token', data.access_token)
        localStorage.setItem('refresh_token', data.refresh_token)
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`

        // 通知所有排队请求
        onRefreshed(data.access_token)

        // 重试原始请求
        return api(originalRequest)
      } catch (refreshError) {
        // refresh 也失败了，才真正清除并跳转
        onRefreshFailed(refreshError)
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    // 其他错误，直接抛出
    return Promise.reject(error)
  },
)

// ---- Token 主动续期（过期前5分钟自动刷新）----
let refreshTimer: ReturnType<typeof setTimeout> | null = null

export function startAutoRefresh() {
  stopAutoRefresh()
  const token = localStorage.getItem('access_token')
  if (!token) return

  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    const exp = payload.exp * 1000
    const now = Date.now()
    const refreshAt = exp - 5 * 60 * 1000 // 过期前5分钟刷新

    if (refreshAt > now) {
      refreshTimer = setTimeout(async () => {
        try {
          const refreshToken = localStorage.getItem('refresh_token')
          if (!refreshToken) return
          const { data } = await axios.post(
            `${import.meta.env.VITE_API_URL || ''}/api/auth/refresh`,
            { refresh_token: refreshToken },
            { timeout: 10000 },
          )
          localStorage.setItem('access_token', data.access_token)
          localStorage.setItem('refresh_token', data.refresh_token)
          // 递归设置下一次刷新
          startAutoRefresh()
        } catch {
          // 静默失败，等 401 拦截器兜底
        }
      }, refreshAt - now)
    }
  } catch {
    // token 格式错误则忽略
  }
}

export function stopAutoRefresh() {
  if (refreshTimer) {
    clearTimeout(refreshTimer)
    refreshTimer = null
  }
}

export default api
