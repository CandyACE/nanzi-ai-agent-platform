<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { modelApi, type AIModel, type AIModelCreate, type AIModelOption, type AIModelUpdate } from '../../api/model'
import { useToast } from '../../composables/useToast'
import { useUser } from '../../composables/useUser'
import ConfirmModal from '../ConfirmModal.vue'
import { 
  PlayIcon,
  PencilSquareIcon,
  TrashIcon,
  DocumentDuplicateIcon
} from '@heroicons/vue/24/outline'

const { showToast } = useToast()
const { hasPermission } = useUser()
const canSave = hasPermission('element:system:config_save')

const models = ref<AIModel[]>([])
const loadingModels = ref(false)
const testingModelId = ref<string | null>(null)
const testingFormModel = ref(false)
const showModelModal = ref(false)
const isEditingModel = ref(false)
const showDeleteConfirm = ref(false)
const pendingDeleteModel = ref<AIModel | null>(null)
const showStatusConfirm = ref(false)
const pendingStatusModel = ref<AIModel | null>(null)
const pendingStatusValue = ref(false)
const showProviderMenu = ref(false)
const showModelPicker = ref(false)
const loadingDiscoveredModels = ref(false)
const discoveredModels = ref<AIModelOption[]>([])
const modelForm = ref<Partial<AIModelCreate> & { id?: string; has_api_key?: boolean }>({
  name: '',
  model_id: '',
  provider: 'openai',
  type: 'llm',
  api_base_url: 'https://api.openai.com/v1',
  api_key: '',
  is_active: true
})

const modelIdConflict = computed(() => {
    const modelId = String(modelForm.value.model_id || '').trim()
    if (!modelId) return false
    return models.value.some((model) => model.model_id === modelId && model.id !== modelForm.value.id)
})

const providerDefaultBaseUrls: Record<string, string> = {
    openai: 'https://api.openai.com/v1',
    deepseek: 'https://api.deepseek.com',
    kimi: 'https://api.moonshot.cn/v1',
    zhipu: 'https://open.bigmodel.cn/api/paas/v4',
    siliconflow: 'https://api.siliconflow.cn/v1',
    dashscope: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    ollama: 'http://localhost:11434/v1',
}
const providerLabels: Record<string, string> = {
    openai: 'OpenAI',
    azure: 'Azure OpenAI',
    deepseek: 'DeepSeek',
    kimi: 'Kimi（月之暗面）',
    zhipu: '智谱 AI (GLM)',
    siliconflow: '硅基流动',
    dashscope: '阿里云百炼 (DashScope)',
    ollama: 'Ollama (Local)',
    other: '其他 OpenAI 兼容服务',
}
const providerCatalog = [
    { value: 'openai', label: 'OpenAI', icon: 'AI', color: '#111827' },
    { value: 'azure', label: 'Azure OpenAI', icon: 'AZ', color: '#2563eb' },
    { value: 'deepseek', label: 'DeepSeek', icon: 'DS', color: '#2563eb' },
    { value: 'kimi', label: 'Kimi（月之暗面）', icon: 'K', color: '#7c3aed' },
    { value: 'zhipu', label: '智谱 AI (GLM)', icon: 'GLM', color: '#0f766e' },
    { value: 'siliconflow', label: '硅基流动', icon: 'SF', color: '#ea580c' },
    { value: 'dashscope', label: '阿里云百炼', icon: 'Q', color: '#0891b2' },
    { value: 'ollama', label: 'Ollama (Local)', icon: 'OL', color: '#374151' },
    { value: 'other', label: '其他 OpenAI 兼容服务', icon: 'API', color: '#64748b' },
]
const supportedProviders = new Set(Object.keys(providerDefaultBaseUrls).concat(['azure', 'other']))
const supportedTypes = new Set(['llm', 'embedding', 'multimodal'])
const contextSizePresets = [32768, 65536, 131072, 262144]
const outputTokenPresets = [8192, 16384, 32768, 65536]
const lastProvider = ref<string>('openai')
const selectedProvider = computed(() =>
    providerCatalog.find((item) => item.value === String(modelForm.value.provider)) || providerCatalog[0]
)
const providerMeta = (provider: string) =>
    providerCatalog.find((item) => item.value === provider) || providerCatalog[providerCatalog.length - 1]

