<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6 animate-in">
    <!-- 页头 -->
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-[var(--text-primary)]">站点管理</h1>
      <button @click="openCreateModal" class="btn-primary flex items-center gap-2 text-sm">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
        </svg>
        添加站点
      </button>
    </div>

    <!-- 资源搜索 -->
    <div class="card p-4">
      <div class="flex gap-2">
        <div class="relative flex-1">
          <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-faint)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
          <input v-model="searchKeyword" @keyup.enter="searchResources"
            placeholder="搜索资源（片名、关键词）"
            class="input !pl-9" />
        </div>
        <button @click="searchResources" :disabled="searching" class="btn-primary shrink-0 min-w-[80px]">
          <span v-if="searching" class="flex items-center gap-1">
            <svg class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            搜索中
          </span>
          <span v-else>搜 索</span>
        </button>
      </div>

      <!-- 搜索结果 -->
      <Transition name="expand">
        <div v-if="searchResults.length > 0" class="mt-4 space-y-2">
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm text-[var(--text-muted)]">找到 <b class="text-[var(--text-primary)]">{{ searchResults.length }}</b> 个资源</span>
            <button @click="searchResults = []" class="text-xs text-[var(--text-faint)] hover:text-[var(--text-muted)] transition-colors">清除结果</button>
          </div>
          <div v-for="res in searchResults" :key="res.title + res.site_name"
            class="flex items-center gap-3 p-3 rounded-lg border border-transparent hover:border-[var(--border-primary)] transition-all"
            style="background: var(--bg-hover)">
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium truncate text-[var(--text-primary)]">{{ res.title }}</div>
              <div class="flex items-center gap-2 mt-1 flex-wrap">
                <span class="text-xs px-1.5 py-0.5 rounded" style="background: var(--border-primary); color: var(--text-muted)">{{ res.site_name }}</span>
                <span v-if="res.size" class="text-xs text-[var(--text-faint)]">{{ formatFileSize(res.size) }}</span>
                <span v-if="res.seeders" class="text-xs text-green-500">↑{{ res.seeders }}</span>
                <span v-if="res.leechers" class="text-xs text-red-400">↓{{ res.leechers }}</span>
                <span v-if="res.free" class="text-xs px-1.5 py-0.5 rounded bg-green-500/15 text-green-400">FREE</span>
              </div>
            </div>
            <button @click="downloadResource(res)" class="btn-primary text-xs shrink-0">下载</button>
          </div>
        </div>
      </Transition>
    </div>

    <!-- 站点卡片列表 -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="site in sites" :key="site.id"
        class="card p-4 transition-all hover:shadow-md">
        <!-- 头部：名称 + 状态 -->
        <div class="flex items-start justify-between mb-3">
          <div class="flex items-center gap-2 min-w-0">
            <!-- 站点类型图标 -->
            <div :class="['w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold shrink-0', siteTypeStyle(site.site_type).bg]">
              <span :class="siteTypeStyle(site.site_type).text">{{ siteTypeStyle(site.site_type).label }}</span>
            </div>
            <div class="min-w-0">
              <div class="font-medium text-[var(--text-primary)] truncate">{{ site.name }}</div>
              <div class="text-xs text-[var(--text-muted)] truncate max-w-[180px]">{{ site.base_url }}</div>
            </div>
          </div>
          <!-- 状态指示 -->
          <div class="flex items-center gap-1 shrink-0 ml-2">
            <span :class="[
              'w-2 h-2 rounded-full',
              site.login_status === 'ok' ? 'bg-[var(--success)]' :
              site.login_status === 'failed' ? 'bg-[var(--error)]' : 'bg-[var(--text-faint)]',
            ]" :title="site.login_status === 'ok' ? '正常' : site.login_status === 'failed' ? '失败' : '未测试'" />
            <span v-if="!site.enabled" class="text-xs text-[var(--text-faint)]">已停用</span>
          </div>
        </div>

        <!-- 标签行 -->
        <div class="flex flex-wrap gap-1.5 mb-3">
          <span class="site-tag">{{ siteTypeLabel(site.site_type) }}</span>
          <span class="site-tag">{{ authTypeLabel(site.auth_type) }}</span>
          <span v-if="site.use_proxy" class="site-tag text-amber-400">代理</span>
          <span v-if="site.rate_limit" class="site-tag text-blue-400">限速</span>
          <span v-if="site.rss_url" class="site-tag text-green-400">RSS</span>
        </div>

        <!-- 流量统计 -->
        <div v-if="site.upload_bytes || site.download_bytes" class="flex gap-3 mb-3 text-xs text-[var(--text-muted)]">
          <span v-if="site.upload_bytes" class="flex items-center gap-1">
            <svg class="w-3 h-3 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 10l7-7m0 0l7 7m-7-7v18"/>
            </svg>
            {{ formatFileSize(site.upload_bytes) }}
          </span>
          <span v-if="site.download_bytes" class="flex items-center gap-1">
            <svg class="w-3 h-3 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3"/>
            </svg>
            {{ formatFileSize(site.download_bytes) }}
          </span>
        </div>

        <!-- 操作按钮 -->
        <div class="flex items-center gap-2">
          <button @click="testSite(site.id)" :disabled="testingSite === site.id"
            class="flex-1 btn-secondary text-xs disabled:opacity-50 flex items-center justify-center gap-1">
            <svg v-if="testingSite === site.id" class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            {{ testingSite === site.id ? '测试中...' : '测试连接' }}
          </button>
          <button @click="refreshUserdata(site.id)"
            :disabled="refreshingUserdata === site.id"
            class="icon-btn" title="刷新用户数据（上传/下载量）">
            <svg v-if="refreshingUserdata === site.id" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            <svg v-else class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
            </svg>
          </button>
          <button @click="openEditModal(site)"
            class="icon-btn" title="编辑">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
            </svg>
          </button>
          <button @click="handleDelete(site)"
            class="icon-btn hover:!text-[var(--error)]" title="删除">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
            </svg>
          </button>
        </div>
      </div>

      <div v-if="sites.length === 0 && !loading" class="col-span-full">
        <AppEmpty message="暂无站点，点击「添加站点」添加 PT/BT 站点以启用资源搜索和订阅" />
      </div>
    </div>

    <!-- ── 创建/编辑站点弹窗 ── -->
    <AppModal :show="showModal" :title="editingSite ? `编辑站点 · ${editingSite.name}` : '添加站点'" max-width="600px" max-height="70vh" @close="closeModal">
      <div class="space-y-5">
        <!-- 基本信息 -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div class="sm:col-span-2">
            <label class="form-label">站点名称 *</label>
            <input v-model="form.name" placeholder="例如: 馒头、观众、家园" class="input" />
          </div>
          <div class="sm:col-span-2">
            <label class="form-label">站点地址 *</label>
            <div class="relative">
              <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-faint)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064"/>
              </svg>
              <input v-model="form.base_url" placeholder="https://www.example.com/" class="input !pl-9" />
            </div>
            <p class="text-xs text-[var(--text-faint)] mt-1">格式: https://www.example.com/</p>
          </div>

          <!-- 站点类型 -->
          <div>
            <label class="form-label">站点类型</label>
            <select v-model="form.site_type" class="input">
              <option value="nexusphp">NexusPHP（国内主流PT）</option>
              <option value="gazelle">Gazelle/Luminance（HDBits等）</option>
              <option value="unit3d">UNIT3D（BeyondHD/BluTopia等）</option>
              <option value="mteam">馒头 M-Team（专用API）</option>
              <option value="discuz">Discuz 论坛型</option>
              <option value="custom_rss">自定义 RSS</option>
            </select>
          </div>

          <!-- 馒头专用提示 -->
          <div v-if="form.site_type === 'mteam'" class="sm:col-span-2 p-3 rounded-lg border border-green-500/30 bg-green-500/5">
            <div class="text-sm font-medium text-green-400 mb-2">🍞 馒头站点配置指南</div>
            <div class="text-xs text-[var(--text-muted)] space-y-1">
              <div><b>站点地址：</b><code class="text-green-300">https://api2.m-team.cc</code>（注意不是首页地址）</div>
              <div><b>认证方式：</b>推荐使用「API Key / Passkey」，令牌获取方式如下</div>
              <div class="pl-3">
                1. 登录馒头站 → <b>控制台 → 实验室 → 存取令牌</b><br>
                2. 点击「创建令牌」，复制生成的 Token<br>
                3. 将 Token 填入下方「令牌」输入框
              </div>
              <div class="text-amber-400 mt-1">⚠️ 请确保令牌具有下载权限，否则搜索成功但无法下载</div>
            </div>
          </div>

          <!-- 状态 + 优先级 -->
          <div>
            <label class="form-label">状态</label>
            <div class="flex items-center gap-3 h-10">
              <button type="button" @click="form.enabled = !form.enabled"
                :class="['relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors duration-200 ease-in-out cursor-pointer',
                  form.enabled ? 'bg-brand-500' : 'bg-[var(--border-primary)]']">
                <span :class="['pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform duration-200 ease-in-out mt-0.5',
                  form.enabled ? 'translate-x-4' : 'translate-x-0.5']" />
              </button>
              <span class="text-sm" :class="form.enabled ? 'text-[var(--text-primary)]' : 'text-[var(--text-faint)]'">
                {{ form.enabled ? '启用' : '停用' }}
              </span>
            </div>
            <p class="text-xs text-[var(--text-faint)] mt-0.5">站点启用/停用</p>
          </div>
        </div>

        <!-- RSS 地址 -->
        <div>
          <label class="form-label">
            <svg class="w-3.5 h-3.5 inline mr-1 text-[var(--text-faint)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 5c7.18 0 13 5.82 13 13M6 11a7 7 0 017 7M6 17a1 1 0 11-2 0 1 1 0 012 0z"/>
            </svg>
            RSS 地址
          </label>
          <input v-model="form.rss_url" placeholder="https://rss.example.com/rss?passkey=xxx" class="input" />
          <p class="text-xs text-[var(--text-faint)] mt-1">订阅模式为「站点RSS」时使用的订阅链接，如未自动获取需手动补充</p>
        </div>

        <!-- 认证方式 -->
        <div>
          <label class="form-label">认证方式</label>
          <div class="flex gap-2 mb-3">
            <button v-for="opt in authTypeOptions" :key="opt.value" type="button"
              @click="form.auth_type = opt.value"
              :class="['px-3 py-1.5 rounded-lg text-xs font-medium transition-all border',
                form.auth_type === opt.value
                  ? 'bg-brand-500 text-white border-brand-500'
                  : 'border-[var(--border-primary)] text-[var(--text-muted)] hover:border-brand-500/50']">
              {{ opt.label }}
            </button>
          </div>

          <!-- COOKIE -->
          <div v-if="form.auth_type === 'cookie'">
            <label class="form-label text-xs">Cookie</label>
            <textarea v-model="form.cookie" rows="3"
              placeholder="uid=xxx; pass=xxx; ..."
              class="input resize-none text-xs font-mono" />
            <p class="text-xs text-[var(--text-faint)] mt-1">登录站点后从浏览器开发者工具的「网络」选项卡中找到请求头中的 Cookie 值</p>
          </div>

          <!-- API KEY -->
          <div v-if="form.auth_type === 'api_key'">
            <label class="form-label text-xs">
              <svg class="w-3.5 h-3.5 inline mr-1 text-[var(--text-faint)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"/>
              </svg>
              令牌（API Key / Passkey）
            </label>
            <input v-model="form.api_key" type="password"
              placeholder="输入 API Key 或 Passkey"
              class="input font-mono text-sm" />
            <p class="text-xs text-[var(--text-faint)] mt-1">
              <template v-if="form.site_type === 'mteam'">馒头：控制台 → 实验室 → 存取令牌</template>
              <template v-else-if="form.site_type === 'unit3d'">UNIT3D：设置 → API Token</template>
              <template v-else>站点的访问 API Key，特殊站点需要</template>
            </p>
          </div>

          <!-- AUTHORIZATION HEADER -->
          <div v-if="form.auth_type === 'authorization'">
            <label class="form-label text-xs">
              <svg class="w-3.5 h-3.5 inline mr-1 text-[var(--text-faint)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/>
              </svg>
              请求头（Authorization）
            </label>
            <input v-model="form.auth_header"
              placeholder="Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
              class="input font-mono text-xs" />
            <p class="text-xs text-[var(--text-faint)] mt-1">站点请求头中的 Authorization 信息，特殊站点需要（如馒头旧版）</p>
          </div>
        </div>

        <!-- 高级设置行 -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="form-label">
              <svg class="w-3.5 h-3.5 inline mr-1 text-[var(--text-faint)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
              超时时间（秒）
            </label>
            <input v-model.number="form.timeout" type="number" min="0" max="300" class="input" />
            <p class="text-xs text-[var(--text-faint)] mt-1">站点请求超时时间，为 0 时不限制</p>
          </div>
          <div>
            <label class="form-label">
              优先级
            </label>
            <input v-model.number="form.priority" type="number" min="1" max="100" class="input" />
            <p class="text-xs text-[var(--text-faint)] mt-1">优先级越小越优先</p>
          </div>
        </div>

        <!-- 下载器 + UA -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="form-label">
              <svg class="w-3.5 h-3.5 inline mr-1 text-[var(--text-faint)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
              </svg>
              下载器
            </label>
            <select v-model="form.downloader" class="input">
              <option value="">默认下载器</option>
              <option value="qbittorrent">qBittorrent</option>
              <option value="transmission">Transmission</option>
              <option value="aria2">Aria2</option>
            </select>
            <p class="text-xs text-[var(--text-faint)] mt-1">此站点使用的下载器</p>
          </div>
          <div>
            <label class="form-label">User-Agent（可选）</label>
            <input v-model="form.user_agent"
              placeholder="留空使用默认 UA"
              class="input text-xs font-mono" />
          </div>
        </div>

        <!-- 开关选项 -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <ToggleField v-model="form.rate_limit" label="限制站点访问频率" desc="防止触发频率限制" />
          <ToggleField v-model="form.use_proxy" label="使用代理访问" desc="使用代理服务器访问该站点" />
          <ToggleField v-model="form.browser_emulation" label="浏览器仿真" desc="使用浏览器模拟真实访问站点" />
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-2 pt-2">
          <button @click="closeModal" class="btn-secondary text-sm">取消</button>
          <button @click="saveSite"
            :disabled="saving || !form.name.trim() || !form.base_url.trim()"
            class="btn-primary text-sm disabled:opacity-50 flex items-center gap-1.5">
            <svg v-if="saving" class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            <svg v-else class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"/>
            </svg>
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </template>
    </AppModal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, defineComponent, h, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { subscribeApi } from '@/api/subscribe'
