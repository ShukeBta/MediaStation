<template>
  <div class="space-y-6">
    <!-- 头部 -->
    <div class="flex justify-between items-center">
      <div>
        <h2 class="text-lg font-semibold">API 配置</h2>
        <p class="text-xs mt-1" style="color: var(--text-muted)">
          配置各数据源 API Key，点击配置项可直接编辑
        </p>
      </div>
      <button @click="loadConfigs" class="btn btn-ghost btn-sm gap-1">
        <Icon icon="ph:arrow-clockwise" />
        刷新
      </button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="flex justify-center py-12">
      <span class="loading loading-spinner loading-lg text-primary"></span>
    </div>

    <!-- 配置分组列表 -->
    <div v-else class="space-y-4">
      <!-- 影视数据源 -->
      <ConfigGroup title="影视数据源" icon="ph:film-strip">
        <ConfigRow
          v-for="p in mediaProviders"
          :key="p.provider"
          :config="p"
          :editing="editingProvider === p.provider"
          :testing="testing === p.provider"
          @edit="startEdit(p.provider, p)"
          @save="saveConfig(p.provider)"
          @cancel="cancelEdit"
          @test="testConnection(p.provider)"
          @clear="confirmClear(p.provider)"
          v-model:edit-form="editForm"
        />
      </ConfigGroup>

      <!-- AI 服务 -->
      <ConfigGroup title="AI 服务" icon="ph:brain">
        <ConfigRow
          v-for="p in aiProviders"
          :key="p.provider"
          :config="p"
          :editing="editingProvider === p.provider"
          :testing="testing === p.provider"
          @edit="startEdit(p.provider, p)"
          @save="saveConfig(p.provider)"
          @cancel="cancelEdit"
          @test="testConnection(p.provider)"
          @clear="confirmClear(p.provider)"
          v-model:edit-form="editForm"
        />
      </ConfigGroup>

      <!-- 其他服务 -->
      <ConfigGroup title="其他服务" icon="ph:gear">
        <ConfigRow
          v-for="p in otherProviders"
          :key="p.provider"
          :config="p"
          :editing="editingProvider === p.provider"
          :testing="testing === p.provider"
          @edit="startEdit(p.provider, p)"
          @save="saveConfig(p.provider)"
          @cancel="cancelEdit"
          @test="testConnection(p.provider)"
          @clear="confirmClear(p.provider)"
          v-model:edit-form="editForm"
        />
      </ConfigGroup>
    </div>

    <!-- 测试连接结果 Modal -->
    <Transition name="modal">
      <div v-if="showTestResult" class="modal modal-open">
        <div class="modal-box relative overflow-hidden">
          <!-- 成功/失败 顶部色条 -->
          <div 
            class="absolute top-0 left-0 right-0 h-1.5"
            :class="testResult?.success ? 'bg-success' : 'bg-error'"
          ></div>
          
          <!-- 关闭按钮 -->
          <button 
            @click="showTestResult = false"
            class="btn btn-sm btn-circle absolute right-2 top-2 btn-ghost"
          >
            <Icon icon="ph:x" />
          </button>

          <!-- 图标 + 结果 -->
          <div class="flex flex-col items-center text-center py-6">
            <!-- 动态图标 -->
            <div 
              class="w-16 h-16 rounded-full flex items-center justify-center mb-4"
              :class="testResult?.success ? 'bg-success/10' : 'bg-error/10'"
            >
              <Icon 
                :icon="testResult?.success ? 'ph:check-circle-fill' : 'ph:x-circle-fill'" 
                class="text-5xl"
                :class="testResult?.success ? 'text-success' : 'text-error'"
              />
            </div>

            <h3 class="font-bold text-lg mb-2">
              {{ testResult?.success ? '连接成功 🎉' : '连接失败' }}
            </h3>
            
            <p 
              class="text-sm max-w-xs"
              :class="testResult?.success ? 'text-success/80' : 'text-error/80'"
            >
              {{ testResult?.message }}
            </p>
          </div>

          <!-- 操作按钮 -->
          <div class="modal-action mt-2">
            <button 
              @click="showTestResult = false"
              class="btn gap-1"
              :class="testResult?.success ? 'btn-success' : 'btn-error'"
            >
              <Icon icon="ph:check" />
              知道了
            </button>
          </div>
        </div>
        <div class="modal-backdrop" @click="showTestResult = false"></div>
      </div>
    </Transition>

    <!-- 清除确认 Modal -->
    <Transition name="modal">
      <div v-if="showClearConfirm" class="modal modal-open">
        <div class="modal-box relative">
          <!-- 警告图标 -->
          <div class="flex flex-col items-center text-center py-4">
            <div class="w-16 h-16 rounded-full bg-warning/10 flex items-center justify-center mb-4">
              <Icon icon="ph:warning-circle-fill" class="text-5xl text-warning" />
            </div>
            
            <h3 class="font-bold text-lg mb-2">确认清除配置</h3>
            <p class="text-sm opacity-70">
              确定要清除 <span class="font-semibold text-warning">{{ getProviderName(clearTarget || '') }}</span> 的 API 配置吗？
            </p>
            <p class="text-xs mt-2 opacity-50">此操作不可恢复</p>
          </div>

          <!-- 操作按钮 -->
          <div class="modal-action">
            <button @click="showClearConfirm = false" class="btn btn-ghost">
              取消
            </button>
            <button @click="executeClear" class="btn btn-error gap-1">
              <Icon icon="ph:trash" />
              确认清除
            </button>
          </div>
        </div>
        <div class="modal-backdrop" @click="showClearConfirm = false"></div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import { apiConfigApi } from '@/api/config'

