<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import axios from '@/utils/axios'
import { useToast } from '@/composables/useToast'
import { useUser } from '@/composables/useUser'
import ConfirmModal from '../../components/ConfirmModal.vue'
import Switch from '../Switch.vue'
import McpToolTester from './McpToolTester.vue'
import { buildDefaultMcpServerName } from '@/utils/mcpServerName'
import { 
  PlusIcon,
  BeakerIcon,
  EyeIcon,
  EyeSlashIcon,
  CodeBracketIcon,
  ListBulletIcon,
  ArrowPathIcon,
  TrashIcon,
  PencilSquareIcon,
  LinkIcon,
  CloudArrowDownIcon,
  MagnifyingGlassIcon,
  SparklesIcon,
  ShoppingBagIcon
} from '@heroicons/vue/24/outline'

const props = withDefaults(defineProps<{
  scope?: 'global' | 'personal'
}>(), {
  scope: 'global'
})

const { showToast } = useToast()
const { userInfo } = useUser()
const canSave = computed(() => {
  if (props.scope === 'personal') return true
  return userInfo.value?.role === 'admin'
})

const getApiErrorMessage = (error: any, fallback: string) => {
  const responseData = error?.response?.data
  const candidates = [
    responseData?.message,
    responseData?.detail,
    responseData?.data?.message,
    responseData?.data?.detail,
  ]
  const message = candidates.find((value) => typeof value === 'string' && value.trim())
  return message || fallback
}

const servers = ref<any[]>([])
const loading = ref(false)
const showAddModal = ref(false)
const isEditing = ref(false)
const editingId = ref('')

// Tool Tester Logic
const showTester = ref(false)
const toolToTest = ref<any>(null)

const openTester = (tool: any) => {
  toolToTest.value = tool
  showTester.value = true
}

const wizardStep = ref<1 | 2>(1) // 1: Input & Verify, 2: Preview & Name
const verifying = ref(false)
const discoveredTools = ref<any[]>([])
const syncLoading = ref<Record<string, boolean>>({})
const statusLoading = ref<Record<string, boolean>>({})

type McpAgentUsage = {
  id: string
  name: string
  display_name: string
  is_enabled: boolean
  active: boolean
  version_count: number
}

type McpServerUsage = {
  server_id: string
  bound_agent_count: number
  active_agent_count: number
  bound_version_count: number
  agents: McpAgentUsage[]
}

const selectedServerUsage = ref<McpServerUsage | null>(null)
const usageLoading = ref<Record<string, boolean>>({})
const showStatusConfirm = ref(false)
const statusConfirmServer = ref<any | null>(null)
const statusConfirmUsage = ref<McpServerUsage | null>(null)
const statusConfirmLoading = ref(false)

// Batch Actions Logic
const selectedToolIds = ref<Set<string>>(new Set())
const selectedServer = ref<any>(null)
const tools = ref<any[]>([])
const toolsLoading = ref(false)
const isSelectedServerEnabled = computed(() => Number(selectedServer.value?.enabled_status) === 1)
const canManageSelectedTools = computed(() => canSave.value && isSelectedServerEnabled.value)
const canManageTool = (tool: any) => canManageSelectedTools.value && tool?.is_available !== false

const isAllSelected = computed(() => {
  const selectableTools = tools.value.filter(tool => tool.is_available !== false)
  return selectableTools.length > 0 && selectedToolIds.value.size === selectableTools.length
})

const toggleSelectAll = () => {
  if (!canManageSelectedTools.value) return
  if (isAllSelected.value) {
    selectedToolIds.value.clear()
  } else {
    tools.value
      .filter(tool => tool.is_available !== false)
      .forEach(tool => selectedToolIds.value.add(tool.id))
  }
}

const toggleSelectTool = (id: string) => {
  if (!canManageSelectedTools.value) return
  if (selectedToolIds.value.has(id)) {
    selectedToolIds.value.delete(id)
  } else {
    selectedToolIds.value.add(id)
  }
}

const batchUpdateStatus = async (published: boolean) => {
  const ids = tools.value
    .filter(tool => selectedToolIds.value.has(tool.id) && tool.is_available !== false)
    .map(tool => tool.id)
  if (!canManageSelectedTools.value || ids.length === 0) return
  
  loading.value = true
  try {
    // Batch update in parallel
    await Promise.all(ids.map(id => 
      axios.put(`/api/portal/mcp/tools/${id}/publish?published=${published}`)
    ))
    
    showToast(`成功${published ? '发布' : '下线'} ${ids.length} 个工具`, 'success')
    if (selectedServer.value) {
      fetchTools(selectedServer.value.id)
      fetchServerUsage(selectedServer.value.id).then((usage) => {
        if (selectedServer.value) selectedServerUsage.value = usage
      })
    }
    selectedToolIds.value.clear()
  } catch (e) {
    showToast(getApiErrorMessage(e, '批量操作失败'), 'error')
  } finally {
    loading.value = false
  }
}