import { downloadApi } from '@/api/download'
import { useFormat } from '@/composables/useFormat'
import { useToast } from '@/composables/useToast'
import AppModal from '@/components/AppModal.vue'
import AppEmpty from '@/components/AppEmpty.vue'

const route = useRoute()
const router = useRouter()
const { formatFileSize, formatDate } = useFormat()
const toast = useToast()

// ── ToggleField 子组件 ──
const ToggleField = defineComponent({
  props: {
    modelValue: Boolean,
    label: String,
    desc: String,
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () => h('div', { class: 'flex items-start gap-3 p-3 rounded-lg border border-[var(--border-primary)] hover:border-brand-500/30 transition-colors' }, [
      h('button', {
        type: 'button',
        class: [
          'relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors duration-200 ease-in-out cursor-pointer mt-0.5',
          props.modelValue ? 'bg-brand-500' : 'bg-[var(--border-primary)]',
        ].join(' '),
        onClick: () => emit('update:modelValue', !props.modelValue),
      }, [
        h('span', {
          class: [
            'pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform duration-200 ease-in-out mt-0.5',
            props.modelValue ? 'translate-x-4' : 'translate-x-0.5',
          ].join(' '),
        })
      ]),
      h('div', { class: 'min-w-0' }, [
        h('div', { class: 'text-sm font-medium text-[var(--text-primary)]' }, props.label),
        h('div', { class: 'text-xs text-[var(--text-faint)] mt-0.5' }, props.desc),
      ])
    ])
  }
})

