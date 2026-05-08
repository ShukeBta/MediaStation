import axios from 'axios'

// API 配置接口返回类型
interface ApiConfigResponse {
  provider: string
  enabled: boolean
  description: string | null
  has_key: boolean
  masked_key: string | null
  base_url: string | null
}

interface TestResult {
  success: boolean
  message: string
  details?: any
}

interface ProviderInfo {
  provider: string
  description: string
  base_url: string | null
}

export const apiConfigApi = {
  // 获取所有配置
  list: () => axios.get<ApiConfigResponse[]>('/api/api-config'),

  // 获取指定配置
  get: (provider: string) => axios.get<ApiConfigResponse>(`/api/api-config/${provider}`),

  // 获取生效配置
  getEffective: (provider: string) =>
    axios.get<any>(`/api/api-config/${provider}/effective`),

  // 更新配置
  update: (provider: string, data: { api_key?: string; base_url?: string; enabled?: boolean; extra?: any }) =>
    axios.post<ApiConfigResponse>(`/api/api-config/${provider}`, data),

  // 删除配置
  delete: (provider: string) =>
    axios.delete(`/api/api-config/${provider}`),

  // 测试连接
  test: (provider: string) =>
    axios.post<TestResult>(`/api/api-config/${provider}/test`),

  // 获取支持的 Provider 列表
  listProviders: () =>
    axios.get<ProviderInfo[]>('/api/api-config/providers/list'),
}