// Headers Editing Logic
const headerMode = ref<'simple' | 'advanced'>('simple')
const headerPairs = ref<{ key: string, value: string }[]>([{ key: '', value: '' }])

const addHeaderPair = () => {
  headerPairs.value.push({ key: '', value: '' })
}
const removeHeaderPair = (index: number) => {
  headerPairs.value.splice(index, 1)
  if (headerPairs.value.length === 0) addHeaderPair()
}

const newServer = ref({
  server_name: '',
  sse_url: '',
  auth_headers: '{}',
  enabled_status: 1
})

// Sync Header Pairs to JSON string
watch(headerPairs, (newPairs) => {
  if (headerMode.value === 'simple') {
    const obj: Record<string, string> = {}
    newPairs.forEach(p => {
      if (p.key.trim()) obj[p.key.trim()] = p.value
    })
    newServer.value.auth_headers = JSON.stringify(obj, null, 2)
  }
}, { deep: true })

// Sync JSON string to Header Pairs
const syncJsonToPairs = () => {
  try {
    const obj = JSON.parse(newServer.value.auth_headers)
    const pairs = Object.entries(obj).map(([k, v]) => ({ key: k, value: String(v) }))
    headerPairs.value = pairs.length > 0 ? pairs : [{ key: '', value: '' }]
  } catch (e) {
    console.error("Invalid JSON for headers")
  }
}

const toggleHeaderMode = () => {
  if (headerMode.value === 'advanced') {
    syncJsonToPairs()
    headerMode.value = 'simple'
  } else {
    headerMode.value = 'advanced'
  }
}

const fetchServers = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/portal/mcp/servers', {
      params: { scope: props.scope }
    })
    servers.value = res.data
  } catch (e) {
    showToast(getApiErrorMessage(e, '获取 MCP 服务列表失败'), 'error')
  } finally {
    loading.value = false
  }
}

const resetWizard = () => {
  isEditing.value = false
  editingId.value = ''
  wizardStep.value = 1
  verifying.value = false
  discoveredTools.value = []
  newServer.value = { server_name: '', sse_url: '', auth_headers: '{}', enabled_status: 1 }
  headerPairs.value = [{ key: '', value: '' }]
  headerMode.value = 'simple'
}

const openEditModal = (server: any) => {
  isEditing.value = true
  editingId.value = server.id
  wizardStep.value = 1
  newServer.value = {
    server_name: server.server_name,
    sse_url: server.sse_url,
    auth_headers: server.auth_headers || '{}',
    enabled_status: server.enabled_status
  }
  syncJsonToPairs()
  showAddModal.value = true
}

const toggleServerStatus = async (server: any, enabled: boolean) => {
  if (!canSave.value || statusLoading.value[server.id]) return false

  const nextStatus = enabled ? 1 : 0
  if (Number(server.enabled_status) === nextStatus) return true

  statusLoading.value[server.id] = true
  try {
    const response = await axios.put(`/api/portal/mcp/servers/${server.id}`, {
      server_name: server.server_name,
      sse_url: server.sse_url,
      auth_headers: server.auth_headers || '{}',
      enabled_status: nextStatus,
      scope: props.scope,
    })
    const savedStatus = Number(response.data?.enabled_status ?? nextStatus)
    server.enabled_status = savedStatus
    if (selectedServer.value?.id === server.id) {
      selectedServer.value = { ...selectedServer.value, enabled_status: savedStatus }
    }
    showToast(savedStatus === 1 ? 'MCP 服务已启用' : 'MCP 服务已禁用', 'success')
    return true
  } catch (e: any) {
    showToast(getApiErrorMessage(e, '更新 MCP 服务状态失败'), 'error')
    return false
  } finally {
    statusLoading.value[server.id] = false
  }
}

const fetchServerUsage = async (serverId: string): Promise<McpServerUsage | null> => {
  usageLoading.value[serverId] = true
  try {
    const response = await axios.get(`/api/portal/mcp/servers/${serverId}/usage`)
    return response.data
  } catch (e: any) {
    showToast(getApiErrorMessage(e, '获取 MCP 使用情况失败'), 'error')
    return null
  } finally {
    usageLoading.value[serverId] = false
  }
}