// ── 数据 ──
const sites = ref<any[]>([])
const loading = ref(false)
const showModal = ref(false)
const editingSite = ref<any>(null)
const saving = ref(false)
const testingSite = ref<number | null>(null)
const refreshingUserdata = ref<number | null>(null)

const defaultForm = () => ({
  name: '',
  base_url: '',
  site_type: 'nexusphp',
  auth_type: 'cookie',
  cookie: '',
  api_key: '',
  auth_header: '',
  user_agent: '',
  rss_url: '',
  timeout: 15,
  priority: 50,
  use_proxy: false,
  rate_limit: false,
  browser_emulation: false,
  enabled: true,
  downloader: '',
})
const form = ref(defaultForm())

// ── 搜索 ──
const searchKeyword = ref('')
const searching = ref(false)
const searchResults = ref<any[]>([])

// ── 认证方式选项 ──
const authTypeOptions = [
  { value: 'cookie', label: 'Cookie' },
  { value: 'api_key', label: 'API Key / Passkey' },
  { value: 'authorization', label: 'Authorization 请求头' },
]

// 选择馒头时自动切换到 API Key 认证方式
watch(() => form.value.site_type, (newType) => {
  if (newType === 'mteam') {
    form.value.auth_type = 'api_key'
  }
})

// ── 站点类型样式 ──
function siteTypeStyle(type: string) {
  const map: Record<string, { bg: string; text: string; label: string }> = {
    nexusphp: { bg: 'bg-blue-500/15', text: 'text-blue-400', label: 'NP' },
    gazelle:  { bg: 'bg-purple-500/15', text: 'text-purple-400', label: 'GZ' },
    unit3d:   { bg: 'bg-orange-500/15', text: 'text-orange-400', label: 'U3' },
    mteam:    { bg: 'bg-green-500/15', text: 'text-green-400', label: 'MT' },
    discuz:   { bg: 'bg-yellow-500/15', text: 'text-yellow-400', label: 'DZ' },
    custom_rss: { bg: 'bg-gray-500/15', text: 'text-gray-400', label: 'RSS' },
  }
  return map[type] || map['nexusphp']
}