const formatTokenSize = (value?: number | null) => {
    if (!value) return ''
    if (value >= 1024 && value % 1024 === 0) return `${value / 1024}K`
    return String(value)
}

const providerBaseUrlHint = computed(() => {
    const provider = String(modelForm.value.provider || '')
    if (provider === 'azure') return 'Azure 需要填写你的资源专属 Endpoint'
    if (provider === 'other') return '可填写代理或其他 OpenAI 兼容服务地址'
    return providerDefaultBaseUrls[provider]
        ? `已提供默认地址：${providerDefaultBaseUrls[provider]}，也可以手工覆盖`
        : '系统将根据供应商提供默认地址'
})

const canDiscoverModels = computed(() => {
    const provider = String(modelForm.value.provider || '')
    const hasConfiguredApiKey = Boolean(
        String(modelForm.value.api_key || '').trim() ||
        (isEditingModel.value && modelForm.value.has_api_key)
    )
    return Boolean(
        provider &&
        provider !== 'azure' &&
        String(modelForm.value.api_base_url || '').trim() &&
        hasConfiguredApiKey
    )
})

const handleProviderChange = () => {
    const provider = String(modelForm.value.provider || '')
    const currentUrl = String(modelForm.value.api_base_url || '').trim()
    const previousDefault = providerDefaultBaseUrls[lastProvider.value]
    if (!currentUrl || (previousDefault && currentUrl === previousDefault)) {
        modelForm.value.api_base_url = providerDefaultBaseUrls[provider] || ''
    }
    lastProvider.value = provider
}

const fetchModels = async () => {
    loadingModels.value = true
    try {
        const res = await modelApi.list(undefined, true)
        models.value = res.data
    } catch (e: any) {
        showToast('获取模型列表失败', 'error')
    } finally {
        loadingModels.value = false
    }
}

const requestStatusChange = (model: AIModel) => {
    pendingStatusModel.value = model
    pendingStatusValue.value = !model.is_active
    showStatusConfirm.value = true
}

const closeStatusConfirm = () => {
    showStatusConfirm.value = false
    pendingStatusModel.value = null
}

const confirmStatusChange = async () => {
    const model = pendingStatusModel.value
    if (!model) return
    try {
        await modelApi.update(model.id, { is_active: pendingStatusValue.value })
        showToast(pendingStatusValue.value ? '模型已启用' : '模型已禁用', 'success')
        closeStatusConfirm()
        await fetchModels()
    } catch (e: any) {
        showToast(`状态更新失败: ${e.response?.data?.message || e.response?.data?.detail || e.message}`, 'error')
    }
}

const discoverProviderModels = async () => {
    const provider = String(modelForm.value.provider || '')
    if (provider === 'azure') {
        showToast('Azure OpenAI 请手工填写部署名称', 'warning')
        return
    }
    loadingDiscoveredModels.value = true
    showModelPicker.value = false
    try {
        const response = await modelApi.discover({
            provider,
            api_base_url: modelForm.value.api_base_url,
            api_key: modelForm.value.api_key,
            model_config_id: modelForm.value.id,
        })
        discoveredModels.value = response.data
        showModelPicker.value = true
        if (!response.data.length) {
            showToast('供应商没有返回可用模型', 'warning')
        }
    } catch (e: any) {
        showToast(`加载模型列表失败: ${e.response?.data?.message || e.response?.data?.detail || e.message}`, 'error')
    } finally {
        loadingDiscoveredModels.value = false
    }
}

