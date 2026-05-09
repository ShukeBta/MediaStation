import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'

// 用户权限接口 — 与后端 UserPermissionOut 对齐
export interface UserPermissions {
  // 基础权限
  can_view_dashboard: boolean
  can_play_media: boolean
  can_cast: boolean
  can_external_player: boolean
  can_favorite: boolean
  can_view_history: boolean
  // 受限功能
  can_edit_media: boolean
  can_rescrape: boolean
  can_use_ai: boolean
  can_manage_chapters: boolean
  can_generate_ai_chapters: boolean
  can_capture_frames: boolean
  can_manage_downloads: boolean
  can_view_discover: boolean
  can_manage_subscriptions: boolean
  can_manage_sites: boolean
  can_use_ai_assistant: boolean
  can_manage_users: boolean
  can_manage_files: boolean
  can_manage_strm: boolean
  can_access_settings: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('access_token') || '')
  const user = ref<any>(null)
  const permissions = ref<UserPermissions | null>(null)
  const permissionsLoaded = ref(false)

  const isAuthenticated = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isPlus = computed(() => {
    // 直接使用 user.tier 字段判断 Plus 状态
    return user.value?.tier === 'plus'
  })

  async function login(username: string, password: string) {
    const { data } = await authApi.login(username, password)
    token.value = data.access_token
    user.value = data.user
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    // 登录成功后获取权限
    await fetchPermissions()
    return data
  }

  async function fetchMe() {
    if (!token.value) return
    try {
      const { data } = await authApi.getMe()
      user.value = data
    } catch {
      if (!localStorage.getItem('access_token')) {
        user.value = null
        token.value = ''
      }
    }
  }

  async function fetchPermissions() {
    if (!token.value) return
    try {
      const { data } = await authApi.getPermissions()
      permissions.value = data
      permissionsLoaded.value = true
    } catch {
      // 权限获取失败不阻塞流程
      console.warn('Failed to fetch user permissions')
      permissionsLoaded.value = true
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    permissions.value = null
    permissionsLoaded.value = false
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    window.location.href = '/login'
  }

  /**
   * 检查当前用户是否拥有指定权限。
   * PLUS 用户和管理员默认拥有所有权限。
   */
  function hasPermission(perm: keyof UserPermissions): boolean {
    if (isAdmin.value) return true
    if (isPlus.value) return true
    return permissions.value?.[perm] ?? false
  }

  /**
   * 检查是否有权访问管理员专属功能。
   */
  function isAdminOnly(): boolean {
    return isAdmin.value
  }

  return {
    token,
    user,
    permissions,
    permissionsLoaded,
    isAuthenticated,
    isAdmin,
    isPlus,
    login,
    fetchMe,
    fetchPermissions,
    logout,
    hasPermission,
    isAdminOnly,
  }
})