// 子组件
import ConfigGroup from './ConfigGroup.vue'
import ConfigRow from './ConfigRow.vue'

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

const configs = ref<ApiConfig[]>([])
const loading = ref(true)
const editingProvider = ref<string | null>(null)
const showTestResult = ref(false)
const testResult = ref<{ success: boolean; message: string } | null>(null)
const testing = ref<string | null>(null)
const showClearConfirm = ref(false)
const clearTarget = ref<string | null>(null)

const editForm = ref<EditForm>({
  api_key: '',
  base_url: '',
})

// Provider 分类 (只保留常用数据源，隐藏 TheTVDB)
const mediaProviderKeys = ['tmdb', 'douban', 'bangumi']
const aiProviderKeys = ['openai', 'siliconflow', 'deepseek']

const mediaProviders = computed(() =>
  configs.value.filter(c => mediaProviderKeys.includes(c.provider))
)

const aiProviders = computed(() =>
  configs.value.filter(c => aiProviderKeys.includes(c.provider))
)

const otherProviders = computed(() =>
  configs.value.filter(c => !mediaProviderKeys.includes(c.provider) && !aiProviderKeys.includes(c.provider))
)

async function loadConfigs() {
  loading.value = true
  try {
    const { data } = await apiConfigApi.list()
    configs.value = data
  } catch (e) {
    console.error('Failed to load API configs:', e)
  } finally {
    loading.value = false
  }
}

function startEdit(provider: string, config: ApiConfig) {
  editingProvider.value = provider
  editForm.value = {
    api_key: '',
    base_url: config.base_url || '',
  }
}

function cancelEdit() {
  editingProvider.value = null
  editForm.value = { api_key: '', base_url: '' }
}

async function saveConfig(provider: string) {
  try {
    await apiConfigApi.update(provider, {
      api_key: editForm.value.api_key || undefined,
      base_url: editForm.value.base_url || undefined,
    })
    editingProvider.value = null
    await loadConfigs()
  } catch (e) {
    console.error('Failed to save config:', e)
  }
}

// 发起清除确认
function confirmClear(provider: string) {
  clearTarget.value = provider
  showClearConfirm.value = true
}

// 执行清除
async function executeClear() {
  if (!clearTarget.value) return
  try {
    await apiConfigApi.delete(clearTarget.value)
    showClearConfirm.value = false
    clearTarget.value = null
    await loadConfigs()
  } catch (e) {
    console.error('Failed to clear config:', e)
  }
}

async function testConnection(provider: string) {
  testing.value = provider
  try {
    const { data } = await apiConfigApi.test(provider)
    testResult.value = data
    showTestResult.value = true
  } catch (e: any) {
    testResult.value = { 
      success: false, 
      message: e?.response?.data?.detail || `测试失败: ${e.message || e}` 
    }
    showTestResult.value = true
  } finally {
    testing.value = null
  }
}

function getProviderName(provider: string): string {
  const names: Record<string, string> = {
    tmdb: 'TMDb',
    douban: '豆瓣',
    bangumi: 'Bangumi',
    openai: 'OpenAI',
    siliconflow: '硅基流动',
    deepseek: 'DeepSeek',
  }
  return names[provider] || provider
}

onMounted(() => {
  loadConfigs()
})
</script>

<style scoped>
/* 弹窗进入/退出动画 */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