const selectDiscoveredModel = (option: AIModelOption) => {
    modelForm.value.model_id = option.model_id
    if (!String(modelForm.value.name || '').trim()) {
        modelForm.value.name = option.name || option.model_id
    }
    showModelPicker.value = false
}

const testModel = async (model: AIModel) => {
    testingModelId.value = model.id
    try {
        const res = await modelApi.testConnection(model.id)
        if (res.data.status === 'success') {
            showToast(`${model.name}: ${res.data.message}`, 'success')
        } else {
            showToast(`${model.name}: ${res.data.message}`, 'error')
        }
    } catch (e: any) {
        showToast(`请求失败: ${e.response?.data?.detail || e.message}`, 'error')
    } finally {
        testingModelId.value = null
    }
}

const testCurrentModel = async () => {
    const modelId = String(modelForm.value.model_id || '').trim()
    const modelType = String(modelForm.value.type || '')
    if (!modelId) {
        showToast('请先填写模型 ID', 'warning')
        return
    }
    if (modelType === 'embedding') {
        showToast('Embedding 模型不能使用聊天模型测试', 'warning')
        return
    }

    testingFormModel.value = true
    try {
        const response = await modelApi.testConfig({
            provider: String(modelForm.value.provider || 'openai'),
            type: modelType,
            model_id: modelId,
            api_base_url: modelForm.value.api_base_url,
            api_key: modelForm.value.api_key,
            context_size: modelForm.value.context_size ?? null,
            max_output_tokens: modelForm.value.max_output_tokens ?? null,
            model_config_id: modelForm.value.id,
        })
        if (response.data.status === 'success') {
            showToast(`连接成功${response.data.response ? `：${response.data.response}` : ''}`, 'success')
        } else {
            showToast(response.data.message || '连接失败', 'error')
        }
    } catch (e: any) {
        showToast(`测试连接失败: ${e.response?.data?.detail || e.message}`, 'error')
    } finally {
        testingFormModel.value = false
    }
}

const openModelModal = (model?: AIModel, isClone = false) => {
    showProviderMenu.value = false
    showModelPicker.value = false
    discoveredModels.value = []
    if (model) {
        if (isClone) {
            isEditingModel.value = false
            modelForm.value = { 
                ...model, 
                id: undefined, 
                name: `${model.name} (Copy)`,
                model_id: `${model.model_id}-copy`,
                api_key: '' 
            }
        } else {
            isEditingModel.value = true
            modelForm.value = { ...model, api_key: '' }
        }
    } else {
        isEditingModel.value = false
        modelForm.value = {
            name: '',
            model_id: '',
            provider: 'openai',
            type: 'llm',
            api_base_url: providerDefaultBaseUrls.openai,
            api_key: '',
            is_active: true
        }
    }
    lastProvider.value = String(modelForm.value.provider || 'openai')
    showModelModal.value = true
}

const cloneModel = (model: AIModel) => {
    openModelModal(model, true)
}