function siteTypeLabel(type: string) {
  const map: Record<string, string> = {
    nexusphp: 'NexusPHP', gazelle: 'Gazelle', unit3d: 'UNIT3D',
    mteam: 'M-Team', discuz: 'Discuz', custom_rss: '自定义RSS',
    nexus_php: 'NexusPHP',
  }
  return map[type] || type
}

function authTypeLabel(type: string) {
  const map: Record<string, string> = {
    cookie: 'Cookie', api_key: 'API Key', authorization: 'Auth Header',
  }
  return map[type] || type || 'Cookie'
}

// ── 弹窗操作 ──
function openCreateModal() {
  editingSite.value = null
  form.value = defaultForm()
  showModal.value = true
}

function openEditModal(site: any) {
  editingSite.value = site
  form.value = {
    name: site.name || '',
    base_url: site.base_url || '',
    site_type: site.site_type || 'nexusphp',
    auth_type: site.auth_type || 'cookie',
    cookie: site.cookie || '',
    api_key: site.api_key || '',
    auth_header: site.auth_header || '',
    user_agent: site.user_agent || '',
    rss_url: site.rss_url || '',
    timeout: site.timeout ?? 15,
    priority: site.priority ?? 50,
    use_proxy: site.use_proxy || false,
    rate_limit: site.rate_limit || false,
    browser_emulation: site.browser_emulation || false,
    enabled: site.enabled !== false,
    downloader: site.downloader || '',
  }
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  editingSite.value = null
}

