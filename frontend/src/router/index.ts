import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// 扩展路由 meta 类型
declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    guest?: boolean
    adminOnly?: boolean
    requiredPermission?: string  // 对应 UserPermissions 中的字段名
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/LoginView.vue'),
      meta: { guest: true },
    },
    {
      path: '/',
      name: 'Dashboard',
      component: () => import('@/views/DashboardView.vue'),
      meta: { requiresAuth: true, requiredPermission: 'can_view_dashboard' },
    },
    {
      path: '/media',
      name: 'MediaLibrary',
      component: () => import('@/views/MediaLibraryView.vue'),
      meta: { requiresAuth: true, requiredPermission: 'can_play_media' },
    },
    {
      path: '/poster-wall',
      name: 'PosterWall',
      component: () => import('@/views/PosterWallView.vue'),
      meta: { requiresAuth: true, requiredPermission: 'can_play_media' },
    },
    {
      path: '/favorites',
      name: 'Favorites',
      component: () => import('@/views/FavoritesView.vue'),
      meta: { requiresAuth: true, requiredPermission: 'can_favorite' },
    },
    {
      path: '/tv/:id',
      name: 'TvSeason',
      component: () => import('@/views/TvSeasonView.vue'),
      meta: { requiresAuth: true, requiredPermission: 'can_play_media' },
    },
    {
      path: '/media/:id',
      name: 'MediaDetail',
      component: () => import('@/views/MediaDetailView.vue'),
      meta: { requiresAuth: true, requiredPermission: 'can_play_media' },
    },
    {
      path: '/player/:id',
      name: 'Player',
      component: () => import('@/views/PlayerView.vue'),
      meta: { requiresAuth: true, requiredPermission: 'can_play_media' },
    },
    {
      path: '/downloads',
      name: 'Downloads',
      component: () => import('@/views/DownloadView.vue'),
      meta: { requiresAuth: true, requiredPermission: 'can_manage_downloads' },
    },
    {
      path: '/discover',
      name: 'Discover',
      component: () => import('@/views/DiscoverView.vue'),
      meta: { requiresAuth: true, requiredPermission: 'can_view_discover' },
    },
    {
      path: '/search',
      name: 'SearchResult',
      component: () => import('@/views/SearchResultView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/subscriptions',
      name: 'Subscriptions',
      component: () => import('@/views/SubscribeView.vue'),
      meta: { requiresAuth: true, requiredPermission: 'can_manage_subscriptions' },
    },
    {
      path: '/sites',
      name: 'Sites',
      component: () => import('@/views/SitesView.vue'),
      meta: { requiresAuth: true, requiredPermission: 'can_manage_sites' },
    },
    {
      path: '/site-search',
      name: 'SiteSearch',
      component: () => import('@/views/SiteSearchView.vue'),
      meta: { requiresAuth: true, requiredPermission: 'can_manage_sites' },
    },
    {
      path: '/settings',
      name: 'Settings',
      component: () => import('@/views/SettingsView.vue'),
      meta: { requiresAuth: true, requiredPermission: 'can_access_settings' },
    },
    {
      path: '/history',
      name: 'WatchHistory',
      component: () => import('@/views/WatchHistoryView.vue'),
      meta: { requiresAuth: true, requiredPermission: 'can_view_history' },
    },
    {
      path: '/profile',
      name: 'Profile',
      component: () => import('@/views/ProfileView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/files',
      name: 'FileManager',
      component: () => import('@/views/FileManagerView.vue'),
      meta: { requiresAuth: true, adminOnly: true, requiredPermission: 'can_manage_files' },
    },
    {
      path: '/playlists',
      name: 'Playlists',
      component: () => import('@/views/PlaylistView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/playlists/:id',
      name: 'PlaylistDetail',
      component: () => import('@/views/PlaylistDetailView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/ai-assistant',
      name: 'AIAssistant',
      component: () => import('@/views/AIAssistantView.vue'),
      meta: { requiresAuth: true, adminOnly: true, requiredPermission: 'can_use_ai_assistant' },
    },
    {
      path: '/profiles-management',
      name: 'ProfileManagement',
      component: () => import('@/views/ProfileManagementView.vue'),
      meta: { requiresAuth: true, adminOnly: true },
    },
    {
      path: '/storage',
      name: 'Storage',
      component: () => import('@/views/StorageView.vue'),
      meta: { requiresAuth: true, adminOnly: true },
    },
    {
      path: '/strm',
      name: 'StrmManagement',
      component: () => import('@/views/StrmView.vue'),
      meta: { requiresAuth: true, requiredPermission: 'can_manage_strm' },
    },
    {
      path: '/dlna',
      name: 'DlnaCast',
      component: () => import('@/views/DlnaView.vue'),
      meta: { requiresAuth: true, requiredPermission: 'can_cast' },
    },
  ],
})

router.beforeEach(async (to, from, next) => {
  const auth = useAuthStore()

  // 初始化用户信息和权限
  if (auth.isAuthenticated && !auth.user) {
    await auth.fetchMe()
  }
  // 首次加载时获取权限和授权状态
  if (auth.isAuthenticated && !auth.permissionsLoaded) {
    await auth.fetchPermissions()
  }
  if (auth.isAuthenticated && !auth.licenseStatus) {
    await auth.fetchLicenseStatus()
  }

  // 未认证 → 登录页
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    next('/login')
    return
  }

  // 已认证 → 不访问登录页
  if (to.meta.guest && auth.isAuthenticated) {
    next('/')
    return
  }

  // 管理员权限检查
  if (to.meta.adminOnly && !auth.isAdmin) {
    next('/')
    return
  }

  // 功能权限检查（仅在权限已成功加载时才拦截）
  // 如果权限未加载成功（permissions 为 null），放行避免无限重定向
  if (to.meta.requiredPermission && auth.permissionsLoaded && auth.permissions) {
    if (!auth.hasPermission(to.meta.requiredPermission as any)) {
      // 无权限：跳转首页并提示
      next('/')
      return
    }
  }

  next()
})

export default router