const saveModel = async () => {
    if (!modelForm.value.name || !modelForm.value.model_id) {
        showToast('请填写名称和模型ID', 'warning')
        return
    }
    if (modelIdConflict.value) {
        showToast('模型 ID 已存在，请更换后再保存', 'warning')
        return
    }
    
    try {
        const payload: AIModelUpdate = {
            name: modelForm.value.name,
            model_id: modelForm.value.model_id,
            api_base_url: modelForm.value.api_base_url,
            context_size: modelForm.value.context_size ?? null,
            max_output_tokens: modelForm.value.max_output_tokens ?? null,
            api_key: modelForm.value.api_key,
            is_active: modelForm.value.is_active,
        }
        // Legacy rows may contain provider/type values that are no longer
        // supported. Omit unchanged legacy values so a harmless name edit can
        // still be saved; selecting a supported value submits it normally.
        if (supportedProviders.has(String(modelForm.value.provider))) {
            payload.provider = modelForm.value.provider
        }
        if (supportedTypes.has(String(modelForm.value.type))) {
            payload.type = modelForm.value.type
        }
        if (payload.api_key === '') {
            delete payload.api_key
        }

        if (isEditingModel.value && modelForm.value.id) {
            await modelApi.update(modelForm.value.id, payload)
            showToast('更新成功', 'success')
        } else {
            await modelApi.create(payload as AIModelCreate)
            showToast('创建成功', 'success')
        }
        showModelModal.value = false
        fetchModels()
    } catch (e: any) {
        showToast('保存失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message), 'error')
    }
}

const deleteModel = (model: AIModel) => {
    pendingDeleteModel.value = model
    showDeleteConfirm.value = true
}

const closeDeleteConfirm = () => {
    showDeleteConfirm.value = false
    pendingDeleteModel.value = null
}

const confirmDeleteModel = async () => {
    const model = pendingDeleteModel.value
    if (!model) return
    try {
        await modelApi.delete(model.id)
        showToast('已删除', 'success')
        closeDeleteConfirm()
        fetchModels()
    } catch(e: any) {
        showToast('删除失败', 'error')
    }
}

const closeFloatingMenus = () => {
    showProviderMenu.value = false
    showModelPicker.value = false
}

// Expose refresh to parent if needed
defineExpose({ refresh: fetchModels })

onMounted(() => {
  fetchModels()
  document.addEventListener('click', closeFloatingMenus)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', closeFloatingMenus)
})
</script>

<template>
  <div class="h-full overflow-y-auto pb-6 custom-scrollbar p-1">
      <div class="bg-white shadow rounded-lg overflow-hidden">
         <div class="p-4 border-b border-gray-100 flex justify-between items-center">
            <h3 class="text-lg font-medium text-gray-900">AI 模型注册表</h3>
            <button 
                v-if="canSave"
                @click="openModelModal()"
                class="px-3 py-1.5 bg-primary text-white text-sm rounded-md hover:bg-primary-dark transition-colors"
            >
                + 添加模型
            </button>
         </div>
         
         <div v-if="loadingModels" class="p-8 text-center text-gray-400">加载中...</div>
         <div v-else class="overflow-x-auto">
         <table class="min-w-[1080px] w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[360px]">模型</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[220px]">提供商</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">类型</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider sticky right-0 bg-gray-50">操作</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="m in models" :key="m.id" class="hover:bg-gray-50">
                    <td class="px-6 py-4 min-w-[360px]">
                        <div class="text-sm font-semibold text-gray-900">{{ m.name }}</div>
                        <div class="mt-1 text-xs text-gray-500 font-mono truncate max-w-[520px]" :title="m.model_id">{{ m.model_id }}</div>
                        <div v-if="m.context_size || m.max_output_tokens" class="mt-2 flex flex-wrap gap-1.5 text-[11px]">
                            <span v-if="m.context_size" class="token-limit-badge">输入 {{ formatTokenSize(m.context_size) }}</span>
                            <span v-if="m.max_output_tokens" class="token-limit-badge">输出 {{ formatTokenSize(m.max_output_tokens) }}</span>
                        </div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        <span class="inline-flex items-center gap-2 px-2.5 py-1 text-xs font-semibold rounded-full bg-blue-50 text-blue-800">
                            <span class="provider-mini-icon" :style="{ backgroundColor: providerMeta(m.provider).color }">{{ providerMeta(m.provider).icon }}</span>
                            {{ providerLabels[m.provider] || m.provider }}
                        </span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        <span class="inline-flex items-center space-x-1.5 select-none">
                            <svg v-if="m.type === 'multimodal'" class="w-4 h-4 text-purple-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" title="多模态模型">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                            <svg v-else class="w-4 h-4 text-blue-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" title="语言模型">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                            </svg>
                            <span class="font-medium">{{ m.type === 'llm' ? 'LLM' : (m.type === 'multimodal' ? 'Multimodal' : m.type) }}</span>
                        </span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <button
                            v-if="canSave"
                            type="button"
                            role="switch"
                            :aria-checked="m.is_active"
                            :title="m.is_active ? '禁用模型' : '启用模型'"
                            class="inline-flex items-center gap-2"
                            @click="requestStatusChange(m)"
                        >
                            <span class="status-switch" :class="m.is_active ? 'status-switch-on' : 'status-switch-off'">
                                <span class="status-switch-knob"></span>
                            </span>
                            <span class="text-xs font-semibold" :class="m.is_active ? 'text-green-700' : 'text-gray-500'">{{ m.is_active ? '启用' : '停用' }}</span>
                        </button>
                        <span v-else class="text-xs font-semibold" :class="m.is_active ? 'text-green-700' : 'text-gray-500'">{{ m.is_active ? '启用' : '停用' }}</span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium sticky right-0 bg-white shadow-[-8px_0_12px_-12px_rgba(15,23,42,0.4)]">
                        <div v-if="canSave" class="flex items-center justify-end space-x-2">
                            <button 
                                @click="testModel(m)" 
                                :disabled="testingModelId === m.id"
                                title="测试连接"
                                class="p-1.5 text-indigo-600 hover:bg-indigo-50 rounded-md transition-colors disabled:opacity-50"
                            >
                                <svg v-if="testingModelId === m.id" class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                                <PlayIcon v-else class="h-4 w-4" />
                            </button>
                            
                            <button 
                                @click="openModelModal(m)" 
                                title="编辑模型"
                                class="p-1.5 text-primary hover:bg-blue-50 rounded-md transition-colors"
                            >
                                <PencilSquareIcon class="h-4 w-4" />
                            </button>

                            <button 
                                @click="cloneModel(m)" 
                                title="复制模型"
                                class="p-1.5 text-gray-600 hover:bg-gray-100 rounded-md transition-colors"
                            >
                                <DocumentDuplicateIcon class="h-4 w-4" />
                            </button>
                            
                            <button 
                                @click="deleteModel(m)" 
                                title="删除模型"
                                class="p-1.5 text-red-500 hover:bg-red-50 rounded-md transition-colors"
                            >
                                <TrashIcon class="h-4 w-4" />
                            </button>
                        </div>
                        <span v-else class="text-gray-400 italic text-xs">仅限管理</span>
                     </td>
                </tr>
                <tr v-if="models.length === 0">
                    <td colspan="5" class="px-6 py-8 text-center text-gray-400 text-sm">暂无模型配置</td>
                </tr>
            </tbody>
         </table>
         </div>
      </div>

      <!-- Model Modal (Moved inside component for self-containment) -->
      <div v-if="showModelModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-900/50 backdrop-blur-sm" @click="showProviderMenu = false; showModelPicker = false">
          <div class="bg-white rounded-xl shadow-xl max-w-xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-4 text-left" @click.stop>
              <h3 class="text-lg font-bold text-gray-900">{{ isEditingModel ? '编辑模型' : '添加新模型' }}</h3>
              
              <div class="space-y-3">
                  <div>
                     <label class="block text-sm font-medium text-gray-700">提供商</label>
                     <div class="relative mt-1">
                         <button type="button" class="provider-select-trigger" @click.stop="showProviderMenu = !showProviderMenu; showModelPicker = false">
                             <span class="flex items-center gap-2 min-w-0">
                                 <span class="provider-icon" :style="{ backgroundColor: selectedProvider.color }">{{ selectedProvider.icon }}</span>
                                 <span class="truncate">{{ selectedProvider.label }}</span>
                             </span>
                             <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                         </button>
                         <div v-if="showProviderMenu" class="provider-menu" @click.stop>
                             <button
                                 v-for="provider in providerCatalog"
                                 :key="provider.value"
                                 type="button"
                                 class="provider-menu-item"
                                 :class="String(modelForm.provider) === provider.value ? 'provider-menu-item-active' : ''"
                                 @click="modelForm.provider = provider.value; handleProviderChange(); showProviderMenu = false"
                             >
                                 <span class="provider-icon" :style="{ backgroundColor: provider.color }">{{ provider.icon }}</span>
                                 <span class="text-left min-w-0">
                                     <span class="block truncate font-medium">{{ provider.label }}</span>
                                     <span class="block truncate text-[11px] text-gray-400">{{ providerDefaultBaseUrls[provider.value] || '需要手工填写接口地址' }}</span>
                                 </span>
                                 <svg v-if="String(modelForm.provider) === provider.value" class="w-4 h-4 ml-auto text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                             </button>
                         </div>
                     </div>
                  </div>
                  <div>
                     <label class="block text-sm font-medium text-gray-700">API Base URL (可选)</label>
                     <input v-model="modelForm.api_base_url" class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-primary focus:border-primary sm:text-sm" :placeholder="providerBaseUrlHint" />
                     <p class="text-xs text-gray-500 mt-1">{{ providerBaseUrlHint }}</p>
                  </div>
                  <div>
                     <label class="block text-sm font-medium text-gray-700">API Key (可选)</label>
                     <input v-model="modelForm.api_key" type="password" class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-primary focus:border-primary sm:text-sm" :placeholder="isEditingModel && modelForm.has_api_key ? '已配置，留空则保留原密钥' : '留空则使用系统默认密钥'" />
                  </div>
                  <div>
                     <div class="flex items-center justify-between">
                         <label class="block text-sm font-medium text-gray-700">模型 ID (API)</label>
                         <button type="button" class="discover-model-button" :class="{ 'discover-model-button-disabled': !canDiscoverModels }" :disabled="loadingDiscoveredModels || !canDiscoverModels" :title="canDiscoverModels ? '加载当前供应商模型列表' : (isEditingModel && modelForm.has_api_key ? '请先填写 API Base URL' : '请先填写 API Base URL 和 API Key')" @click="discoverProviderModels">
                             <svg v-if="loadingDiscoveredModels" class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/></svg>
                             <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7h16M4 12h16M4 17h16" /></svg>
                             {{ loadingDiscoveredModels ? '加载中' : '加载模型列表' }}
                         </button>
                     </div>
                     <div class="relative mt-1">
                         <input v-model="modelForm.model_id" :class="modelIdConflict ? 'border-red-400 focus:ring-red-500 focus:border-red-500' : 'border-gray-300 focus:ring-primary focus:border-primary'" class="block w-full rounded-md shadow-sm sm:text-sm font-mono pr-3" placeholder="例如: gpt-4o" />
                         <div v-if="showModelPicker" class="model-picker-menu" @click.stop>
                             <div class="px-3 py-2 border-b border-gray-100 text-xs text-gray-500">选择 {{ providerLabels[String(modelForm.provider)] || modelForm.provider }} 模型</div>
                             <button v-for="option in discoveredModels" :key="option.model_id" type="button" class="model-picker-item" @click="selectDiscoveredModel(option)">
                                 <span class="font-medium text-gray-800">{{ option.name }}</span>
                                 <span class="text-xs font-mono text-gray-500">{{ option.model_id }}</span>
                             </button>
                         </div>
                     </div>
                     <p class="text-xs text-gray-500 mt-1">云服务商定义的实际模型标识符；可手工填写，也可从供应商列表选择</p>
                     <p v-if="modelIdConflict" class="text-xs text-red-600 mt-1">该 model_id 已存在，模型 ID 必须全局唯一</p>
                  </div>
                  <div>
                     <label class="block text-sm font-medium text-gray-700">模型类型</label>
                     <select v-model="modelForm.type" class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-primary focus:border-primary sm:text-sm">
                         <option value="llm">LLM (文本生成)</option>
                         <option value="embedding">Embedding (向量)</option>
                         <option value="multimodal">Multimodal (多模态)</option>
                     </select>
                  </div>
                  <div>
                     <label class="block text-sm font-medium text-gray-700">模型名称</label>
                     <input v-model="modelForm.name" class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-primary focus:border-primary sm:text-sm" placeholder="例如: GPT-4o 生产版" />
                     <p class="text-xs text-gray-500 mt-1">用于系统界面展示，不影响实际 API 调用</p>
                  </div>
                  <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <div>
                          <label class="block text-sm font-medium text-gray-700">输入上下文（可选）</label>
                          <input v-model.number="modelForm.context_size" type="number" min="1" step="1" class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-primary focus:border-primary sm:text-sm" placeholder="使用供应商默认值" />
                          <div class="token-preset-row">
                              <button v-for="size in contextSizePresets" :key="size" type="button" class="token-preset-button" :class="modelForm.context_size === size ? 'token-preset-button-active' : ''" @click="modelForm.context_size = size">{{ formatTokenSize(size) }}</button>
                          </div>
                          <p class="text-xs text-gray-500 mt-1">用于上下文压缩；留空使用运行时默认值</p>
                      </div>
                      <div>
                          <label class="block text-sm font-medium text-gray-700">输出上限（可选）</label>
                          <input v-model.number="modelForm.max_output_tokens" type="number" min="1" step="1" class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-primary focus:border-primary sm:text-sm" placeholder="使用供应商默认值" />
                          <div class="token-preset-row">
                              <button v-for="size in outputTokenPresets" :key="size" type="button" class="token-preset-button" :class="modelForm.max_output_tokens === size ? 'token-preset-button-active' : ''" @click="modelForm.max_output_tokens = size">{{ formatTokenSize(size) }}</button>
                          </div>
                          <p class="text-xs text-gray-500 mt-1">发送为 API 的最大输出 token；留空使用供应商默认值</p>
                      </div>
                  </div>
                  <div class="flex items-center">
                      <input id="is_active" type="checkbox" v-model="modelForm.is_active" class="h-4 w-4 text-primary focus:ring-primary border-gray-300 rounded" />
                      <label for="is_active" class="ml-2 block text-sm text-gray-900">启用此模型</label>
                  </div>
              </div>
              
              <div class="flex justify-end space-x-3 mt-6">
                  <button @click="showModelModal = false" class="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50">取消</button>
                  <button type="button" @click="testCurrentModel" :disabled="testingFormModel || !String(modelForm.model_id || '').trim() || modelForm.type === 'embedding'" class="inline-flex items-center gap-2 px-4 py-2 border border-blue-200 rounded-md text-sm font-medium text-primary bg-blue-50 hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed">
                      <svg v-if="testingFormModel" class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path></svg>
                      {{ testingFormModel ? '测试中' : '测试连接' }}
                  </button>
                  <button @click="saveModel" :disabled="modelIdConflict" class="px-4 py-2 bg-primary border border-transparent rounded-md text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50 disabled:cursor-not-allowed">保存</button>
              </div>
          </div>
      </div>

      <ConfirmModal
        v-if="showStatusConfirm && pendingStatusModel"
        :title="pendingStatusValue ? '启用模型' : '禁用模型'"
        :message="pendingStatusValue ? `确定启用模型「${pendingStatusModel.name}」吗？启用后它会重新出现在模型选择列表中。` : `确定禁用模型「${pendingStatusModel.name}」吗？禁用后新请求将不能选择它。`"
        :confirm-text="pendingStatusValue ? '确认启用' : '确认禁用'"
        cancel-text="取消"
        :type="pendingStatusValue ? 'primary' : 'danger'"
        @confirm="confirmStatusChange"
        @cancel="closeStatusConfirm"
      />

      <ConfirmModal
        v-if="showDeleteConfirm && pendingDeleteModel"
        title="删除模型"
        :message="`确定要删除模型「${pendingDeleteModel.name}」吗？删除后将无法恢复。`"
        confirm-text="删除"
        cancel-text="取消"
        type="danger"
        @confirm="confirmDeleteModel"
        @cancel="closeDeleteConfirm"
      />
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: rgba(156, 163, 175, 0.3);
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: rgba(156, 163, 175, 0.5);
}

