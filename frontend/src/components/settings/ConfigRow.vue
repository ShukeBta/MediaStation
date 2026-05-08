<template>
  <div class="flex items-center px-4 py-3 hover:bg-[var(--bg-tertiary)] transition-colors group rounded-lg">
    <!-- 左侧：图标 + 名称和状态 -->
    <div class="flex-1 min-w-0 flex items-center gap-3">
      <!-- 数据源图标 -->
      <div class="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold"
           :class="config.has_key ? 'bg-success/10 text-success' : 'bg-warning/10 text-warning'">
        {{ getProviderInitial(config.provider) }}
      </div>
      
      <div class="min-w-0">
        <div class="flex items-center gap-2">
          <span class="font-medium text-sm">{{ getProviderName(config.provider) }}</span>
          <!-- 状态标识：已配置 -->
          <span
            v-if="config.has_key"
            class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-success/10 text-success"
          >
            <Icon icon="ph:check-circle-fill" class="text-sm" />
            已配置
          </span>
          <!-- 状态标识：未配置 -->
          <span v-else class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-warning/10 text-warning">
            <Icon icon="ph:warning-circle-fill" class="text-sm" />
            未配置
          </span>
        </div>
        <p class="text-xs mt-0.5 truncate" style="color: var(--text-muted)">
          {{ config.description || getDefaultDescription(config.provider) }}
        </p>
      </div>
    </div>

      <!-- 中间：API Key/地址显示 -->
    <div class="flex-1 mx-4 hidden md:block">
      <!-- 编辑模式 -->
      <template v-if="editing">
        <div class="flex gap-2">
          <input
            v-model="editForm.api_key"
            type="password"
            class="input input-sm flex-1 font-mono"
            placeholder="输入 API Key"
            @keyup.enter="$emit('save')"
            @keyup.escape="$emit('cancel')"
          />
          <input
            v-model="editForm.base_url"
            type="text"
            class="input input-sm flex-1"
            placeholder="API 地址（可选）"
          />
        </div>
      </template>
      <!-- 显示模式 -->
      <template v-else>
        <div v-if="config.has_key" class="flex items-center gap-2">
          <!-- API Key 遮罩显示优化 -->
          <div class="flex items-center gap-1.5 px-2.5 py-1.5 bg-success/5 border border-success/20 rounded-lg">
            <Icon icon="ph:key-fill" class="text-success/60 text-xs" />
            <span class="font-mono text-xs tracking-wider text-success/80">
              {{ formatMaskedKey(config.masked_key) }}
            </span>
          </div>
          <!-- Base URL -->
          <div v-if="config.base_url" class="flex items-center gap-1 px-2 py-1 bg-info/5 border border-info/20 rounded-lg">
            <Icon icon="ph:link" class="text-info/60 text-xs" />
            <span class="text-xs text-info/80 truncate max-w-[200px]">
              {{ config.base_url }}
            </span>
          </div>
        </div>
        <div v-else class="flex items-center gap-1.5 text-xs" style="color: var(--text-muted)">
          <Icon icon="ph:warning-circle" class="text-warning/60" />
          <span>未设置 API Key</span>
        </div>
      </template>
    </div>

    <!-- 右侧：操作按钮 -->
    <div class="flex items-center gap-1">
      <!-- 编辑模式按钮 -->
      <template v-if="editing">
        <button @click="$emit('save')" class="btn btn-xs btn-primary gap-1">
          <Icon icon="ph:check" class="text-sm" />
          保存
        </button>
        <button @click="$emit('cancel')" class="btn btn-xs btn-ghost gap-1">
          <Icon icon="ph:x" class="text-sm" />
          取消
        </button>
      </template>
      
      <!-- 显示模式按钮 -->
      <template v-else>
        <!-- 测试连接按钮（带loading状态） -->
        <button
          @click="$emit('test')"
          class="btn btn-xs btn-ghost gap-1"
          :class="{ 'loading loading-spinner loading-xs': testing }"
          :disabled="!config.has_key || testing"
          :title="config.has_key ? '测试连接' : '请先配置 API Key'"
        >
          <Icon v-if="!testing" icon="ph:plug" />
          <span v-if="!testing">测试</span>
        </button>
        
        <!-- 编辑按钮 -->
        <button
          @click="$emit('edit')"
          class="btn btn-xs btn-ghost gap-1"
          title="编辑配置"
        >
          <Icon icon="ph:pencil-simple" class="text-sm" />
          <span class="hidden lg:inline">编辑</span>
        </button>
        
        <!-- 清除按钮（带确认） -->
        <button
          v-if="config.has_key"
          @click="$emit('clear')"
          class="btn btn-xs btn-ghost text-error gap-1"
          title="清除配置"
        >
          <Icon icon="ph:trash" class="text-sm" />
          <span class="hidden lg:inline">清除</span>
        </button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, defineModel } from 'vue'
import { Icon } from '@iconify/vue'

interface ApiConfig {
  provider: string
  enabled: boolean
  description: string | null
  has_key: boolean
  masked_key: string | null
  base_url: string | null
}

interface EditForm {
  api_key: string
  base_url: string
}

const props = defineProps<{
  config: ApiConfig
  editing: boolean
  testing?: boolean
}>()

const editForm = defineModel<EditForm>('editForm', { required: true })

defineEmits<{
  (e: 'edit'): void
  (e: 'save'): void
  (e: 'cancel'): void
  (e: 'test'): void
  (e: 'clear'): void
}>()

const providerNames: Record<string, string> = {
  tmdb: 'TMDb',
  douban: '豆瓣',
  bangumi: 'Bangumi',
  thetvdb: 'TheTVDB',
  fanart: 'Fanart.tv',
  openai: 'OpenAI',
  siliconflow: '硅基流动',
  deepseek: 'DeepSeek',
  adult: 'Adult',
}

const defaultDescriptions: Record<string, string> = {
  tmdb: '电影/电视剧元数据',
  douban: '豆瓣评分和评论',
  bangumi: 'Bangumi 动画数据',
  thetvdb: 'TV 数据库',
  fanart: '高清海报背景',
  openai: 'GPT-4 智能助手',
  siliconflow: '国产大模型',
  deepseek: 'DeepSeek AI',
  adult: '18+ 番号刮削',
}

function getProviderName(provider: string): string {
  return providerNames[provider] || provider
}

function getProviderInitial(provider: string): string {
  const name = getProviderName(provider)
  return name.charAt(0).toUpperCase()
}

function getDefaultDescription(provider: string): string {
  return defaultDescriptions[provider] || ''
}

// 优化遮罩 Key 显示格式（添加空格增强可读性）
function formatMaskedKey(masked?: string | null): string {
  if (!masked) return '••••••••'
  // 在遮罩字符间添加空格，增强可读性
  return masked.replace(/(.{4})/, '$1 ').trim()
}
</script>