const formatUsageImpact = (usage: McpServerUsage | null, action: '禁用' | '删除') => {
  if (!usage || usage.bound_agent_count === 0) {
    return `${action}后，关联的 MCP 工具将立即不可用。`
  }

  const names = usage.agents
    .slice(0, 5)
    .map(agent => agent.display_name || agent.name)
    .join('、')
  const more = usage.agents.length > 5 ? ` 等 ${usage.agents.length} 个智能体` : ''
  return `${action}后，关联的 MCP 工具将立即不可用。\n受影响智能体：${names}${more}\n其中当前生效：${usage.active_agent_count} 个。`
}

const handleServerStatusChange = async (server: any, enabled: boolean) => {
  if (enabled) {
    await toggleServerStatus(server, true)
    return
  }

  if (statusLoading.value[server.id]) return
  statusLoading.value[server.id] = true
  try {
    const usage = await fetchServerUsage(server.id)
    if (!usage) return
    statusConfirmServer.value = server
    statusConfirmUsage.value = usage
    showStatusConfirm.value = true
  } finally {
    statusLoading.value[server.id] = false
  }
}

const executeStatusChange = async () => {
  if (!statusConfirmServer.value) return
  statusConfirmLoading.value = true
  const success = await toggleServerStatus(statusConfirmServer.value, false)
  statusConfirmLoading.value = false
  if (success) {
    showStatusConfirm.value = false
    statusConfirmServer.value = null
    statusConfirmUsage.value = null
  }
}

const cancelStatusConfirm = () => {
  if (statusConfirmLoading.value) return
  showStatusConfirm.value = false
  statusConfirmServer.value = null
  statusConfirmUsage.value = null
}

const handleVerify = async () => {
  if (!newServer.value.sse_url) {
    showToast('请输入 SSE 握手地址', 'warning')
    return
  }
  
  verifying.value = true
  try {
    const res = await axios.post('/api/portal/mcp/verify', newServer.value)
    discoveredTools.value = res.data.tools
    wizardStep.value = 2
    if (!newServer.value.server_name) {
        try {
            const url = new URL(newServer.value.sse_url)
            const baseName = buildDefaultMcpServerName(
              props.scope,
              userInfo.value?.user_name,
              url.hostname,
            )
            let candidateName = baseName
            let counter = 1
            while (servers.value.some((s: any) => s.server_name === candidateName)) {
                counter++
                candidateName = `${baseName}-${counter}`
            }
            newServer.value.server_name = candidateName
        } catch {
            newServer.value.server_name = buildDefaultMcpServerName(
              props.scope,
              userInfo.value?.user_name,
              '',
            )
        }
    }
    showToast('连接成功，已发现工具', 'success')
  } catch (e: any) {
    showToast(getApiErrorMessage(e, '连接失败，请检查地址或认证信息'), 'error')
  } finally {
    verifying.value = false
  }
}

const addServer = async () => {
  if (!newServer.value.server_name || !newServer.value.sse_url) {
    showToast('请填写完整信息', 'warning')
    return
  }
  if (headerMode.value === 'advanced') {
    try { JSON.parse(newServer.value.auth_headers) }
    catch (e) { showToast('JSON 格式错误', 'error'); return }
  }

  try {
    const payload = { ...newServer.value, scope: props.scope }
    if (isEditing.value) {
      await axios.put(`/api/portal/mcp/servers/${editingId.value}`, payload)
      showToast('更新成功', 'success')
    } else {
      await axios.post('/api/portal/mcp/servers', payload)
      showToast('添加成功', 'success')
    }
    showAddModal.value = false
    fetchServers()
    resetWizard()
  } catch (e: any) {
    showToast(getApiErrorMessage(e, '操作失败'), 'error')
  }
}

// Deletion Logic
const showDeleteConfirm = ref(false)
const serverToDelete = ref<string | null>(null)
const deleteServerUsage = ref<McpServerUsage | null>(null)
const deleteLoading = ref(false)

const confirmDeleteServer = async (server: any) => {
  const usage = await fetchServerUsage(server.id)
  if (!usage) return
  serverToDelete.value = server.id
  deleteServerUsage.value = usage
  showDeleteConfirm.value = true
}

const executeDeleteServer = async () => {
  if (!serverToDelete.value) return
  const deletingId = serverToDelete.value
  deleteLoading.value = true
  try {
    await axios.delete(`/api/portal/mcp/servers/${deletingId}`)
    showToast('删除成功', 'success')
    showDeleteConfirm.value = false
    serverToDelete.value = null
    deleteServerUsage.value = null
    fetchServers()
    if (selectedServer.value?.id === deletingId) {
      selectedServer.value = null
      selectedServerUsage.value = null
    }
  } catch (e) {
    showToast(getApiErrorMessage(e, '删除失败'), 'error')
  } finally {
    deleteLoading.value = false
  }
}