.provider-icon,
.provider-mini-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  color: white;
  font-weight: 700;
  letter-spacing: -0.04em;
}

.provider-icon {
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 0.55rem;
  font-size: 0.65rem;
}

.provider-mini-icon {
  width: 1.25rem;
  height: 1.25rem;
  border-radius: 0.4rem;
  font-size: 0.5rem;
}

.provider-select-trigger {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  border: 1px solid rgb(209 213 219);
  border-radius: 0.375rem;
  background: white;
  padding: 0.45rem 0.65rem;
  font-size: 0.875rem;
  color: rgb(31 41 55);
  transition: border-color 150ms, box-shadow 150ms;
}

.provider-select-trigger:hover,
.provider-select-trigger:focus {
  border-color: rgb(37 99 235);
  box-shadow: 0 0 0 2px rgb(219 234 254);
  outline: none;
}

.provider-menu,
.model-picker-menu {
  position: absolute;
  z-index: 60;
  overflow: hidden;
  border: 1px solid rgb(226 232 240);
  border-radius: 0.75rem;
  background: white;
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.16);
}

.provider-menu {
  left: 0;
  right: 0;
  top: calc(100% + 0.35rem);
  max-height: 18rem;
  overflow-y: auto;
  padding: 0.3rem;
}

.provider-menu-item,
.model-picker-item {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 0.65rem;
  border-radius: 0.55rem;
  padding: 0.55rem 0.6rem;
  text-align: left;
  transition: background-color 150ms;
}

