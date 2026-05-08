import api from './client'

export const authApi = {
  login: (username: string, password: string) =>
    api.post('/api/auth/login', { username, password }),
  refresh: (refreshToken: string) =>
    api.post('/api/auth/refresh', { refresh_token: refreshToken }),
  getMe: () => api.get('/api/auth/me'),
  logout: () => api.post('/api/auth/logout').catch(() => {}),
  changePassword: (oldPassword: string, newPassword: string) =>
    api.post('/api/auth/change-password', { old_password: oldPassword, new_password: newPassword }),
  updateProfile: (data: { avatar?: string | null; nickname?: string | null }) =>
    api.patch('/api/auth/profile', data),
  getPermissions: () => api.get('/api/auth/permissions'),
}

export const userApi = {
  listUsers: () => api.get('/api/users'),
  createUser: (data: { username: string; password: string; role: string; tier?: string }) =>
    api.post('/api/users', data),
  updateUser: (id: number, data: { password?: string; role?: string; tier?: string; is_active?: boolean; avatar?: string }) =>
    api.put(`/api/users/${id}`, data),
  deleteUser: (id: number) => api.delete(`/api/users/${id}`),
  getUserPermissions: (userId: number) => api.get(`/api/users/${userId}/permissions`),
  updateUserPermissions: (userId: number, data: Record<string, boolean>) =>
    api.put(`/api/users/${userId}/permissions`, data),
  resetUserPermissions: (userId: number) =>
    api.post(`/api/users/${userId}/permissions/reset`),
}

export const systemApi = {
  getConfig: () => api.get('/api/system/config'),
  updateConfig: (data: { user_tier?: string; max_free_users?: number }) =>
    api.put('/api/system/config', data),
}