const cancelDeleteServer = () => {
  if (deleteLoading.value) return
  showDeleteConfirm.value = false
  serverToDelete.value = null
  deleteServerUsage.value = null
}

const syncTools = async (id: string) => {
  if (syncLoading.value[id]) return
  
  syncLoading.value[id] = true
  try {
    const response = await axios.post(`/api/portal/mcp/servers/${id}/sync`)
    const remoteDeletedCount = Number(response.data?.remote_deleted_count || 0)
    showToast(
      remoteDeletedCount > 0
        ? `同步成功，已标记 ${remoteDeletedCount} 个远端已删除工具`
        : '同步成功',
      'success',
    )
    fetchServers()
    if (selectedServer.value?.id === id) {
        fetchTools(id)
        fetchServerUsage(id).then((usage) => {
          if (selectedServer.value?.id === id) selectedServerUsage.value = usage
        })
    }
  } catch (e: any) {
    showToast(getApiErrorMessage(e, '同步失败'), 'error')
  } finally {
    syncLoading.value[id] = false
  }
}

const fetchTools = async (serverId: string) => {
  toolsLoading.value = true
  try {
    const res = await axios.get(`/api/portal/mcp/servers/${serverId}/tools`)
    tools.value = res.data
  } catch (e) {
    showToast(getApiErrorMessage(e, '获取工具列表失败'), 'error')
  } finally {
    toolsLoading.value = false
  }
}

const selectServer = (server: any) => {
  selectedServer.value = server
  selectedServerUsage.value = null
  selectedToolIds.value = new Set()
  fetchTools(server.id)
  fetchServerUsage(server.id).then((usage) => {
    if (selectedServer.value?.id === server.id) selectedServerUsage.value = usage
  })
}

const togglePublish = async (tool: any) => {
  if (!canManageTool(tool)) return
  try {
    const newStatus = !tool.is_published
    await axios.put(`/api/portal/mcp/tools/${tool.id}/publish?published=${newStatus}`)
    tool.is_published = newStatus
    showToast(newStatus ? '工具已发布' : '工具已下线', 'success')
    if (selectedServer.value) {
      fetchServerUsage(selectedServer.value.id).then((usage) => {
        if (selectedServer.value) selectedServerUsage.value = usage
      })
    }
  } catch (e) {
    showToast(getApiErrorMessage(e, '操作失败'), 'error')
  }
}

onMounted(fetchServers)
</script>