.token-limit-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 9999px;
  background: rgb(248 250 252);
  color: rgb(100 116 139);
  padding: 0.15rem 0.45rem;
}

.token-preset-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  margin-top: 0.4rem;
}

.token-preset-button {
  border: 1px solid transparent;
  border-radius: 9999px;
  padding: 0.15rem 0.45rem;
  color: rgb(51 65 85);
  font-size: 0.75rem;
}

.token-preset-button:hover,
.token-preset-button-active {
  border-color: rgb(203 213 225);
  background: white;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
}

.provider-menu-item:hover,
.model-picker-item:hover {
  background: rgb(239 246 255);
}

.provider-menu-item-active {
  background: rgb(239 246 255);
  color: rgb(29 78 216);
}

.model-picker-menu {
  left: 0;
  right: 0;
  top: calc(100% + 0.35rem);
  max-height: 15rem;
  overflow-y: auto;
}

.model-picker-item {
  flex-direction: column;
  align-items: flex-start;
  gap: 0.15rem;
  border-radius: 0;
  padding: 0.65rem 0.75rem;
}

.discover-model-button {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  border-radius: 0.45rem;
  background: rgb(239 246 255);
  padding: 0.35rem 0.55rem;
  color: rgb(37 99 235);
  font-size: 0.75rem;
  font-weight: 600;
}

.discover-model-button:hover {
  background: rgb(219 234 254);
}

.discover-model-button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.status-switch {
  display: inline-flex;
  width: 2.25rem;
  height: 1.25rem;
  align-items: center;
  border-radius: 9999px;
  padding: 0.125rem;
  transition: background-color 150ms;
}

.status-switch-on {
  justify-content: flex-end;
  background: rgb(34 197 94);
}

.status-switch-off {
  justify-content: flex-start;
  background: rgb(203 213 225);
}

.status-switch-knob {
  display: block;
  width: 1rem;
  height: 1rem;
  border-radius: 9999px;
  background: white;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.25);
}
</style>
