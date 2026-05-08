import api from './client'

export interface LicenseKeyCreate {
  license_type?: string
  max_devices?: number
  expiry_days?: number | null
  note?: string | null
}

export interface LicenseKeyOut {
  id: number
  key_display: string
  license_type: string
  max_devices: number
  expiry_date: string | null
  is_revoked: boolean
  note: string | null
  created_at: string
  active_device_count: number
}

export interface LicenseActivationOut {
  id: number
  device_name: string | null
  device_fingerprint_short: string
  first_activated_at: string
  last_seen_at: string
  is_active: boolean
  unbound_at: string | null
}

export interface LicenseStatusOut {
  is_plus: boolean
  license_type: string | null
  expiry_date: string | null
  device_name: string | null
  max_devices: number | null
  days_remaining: number | null
  license_key_id: number | null
  verification_mode?: string
  in_grace_period?: boolean
  grace_days_remaining?: number | null
}

export interface LicenseConfigUpdate {
  verification_mode?: string
  server_url?: string | null
  server_secret?: string | null
  heartbeat_interval_days?: number | null
  grace_period_days?: number | null
}

export interface LicenseConfigOut {
  verification_mode: string
  server_url: string | null
  server_secret_set: boolean
  heartbeat_interval_days: number
  grace_period_days: number
  instance_id: string | null
}

export interface LicenseHeartbeatStatus {
  verification_mode: string
  last_verified_at: string | null
  last_heartbeat_at: string | null
  next_heartbeat_at: string | null
  grace_period_ends: string | null
  days_in_grace: number | null
}

export const licenseApi = {
  // 管理员接口
  generate: (data: LicenseKeyCreate) =>
    api.post('/api/license/generate', data),
  list: () =>
    api.get('/api/license/list'),
  getActivations: (keyId: number) =>
    api.get(`/api/license/${keyId}/activations`),
  revoke: (keyId: number) =>
    api.post(`/api/license/${keyId}/revoke`),
  unbindDevice: (activationId: number) =>
    api.post(`/api/license/activation/${activationId}/unbind`),

  // 配置管理（管理员）
  getConfig: () =>
    api.get<LicenseConfigOut>('/api/license/config'),
  updateConfig: (data: LicenseConfigUpdate) =>
    api.post<LicenseConfigOut>('/api/license/config', data),
  testConnection: (url: string) =>
    api.post<{ success: boolean; message: string }>('/api/license/config/test', null, { params: { url } }),

  // 在线验证
  refreshLicense: () =>
    api.post<LicenseStatusOut>('/api/license/refresh'),
  getHeartbeatStatus: () =>
    api.get<LicenseHeartbeatStatus>('/api/license/heartbeat-status'),

  // 所有认证用户
  activate: (key: string) =>
    api.post('/api/license/activate', { key }),
  getStatus: () =>
    api.get<LicenseStatusOut>('/api/license/status'),
  unbindCurrent: () =>
    api.post('/api/license/unbind'),
}