<template>
  <div class="flex h-full gap-6">
    <!-- Left: Server List -->
    <div class="w-1/3 flex flex-col bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      <!-- Market Guide (High Contrast with Dynamic Scope Theme) -->
      <div 
        class="p-4 text-white border-b border-white/10 transition-colors duration-300"
        :class="props.scope === 'personal' ? 'bg-slate-950' : 'bg-slate-900'"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <h4 
              class="text-sm font-black flex items-center transition-colors duration-300"
              :class="props.scope === 'personal' ? 'text-emerald-400' : 'text-indigo-400'"
            >
              <ShoppingBagIcon class="w-4 h-4 mr-1.5" />
              探索 MCP 市场
            </h4>
            <p class="text-[10px] text-slate-400 mt-1 leading-relaxed">
              {{ props.scope === 'personal' ? '去魔搭(ModelScope)寻找并接入属于您的私有扩展' : '去魔搭(ModelScope)寻找更多公共好用的工具集' }}
            </p>
            <div class="mt-2">
              <a 
                href="https://modelscope.cn/mcp" 
                target="_blank" 
                class="inline-flex items-center text-[10px] font-bold text-white px-2 py-1 rounded transition-all duration-200 shadow-sm"
                :class="props.scope === 'personal' ? 'bg-emerald-600 hover:bg-emerald-500' : 'bg-indigo-600 hover:bg-indigo-500'"
              >
                立即前往市场
                <MagnifyingGlassIcon class="w-3 h-3 ml-1" />
              </a>
            </div>
          </div>
        </div>
      </div>

      <div class="p-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/80">
        <div class="flex items-center space-x-2">
          <h3 class="text-xs font-bold text-gray-500 uppercase tracking-wider">
            {{ props.scope === 'personal' ? '已连接服务 (我的私有)' : '已连接服务 (平台公共)' }}
          </h3>
          <span v-if="props.scope === 'global' && !canSave" class="text-[10px] text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200/60 font-normal">
            管理员可编辑
          </span>
        </div>
        <button 
          v-if="canSave" 
          @click="resetWizard(); showAddModal = true" 
          class="px-3 py-1.5 text-white rounded-md transition-all flex items-center text-[11px] font-bold shadow-sm"
          :class="props.scope === 'personal' ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-primary hover:bg-primary-dark'"
        >
          <PlusIcon class="w-3.5 h-3.5 mr-1" />
          添加服务
        </button>
      </div>

      <div class="flex-1 overflow-y-auto custom-scrollbar">
        <div v-if="loading" class="p-8 text-center">
          <ArrowPathIcon class="w-6 h-6 animate-spin mx-auto text-gray-300" />
        </div>
        <div v-else-if="servers.length === 0" class="p-8 text-center text-gray-400 text-sm italic">
          暂无配置 MCP 服务
        </div>
        <div v-else class="divide-y divide-gray-50">
          <div 
            v-for="server in servers" 
            :key="server.id"
            @click="selectServer(server)"
            class="p-4 cursor-pointer transition-all hover:bg-blue-50/30"
            :class="selectedServer?.id === server.id ? 'bg-blue-50 border-l-4 border-primary' : 'border-l-4 border-transparent'"
          >
            <div class="flex justify-between items-start mb-1 gap-2">
              <span class="text-sm font-bold text-gray-900 truncate">{{ server.server_name }}</span>
              <div class="flex items-center gap-2 shrink-0" @click.stop>
                <span
                  class="text-[10px] font-semibold"
                  :class="server.enabled_status === 1 ? 'text-emerald-600' : 'text-gray-400'"
                >
                  {{ server.enabled_status === 1 ? '运行中' : '已禁用' }}
                </span>
                <Switch
                  :model-value="server.enabled_status === 1"
                  :disabled="!canSave || statusLoading[server.id]"
                  :loading="statusLoading[server.id]"
                  :aria-label="`${server.server_name}${server.enabled_status === 1 ? '禁用' : '启用'}`"
                  @update:model-value="handleServerStatusChange(server, $event)"
                />
                <div v-if="canSave" class="flex space-x-1">
                  <button @click="openEditModal(server)" class="p-1 text-gray-400 hover:text-blue-500 transition-colors" title="编辑配置">
                    <PencilSquareIcon class="w-4 h-4" />
                  </button>
                  <button @click="syncTools(server.id)" :disabled="syncLoading[server.id]" class="p-1 text-gray-400 hover:text-primary transition-colors">
                    <CloudArrowDownIcon class="w-4 h-4" :class="syncLoading[server.id] ? 'animate-bounce' : ''" />
                  </button>
                  <button @click="confirmDeleteServer(server)" class="p-1 text-gray-400 hover:text-red-500 transition-colors">
                    <TrashIcon class="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
            <div class="flex items-center text-[10px] text-gray-400 font-mono truncate mb-2">
              <LinkIcon class="w-3 h-3 mr-1" />
              {{ server.sse_url }}
            </div>
            <div class="flex justify-between items-center">
              <span class="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                {{ server.tool_count }} 工具 /
                <span v-if="server.enabled_status === 1" class="text-green-600 font-bold">{{ server.published_tool_count }} 已发布</span>
                <span v-else class="text-gray-400 font-bold">服务已禁用</span>
                <span v-if="server.stale_tool_count > 0" class="ml-1 text-amber-600">{{ server.stale_tool_count }} 个远端已删除</span>
              </span>
              <span class="text-[9px] text-gray-400 italic" v-if="server.last_sync_at">同步于 {{ new Date(server.last_sync_at).toLocaleString() }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Right: Tool List -->
    <div class="flex-1 flex flex-col bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      <div v-if="!selectedServer" class="flex-1 flex flex-col items-center justify-center text-gray-400">
        <SparklesIcon class="w-12 h-12 mb-4 opacity-20" />
        <p class="text-sm">请在左侧选择一个 MCP 服务查看工具</p>
      </div>
      
      <template v-else>
        <div class="p-4 border-b border-gray-200 bg-slate-50 flex justify-between items-center">
          <div class="flex items-center">
            <input 
              v-if="canSave"
              type="checkbox" 
              :checked="isAllSelected" 
              :disabled="!canManageSelectedTools"
              @change="toggleSelectAll"
              class="w-4 h-4 text-primary border-gray-400 rounded focus:ring-primary mr-3" 
            />
            <div>
              <h3 class="text-sm font-bold text-slate-800">{{ selectedServer.server_name }} 工具</h3>
              <p class="text-[10px] text-amber-600 mt-0.5" v-if="!isSelectedServerEnabled">服务已禁用，工具暂不可测试、发布或下线</p>
              <p class="text-[10px] text-slate-500 mt-0.5" v-else-if="selectedToolIds.size === 0">发布后的工具智能体才可见</p>
              <p class="text-[10px] text-primary font-black mt-0.5" v-else>已选中 {{ selectedToolIds.size }} 个项</p>
              <div v-if="selectedServerUsage" class="flex items-center gap-2 mt-1 text-[10px]">
                <span class="text-slate-500">绑定 {{ selectedServerUsage.bound_agent_count }} 个智能体</span>
                <span class="text-emerald-600">生效 {{ selectedServerUsage.active_agent_count }} 个</span>
                <span class="text-slate-400">{{ selectedServerUsage.bound_version_count }} 个版本配置</span>
              </div>
              <span v-else-if="usageLoading[selectedServer.id]" class="text-[10px] text-slate-400 mt-1">正在统计使用情况...</span>
            </div>
          </div>
          
          <div class="flex items-center space-x-3">
            <div v-if="canSave && selectedToolIds.size > 0" class="flex items-center space-x-2 animate-fade-in bg-white p-1 rounded-lg border border-gray-200 shadow-sm">
              <button @click="batchUpdateStatus(true)" :disabled="!canManageSelectedTools" class="text-[10px] font-bold bg-green-600 text-white px-3 py-1 rounded shadow-sm hover:bg-green-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed">批量发布</button>
              <button @click="batchUpdateStatus(false)" :disabled="!canManageSelectedTools" class="text-[10px] font-bold bg-slate-600 text-white px-3 py-1 rounded shadow-sm hover:bg-slate-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed">批量下线</button>
            </div>
            <button v-if="canSave" @click="syncTools(selectedServer.id)" :disabled="syncLoading[selectedServer.id]" class="text-[11px] font-bold text-primary flex items-center hover:underline bg-white px-2 py-1 rounded border border-gray-200">
              <ArrowPathIcon class="w-3.5 h-3.5 mr-1" :class="syncLoading[selectedServer.id] ? 'animate-spin' : ''" />
              刷新
            </button>
          </div>
        </div>

        <div class="flex-1 overflow-y-auto p-4 custom-scrollbar">
          <div v-if="toolsLoading" class="p-12 text-center">
            <ArrowPathIcon class="w-8 h-8 animate-spin mx-auto text-gray-200" />
          </div>
          <div v-else-if="tools.length === 0" class="p-12 text-center">
            <p class="text-gray-400 text-sm">该服务下暂无同步到的工具，请点击同步按钮。</p>
          </div>
          <div v-else class="grid grid-cols-1 gap-4">
            <div 
              v-for="tool in tools" 
              :key="tool.id" 
              @click="canManageTool(tool) && toggleSelectTool(tool.id)"
              class="p-4 rounded-lg border flex justify-between items-start group transition-all"
              :class="[
                canManageTool(tool) ? 'cursor-pointer' : 'cursor-default',
                selectedToolIds.has(tool.id) ? 'border-primary bg-blue-50/50 shadow-sm' : 'border-gray-100 bg-gray-50/30 hover:border-primary/30'
              ]"
            >
              <div class="flex items-start flex-1 min-w-0 pr-4">
                <input 
                  v-if="canSave"
                  type="checkbox" 
                  :checked="selectedToolIds.has(tool.id)" 
                  :disabled="!canManageTool(tool)"
                  @click.stop="toggleSelectTool(tool.id)"
                  class="w-3.5 h-3.5 mt-1 text-primary border-gray-300 rounded focus:ring-primary mr-3" 
                />
                <div class="flex-1 min-w-0">
                  <div class="flex items-center space-x-2 mb-1">
                    <span class="text-sm font-bold text-gray-900">{{ tool.tool_name }}</span>
                    <span v-if="tool.usage_count > 0" class="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium bg-blue-100 text-blue-700" title="被智能体引用次数">
                      <LinkIcon class="w-3 h-3 mr-0.5" />{{ tool.usage_count }}
                    </span>
                    <span v-if="!isSelectedServerEnabled" class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-50 text-amber-600 border border-amber-100 uppercase tracking-tighter">服务已禁用</span>
                    <span v-else-if="tool.is_available === false" class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-50 text-amber-600 border border-amber-100 uppercase tracking-tighter">远端已删除</span>
                    <span v-else-if="tool.is_published" class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-green-50 text-green-600 border border-green-100 uppercase tracking-tighter">已发布</span>
                    <span v-else class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-gray-100 text-gray-400 border border-gray-200 uppercase tracking-tighter">待发布</span>
                  </div>
                  <p class="text-xs text-gray-500 line-clamp-2 leading-relaxed italic">
                    {{ tool.tool_description || '暂无描述' }}
                  </p>
                  <div class="mt-2 flex flex-wrap gap-1" v-if="tool.parameter_schema">
                    <code class="text-[9px] bg-white px-1 border rounded text-gray-400" v-for="(_, p) in JSON.parse(tool.parameter_schema).properties" :key="p">{{ p }}</code>
                  </div>
                </div>
              </div>
              <div v-if="canSave" class="flex flex-col items-end space-y-2">
                <button 
                  @click.stop="openTester(tool)"
                  :disabled="!canManageTool(tool)"
                  class="flex items-center text-[11px] font-bold transition-colors px-3 py-1.5 rounded-md border shadow-sm bg-white text-indigo-600 hover:bg-indigo-50 border-indigo-100 opacity-0 group-hover:opacity-100 disabled:cursor-not-allowed disabled:opacity-40"
                  title="在线测试"
                >
                  <BeakerIcon class="w-3.5 h-3.5 mr-1.5" />
                  测试
                </button>
                <button 
                  @click.stop="togglePublish(tool)"
                  :disabled="!canManageTool(tool)"
                  class="flex items-center text-[11px] font-bold transition-colors px-3 py-1.5 rounded-md border shadow-sm opacity-0 group-hover:opacity-100 disabled:cursor-not-allowed disabled:opacity-40"
                  :class="tool.is_published ? 'bg-white text-gray-600 hover:text-red-600' : 'bg-primary text-white hover:bg-primary-dark'"
                >
                  <component :is="tool.is_published ? EyeSlashIcon : EyeIcon" class="w-3.5 h-3.5 mr-1.5" />
                  {{ tool.is_published ? '下线' : '发布' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- Tool Tester Drawer -->
    <McpToolTester 
      v-if="toolToTest"
      :tool="toolToTest" 
      :is-open="showTester" 
      @close="showTester = false" 
    />

    <!-- Add Server Modal (Connection Wizard) -->
    <div v-if="showAddModal" class="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-gray-900/50 backdrop-blur-sm">
      <div class="bg-white rounded-xl shadow-2xl w-full max-w-lg overflow-hidden animate-fade-in-up">
        <!-- Wizard Header -->
        <div class="p-6 border-b border-gray-100 bg-gray-50/50">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-bold text-gray-900">
              {{ wizardStep === 1 ? (isEditing ? '编辑配置' : '第一步：建立连接') : '第二步：确认工具并命名' }}
            </h3>
            <div class="flex space-x-1" v-if="!isEditing">
              <div class="w-2 h-2 rounded-full" :class="wizardStep === 1 ? 'bg-primary' : 'bg-gray-200'"></div>
              <div class="w-2 h-2 rounded-full" :class="wizardStep === 2 ? 'bg-primary' : 'bg-gray-200'"></div>
            </div>
          </div>
          <p class="text-xs text-gray-500">
            {{ wizardStep === 1 ? '输入外部 MCP SSE 服务端地址，系统将尝试探测其支持的工具。' : `探测成功！共发现 ${discoveredTools.length} 个工具。请检查列表并为该服务命名。` }}
          </p>
        </div>

        <!-- Wizard Step 1: Input -->
        <div v-if="wizardStep === 1" class="p-6 space-y-5">
          <div>
            <label class="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1.5 flex items-center">
              <LinkIcon class="w-3 h-3 mr-1" /> SSE 握手地址
            </label>
            <input v-model="newServer.sse_url" placeholder="https://..." class="w-full px-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-primary outline-none font-mono" />
            <p class="text-[10px] text-gray-400 mt-1">支持标准的 MCP SSE URL，例如来自 mcpmarket.cn 的代理地址。</p>
          </div>
          
          <!-- Dynamic Headers Editor -->
          <div>
            <div class="flex justify-between items-center mb-2">
              <label class="block text-xs font-bold text-gray-700 uppercase tracking-wider">身份认证 (可选)</label>
              <button @click="toggleHeaderMode" class="text-[10px] text-primary font-bold flex items-center hover:underline">
                <component :is="headerMode === 'simple' ? CodeBracketIcon : ListBulletIcon" class="w-3 h-3 mr-1" />
                切换到{{ headerMode === 'simple' ? '高级 JSON' : '可视化列表' }}
              </button>
            </div>

            <div v-if="headerMode === 'simple'" class="space-y-3">
              <p class="text-[10px] text-gray-400 leading-relaxed">
                如果服务需要令牌或 API Key，请添加下方项。
                <span class="text-primary cursor-pointer hover:underline" @click="headerPairs[0] = {key: 'Authorization', value: 'Bearer '}">[常用推荐：Authorization]</span>
              </p>
              
              <div class="space-y-2 bg-gray-50 p-3 rounded-lg border border-gray-100 max-h-[150px] overflow-y-auto custom-scrollbar">
                <div v-for="(pair, index) in headerPairs" :key="index" class="flex gap-2">
                  <div class="flex-1">
                    <input 
                      v-model="pair.key" 
                      placeholder="名称 (如 Authorization)" 
                      class="w-full px-3 py-1.5 text-xs border rounded focus:ring-1 focus:ring-primary outline-none" 
                    />
                  </div>
                  <div class="flex-1">
                    <input 
                      v-model="pair.value" 
                      :placeholder="pair.key === 'Authorization' ? 'Bearer sk-...' : '内容 (Value)'" 
                      class="w-full px-3 py-1.5 text-xs border rounded focus:ring-1 focus:ring-primary outline-none" 
                    />
                  </div>
                  <button @click="removeHeaderPair(index)" class="p-1.5 text-gray-400 hover:text-red-500">
                    <TrashIcon class="w-4 h-4" />
                  </button>
                </div>
                <button @click="addHeaderPair" class="mt-2 text-[10px] font-bold text-primary flex items-center hover:underline">
                  <PlusIcon class="w-3 h-3 mr-1" /> 继续添加
                </button>
              </div>
            </div>
            <div v-else>
              <textarea v-model="newServer.auth_headers" rows="4" class="w-full px-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-primary outline-none font-mono bg-gray-900 text-green-400" placeholder='{}'></textarea>
            </div>
          </div>
        </div>

        <!-- Wizard Step 2: Preview -->
        <div v-else class="p-6 space-y-5">
          <div>
            <label class="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1.5">服务显示名称</label>
            <input v-model="newServer.server_name" placeholder="起个好记的名字" class="w-full px-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-primary outline-none" />
          </div>
          
          <div>
            <label class="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">发现的工具预览</label>
            <div class="bg-gray-50 rounded-lg border border-gray-100 max-h-[250px] overflow-y-auto divide-y divide-gray-200 custom-scrollbar">
              <div v-for="tool in discoveredTools" :key="tool.name" class="p-3">
                <div class="text-xs font-bold text-gray-800">{{ tool.name }}</div>
                <div class="text-[10px] text-gray-500 line-clamp-1 italic">{{ tool.description || '无描述' }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Wizard Footer -->
        <div class="p-6 bg-gray-50 flex justify-between items-center">
          <button @click="showAddModal = false" class="px-4 py-2 text-sm text-gray-500 hover:text-gray-700 font-medium">取消</button>
          
          <div class="flex space-x-3">
            <button v-if="wizardStep === 2" @click="wizardStep = 1" class="px-4 py-2 text-sm text-primary font-medium hover:underline">返回修改</button>
            
            <button 
              v-if="wizardStep === 1"
              @click="handleVerify" 
              :disabled="verifying"
              class="px-6 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-dark font-bold shadow-lg shadow-primary/20 transition-all disabled:opacity-50 flex items-center"
            >
              <ArrowPathIcon v-if="verifying" class="w-4 h-4 mr-2 animate-spin" />
              {{ verifying ? '正在尝试建立连接...' : '连接并发现工具' }}
            </button>
            
            <button 
              v-else
              @click="addServer" 
              class="px-6 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 font-bold shadow-lg shadow-green-600/20 transition-all active:scale-95"
            >
              {{ isEditing ? '保存修改' : '确认并完成添加' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation -->
    <ConfirmModal 
      v-if="showDeleteConfirm"
      title="删除 MCP 服务"
      :message="`确定要删除该服务及其缓存的所有工具吗？此操作不可恢复。\n${formatUsageImpact(deleteServerUsage, '删除')}`"
      type="danger"
      :loading="deleteLoading"
      @confirm="executeDeleteServer"
      @cancel="cancelDeleteServer"
    />

    <ConfirmModal
      v-if="showStatusConfirm"
      title="禁用 MCP 服务"
      :message="formatUsageImpact(statusConfirmUsage, '禁用')"
      type="warning"
      confirm-text="确认禁用"
      :loading="statusConfirmLoading"
      @confirm="executeStatusChange"
      @cancel="cancelStatusConfirm"
    />
  </div>
</template>

<style scoped>
.animate-fade-in-up { animation: fadeInUp 0.3s ease-out; }
@keyframes fadeInUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #e5e7eb; border-radius: 4px; }
</style>
