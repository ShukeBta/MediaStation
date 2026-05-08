<template>
  <div class="p-4 md:p-6 max-w-5xl mx-auto space-y-6">
    <h1 class="text-2xl font-bold">设置</h1>

    <!-- 选项卡 -->
    <div class="flex gap-1 border-b border-[var(--border-primary)] overflow-x-auto scrollbar-none">
      <button v-for="tab in tabs" :key="tab.key" @click="activeTab = tab.key"
        :class="[
          'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap shrink-0',
          activeTab === tab.key
            ? 'border-brand-500 text-brand-400'
            : 'border-transparent hover:text-[var(--text-secondary)]',
        ]"
        :style="activeTab !== tab.key ? 'color: var(--text-muted)' : ''">
        {{ tab.label }}
      </button>
    </div>

    <Transition name="page" mode="out-in">
      <component :is="tabComponents[activeTab]" :key="activeTab" @switch-tab="activeTab = $event" />
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, shallowRef, markRaw, computed, onMounted } from 'vue'
import LibrariesTab from '@/components/settings/LibrariesTab.vue'
import DownloadTab from '@/components/settings/DownloadTab.vue'
import NotifyTab from '@/components/settings/NotifyTab.vue'
import SchedulerTab from '@/components/settings/SchedulerTab.vue'
import SystemTab from '@/components/settings/SystemTab.vue'
import GeneralTab from '@/components/settings/GeneralTab.vue'
import AccountTab from '@/components/settings/AccountTab.vue'
import UsersTab from '@/components/settings/UsersTab.vue'
import ApiConfigTab from '@/components/settings/ApiConfigTab.vue'
import AdultTab from '@/components/settings/AdultTab.vue'
import OrganizeScrapeTab from '@/components/settings/OrganizeScrapeTab.vue'
import { authApi } from '@/api/auth'
import LicenseTab from '@/components/settings/LicenseTab.vue'

const activeTab = ref('account')
const isAdmin = ref(false)

const allTabs = [
  { key: 'account', label: '我的账号', adminOnly: false },
  { key: 'libraries', label: '媒体库', adminOnly: false },
  { key: 'download', label: '下载客户端', adminOnly: false },
  { key: 'notify', label: '通知渠道', adminOnly: false },
  { key: 'organize', label: '整理&刮削', adminOnly: true },
  { key: 'scheduler', label: '定时任务', adminOnly: true },
  { key: 'apiconfig', label: 'API 配置', adminOnly: true },
  { key: 'adult', label: 'Adult', adminOnly: true },
  { key: 'general', label: '全局配置', adminOnly: true },
  { key: 'users', label: '用户管理', adminOnly: true },
  { key: 'license', label: '授权管理', adminOnly: false },
  { key: 'system', label: '系统信息', adminOnly: true },
]

const tabs = computed(() => allTabs.filter(t => !t.adminOnly || isAdmin.value))

const tabComponents: Record<string, ReturnType<typeof markRaw>> = {
  account: markRaw(AccountTab),
  libraries: markRaw(LibrariesTab),
  download: markRaw(DownloadTab),
  notify: markRaw(NotifyTab),
  organize: markRaw(OrganizeScrapeTab),
  scheduler: markRaw(SchedulerTab),
  apiconfig: markRaw(ApiConfigTab),
  adult: markRaw(AdultTab),
  general: markRaw(GeneralTab),
  users: markRaw(UsersTab),
  license: markRaw(LicenseTab),
  system: markRaw(SystemTab),
}

onMounted(async () => {
  try {
    const { data } = await authApi.getMe()
    isAdmin.value = data.role === 'admin'
  } catch {}
})
</script>

<style scoped>
/* 隐藏 tab 滚动条 */
.scrollbar-none::-webkit-scrollbar { display: none; }
.scrollbar-none { -ms-overflow-style: none; scrollbar-width: none; }
</style>