async function saveSite() {
  if (!form.value.name.trim() || !form.value.base_url.trim()) return
  saving.value = true
  try {
    const payload = { ...form.value }
    // 空字符串转 null
    if (!payload.cookie) payload.cookie = null as any
    if (!payload.api_key) payload.api_key = null as any
    if (!payload.auth_header) payload.auth_header = null as any
    if (!payload.user_agent) payload.user_agent = null as any
    if (!payload.rss_url) payload.rss_url = null as any
    if (!payload.downloader) payload.downloader = null as any

    if (editingSite.value) {
      await subscribeApi.updateSite(editingSite.value.id, payload)
      toast.success('站点已更新')
    } else {
      await subscribeApi.createSite(payload)
      toast.success('站点已添加')
    }
    closeModal()
    await loadSites()
  } catch (e: any) {
    toast.error(`保存失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    saving.value = false
  }
}

async function loadSites() {
  loading.value = true
  try {
    const { data } = await subscribeApi.getSites()
    sites.value = Array.isArray(data) ? data : (data.items || [])
  } catch {
    toast.error('加载站点失败')
  } finally {
    loading.value = false
  }
}

async function refreshUserdata(id: number) {
  refreshingUserdata.value = id
  try {
    const { data } = await subscribeApi.refreshSiteUserdata(id)
    if (data.success) {
      toast.success(`用户数据已刷新：${data.site_name}`)
    } else {
      toast.warning(data.message || '该站点暂不支持用户数据获取')
    }
    await loadSites()
  } catch (e: any) {
    toast.error(`刷新失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    refreshingUserdata.value = null
  }
}

async function testSite(id: number) {
  testingSite.value = id
  try {
    const { data } = await subscribeApi.testSite(id)
    if (data.connected) {
      toast.success(`连接测试成功：${data.message || ''}`)
    } else {
      toast.error(`连接测试失败：${data.message || ''}`)
    }
    await loadSites()
  } catch (e: any) {
    toast.error(`连接测试失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    testingSite.value = null
  }
}

async function handleDelete(site: any) {
  const confirmed = await toast.confirm({
    title: '确认删除',
    message: `确定要删除站点「${site.name}」吗？此操作不可撤销。`,
    confirmText: '删除',
    danger: true,
  })
  if (!confirmed) return
  try {
    await subscribeApi.deleteSite(site.id)
    toast.success('站点已删除')
    await loadSites()
  } catch {
    toast.error('删除站点失败')
  }
}

async function searchResources() {
  if (!searchKeyword.value.trim()) return
  searching.value = true
  searchResults.value = []
  try {
    const { data } = await subscribeApi.searchSites(searchKeyword.value.trim())
    searchResults.value = Array.isArray(data) ? data : (data.results || data.items || [])
  } catch {
    toast.error('搜索资源失败，请检查站点配置')
  } finally {
    searching.value = false
  }
}

async function downloadResource(res: any) {
  try {
    // 传递站点信息，让后端能解析 genDlToken 等需要认证的下载链接
    await downloadApi.addTask({
      torrent_url: res.download_url || res.torrent_url,
      site_id: res.site_id,
      title: res.title,
    })
    toast.success('已添加到下载列表')
  } catch {
    toast.error('添加下载失败，请检查下载客户端配置')
  }
}

// ── URL 查询参数处理 ──
onMounted(async () => {
  // 加载站点列表
  await loadSites()

  // 检查 URL 查询参数
  const searchParam = route.query.search as string
  if (searchParam) {
    // 有 search 参数，自动搜索
    searchKeyword.value = searchParam
    await searchResources()
    // 清除 URL 参数，避免刷新时重复搜索
    router.replace({ path: '/subscribe' })
  }
})
</script>

<style scoped>
.site-tag {
  @apply text-xs px-1.5 py-0.5 rounded text-[var(--text-muted)];
  background: var(--bg-input);
}
.icon-btn {
  @apply p-1.5 rounded-lg transition-colors text-[var(--text-muted)] hover:text-[var(--text-secondary)];
  background: transparent;
}
.icon-btn:hover {
  background: var(--bg-hover);
}
.form-label {
  @apply block text-sm text-[var(--text-muted)] mb-1.5 font-medium;
}
</style>
