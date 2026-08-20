<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import axios from '../utils/axios'
import Toast from '../components/Toast.vue'
import { useBranding } from '../composables/useBranding'
import { renderMarkdown } from '../utils/markdown'
import { copyToClipboard } from '../utils/clipboard'

const { branding, loadBranding } = useBranding()

const userInfo = ref<any>({})
const userApiKey = ref('')
const loadingApiKey = ref(false)
const apiKeyRevealed = ref(false)
const newPassword = ref('')
const confirmPassword = ref('')
const loadingPassword = ref(false)

const apiKeyDisplay = computed(() => {
  if (!userApiKey.value) return '点击“查看”加载'
  if (!apiKeyRevealed.value) {
    return '•'.repeat(Math.min(28, Math.max(16, userApiKey.value.length)))
  }
  return userApiKey.value
})

const toast = ref({
  show: false,
  message: '',
  type: 'info' as 'success' | 'error' | 'warning' | 'info',
  key: 0
})

const showToast = (message: string, type: 'success' | 'error' | 'warning' | 'info' = 'info') => {
  toast.value = {
    show: true,
    message,
    type,
    key: toast.value.key + 1
  }
}

const closeToast = () => {
  toast.value.show = false
}

const fetchUserInfo = async () => {
    try {
        const response = await axios.get('/api/portal/auth/me')
        if (response.data && response.data.status === 'success') {
            userInfo.value = response.data.data
        }
    } catch (e) {
        console.error("Failed to fetch user info", e)
    }
}

const fetchApiKey = async () => {
  if (!userInfo.value.user_id) return
  
  loadingApiKey.value = true
  try {
    const response = await axios.get(`/api/portal/management/api-key/${userInfo.value.user_id}`)
    userApiKey.value = response.data.api_key
    apiKeyRevealed.value = true
  } catch (error: any) {
    showToast(error.response?.data?.detail || '获取 API Key 失败', 'error')
  } finally {
    loadingApiKey.value = false
  }
}

const hideApiKey = () => {
  apiKeyRevealed.value = false
}

const revealOrFetchApiKey = async () => {
  if (userApiKey.value) {
    apiKeyRevealed.value = true
    return
  }
  await fetchApiKey()
}

const copyApiKey = async () => {
  if (!userApiKey.value) return
  const success = await copyToClipboard(userApiKey.value)
  if (success) {
    showToast('API Key 已复制', 'success')
  } else {
    showToast('复制失败，请手动复制', 'error')
  }
}

const handlePasswordChange = async () => {
    if (!newPassword.value || newPassword.value.length < 6) {
        showToast('密码长度至少需要6位', 'warning')
        return
    }
    if (newPassword.value !== confirmPassword.value) {
        showToast('两次输入的密码不一致', 'warning')
        return
    }
    
    loadingPassword.value = true
    try {
        const response = await axios.put('/api/portal/auth/password', {
            password: newPassword.value
        })
        if (response.data && response.data.status === 'success') {
            showToast('密码修改成功', 'success')
            newPassword.value = ''
            confirmPassword.value = ''
        } else {
            showToast('修改失败', 'error')
        }
    } catch (e: any) {
        showToast(e.response?.data?.detail || '修改失败', 'error')
    } finally {
        loadingPassword.value = false
    }
}

const clearingBrowserData = ref(false)
const handleClearBrowserData = async () => {
    if (!confirm('确认清除您在平台上的【云端自动化浏览器】历史、登录状态和缓存吗？\n（此操作仅重置云端服务端浏览器，不会影响您本地电脑的浏览器）。')) return
    clearingBrowserData.value = true
    try {
        await axios.delete('/api/v1/browser/profiles/clear')
        showToast('云端自动化浏览器历史、登录态及文件缓存已彻底清除', 'success')
    } catch (e: any) {
        showToast(e.response?.data?.detail || '清除失败，请稍后重试', 'error')
    } finally {
        clearingBrowserData.value = false
    }
}

import { watch } from 'vue'
import PersonalTokenUsage from '../components/personal/PersonalTokenUsage.vue'
import PersonalMemoryPanel from '../components/personal/PersonalMemoryPanel.vue'
import NotificationConfigs from '../components/personal/NotificationConfigs.vue'
import DataPortalHome from './DataPortalHome.vue'
import SkillsManagement from './SkillsManagement.vue'
import McpManagement from './McpManagement.vue'
import TaskCenter from './TaskCenter.vue'
import { useRoute, useRouter } from 'vue-router'

type PersonalTab = 'info' | 'permissions' | 'memory' | 'tokens' | 'notifications' | 'data' | 'skills' | 'mcp' | 'tasks'
const route = useRoute()
const router = useRouter()
const personalTabs: PersonalTab[] = ['info', 'permissions', 'memory', 'tokens', 'notifications', 'data', 'skills', 'mcp', 'tasks']
const activeTab = ref<PersonalTab>(personalTabs.includes(route.query.tab as PersonalTab) ? route.query.tab as PersonalTab : 'info')
const skillsInitialId = computed(() => String(route.query.skill_id || '').trim())
const permissionsSubTab = ref<'list' | 'about'>('list')
const showAboutTab = computed(() => !!branding.value.contact_markdown?.trim())
const contactHtml = computed(() => renderMarkdown(branding.value.contact_markdown || ''))
const loadingPermissions = ref(false)
const permissions = ref<{
    roles?: string[],
    permissions?: {
        agents?: string[],
        datasets?: string[],
        apis?: string[],
        metadata?: string[],
        menus?: string[],
        elements?: string[]
    },
    details?: {
        agents?: Array<{ id: string, name: string, display_name?: string, description?: string }>,
        datasets?: Array<{ id: string, name: string, display_name?: string, description?: string }>,
        apis?: Array<{ id: string, name: string, display_name?: string, description?: string }>,
        metadata?: Array<{ id: string, name: string, display_name?: string, description?: string }>,
        menus?: Array<{ id: string, name: string, display_name?: string, description?: string }>,
        elements?: Array<{ id: string, name: string, display_name?: string, description?: string }>
    }
}>({})

const fetchPermissions = async () => {
    loadingPermissions.value = true
    try {
        const permRes = await axios.get('/api/portal/auth/permissions')
        permissions.value = permRes.data || {}
    } catch (e) {
        console.error("Failed to fetch permissions", e)
        showToast('获取权限列表失败', 'error')
    } finally {
        loadingPermissions.value = false
    }
}

watch(activeTab, (val) => {
    const nextQuery: Record<string, any> = { ...route.query }
    if (val === 'info') {
        delete nextQuery.tab
    } else {
        nextQuery.tab = val
    }
    // 离开「我的技能」时清掉深链 skill_id，避免再切回来又自动弹出编辑抽屉
    if (val !== 'skills') {
        delete nextQuery.skill_id
    }
    router.replace({ query: nextQuery })
    if (val === 'permissions' && !permissions.value.details) {
        fetchPermissions()
    }
})

const clearSkillsDeepLink = () => {
    if (!route.query.skill_id) return
    const nextQuery: Record<string, any> = { ...route.query }
    delete nextQuery.skill_id
    router.replace({ query: nextQuery })
}
watch(() => route.query.tab, (value) => {
    activeTab.value = personalTabs.includes(value as PersonalTab) ? value as PersonalTab : 'info'
})

onMounted(() => {
    fetchUserInfo()
    loadBranding()
})
</script>

<template>
<div class="min-h-full bg-white">
    <div>
        <h2 class="px-4 pt-5 text-lg font-bold text-gray-900 sm:px-6 sm:pt-6 sm:text-xl">个人中心</h2>
        
        <!-- Tabs -->
        <div class="mt-4 border-b border-gray-200 px-4 sm:mt-6 sm:px-6">
            <nav class="-mb-px flex space-x-4 sm:space-x-8 overflow-x-auto">
                <button
                    @click="activeTab = 'info'"
                    :class="[
                        activeTab === 'info'
                            ? 'border-blue-500 text-blue-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
                        'whitespace-nowrap py-3 sm:py-4 px-1 border-b-2 font-medium text-xs sm:text-sm transition-colors'
                    ]"
                >
                    基本信息
                </button>
                <button 
                    @click="activeTab = 'permissions'"
                    :class="[
                        activeTab === 'permissions'
                            ? 'border-blue-500 text-blue-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
                        'whitespace-nowrap py-3 sm:py-4 px-1 border-b-2 font-medium text-xs sm:text-sm transition-colors'
                    ]"
                >
                    我的权限
                </button>
                <button 
                    @click="activeTab = 'memory'"
                    :class="[
                        activeTab === 'memory'
                            ? 'border-blue-500 text-blue-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
                        'whitespace-nowrap py-3 sm:py-4 px-1 border-b-2 font-medium text-xs sm:text-sm transition-colors'
                    ]"
                >
                    我的记忆
                </button>
                <button 
                    @click="activeTab = 'tokens'"
                    :class="[
                        activeTab === 'tokens'
                            ? 'border-blue-500 text-blue-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
                        'whitespace-nowrap py-3 sm:py-4 px-1 border-b-2 font-medium text-xs sm:text-sm transition-colors'
                    ]"
                >
                    我的 Token 消耗
                </button>
                <button
                    @click="activeTab = 'data'"
                    :class="[
                        activeTab === 'data'
                            ? 'border-blue-500 text-blue-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
                        'whitespace-nowrap py-3 sm:py-4 px-1 border-b-2 font-medium text-xs sm:text-sm transition-colors'
                    ]"
                >
                    我的数据门户
                </button>
                <button
                    @click="activeTab = 'skills'"
                    :class="[
                        activeTab === 'skills'
                            ? 'border-blue-500 text-blue-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
                        'whitespace-nowrap py-3 sm:py-4 px-1 border-b-2 font-medium text-xs sm:text-sm transition-colors'
                    ]"
                >
                    我的技能
                </button>
                <button
                    @click="activeTab = 'mcp'"
                    :class="[
                        activeTab === 'mcp'
                            ? 'border-blue-500 text-blue-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
                        'whitespace-nowrap py-3 sm:py-4 px-1 border-b-2 font-medium text-xs sm:text-sm transition-colors'
                    ]"
                >
                    我的 MCP
                </button>
                <button
                    @click="activeTab = 'tasks'"
                    :class="[
                        activeTab === 'tasks'
                            ? 'border-blue-500 text-blue-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
                        'whitespace-nowrap py-3 sm:py-4 px-1 border-b-2 font-medium text-xs sm:text-sm transition-colors'
                    ]"
                >
                    我的任务
                </button>
                <button 
                    @click="activeTab = 'notifications'"
                    :class="[
                        activeTab === 'notifications'
                            ? 'border-blue-500 text-blue-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
                        'whitespace-nowrap py-3 sm:py-4 px-1 border-b-2 font-medium text-xs sm:text-sm transition-colors'
                    ]"
                >
                    消息通知
                </button>
            </nav>
        </div>

        <div :class="(activeTab === 'data' || activeTab === 'skills' || activeTab === 'mcp' || activeTab === 'tasks') ? 'pt-4 sm:pt-5' : 'px-4 pt-4 pb-4 sm:px-6 sm:pt-5 sm:pb-6'">
        <!-- Info Tab -->
        <div v-if="activeTab === 'info'">
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8">
                <!-- Basic Info -->
                <div class="space-y-4 sm:space-y-6">
                    <h3 class="text-md sm:text-lg font-medium text-gray-900 border-b pb-2">账号信息</h3>
                    
                    <div class="flex items-center">
                        <div class="h-12 w-12 sm:h-16 sm:w-16 rounded-full bg-primary flex items-center justify-center text-xl sm:text-2xl font-bold text-white uppercase">
                            {{ (userInfo.real_name || userInfo.user_name || 'U').substring(0, 2) }}
                        </div>
                        <div class="ml-3 sm:ml-4">
                            <p class="text-md sm:text-lg font-medium">{{ userInfo.real_name || userInfo.user_name }}</p>
                            <div class="flex flex-wrap items-center gap-2 mt-0.5 sm:mt-1">
                                <span class="text-xs sm:text-sm text-gray-500 font-mono">@{{ userInfo.user_name }}</span>
                                <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] sm:text-xs font-medium" 
                                    :class="userInfo.role === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'"
                                >
                                    {{ userInfo.role === 'admin' ? '管理员' : '普通用户' }}
                                </span>
                            </div>
                        </div>
                    </div>

                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs sm:text-sm">
                       <div>
                           <label class="block text-gray-400 font-medium uppercase text-[10px] mb-0.5">用户ID</label>
                           <p class="font-mono text-gray-700">{{ userInfo.user_id }}</p>
                       </div>
                       <div>
                           <label class="block text-gray-400 font-medium uppercase text-[10px] mb-0.5">创建时间</label>
                           <p class="text-gray-700">{{ userInfo.created_at || '-' }}</p>
                       </div>
                       <div class="sm:col-span-2">
                           <label class="block text-gray-400 font-medium uppercase text-[10px] mb-0.5">备注</label>
                           <p class="text-gray-700 bg-gray-50 p-2 rounded border border-gray-100">{{ userInfo.remark || '暂无备注' }}</p>
                       </div>
                    </div>

                    <div>
                        <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">API Key</label>
                        <div class="flex items-center space-x-2">
                            <input
                                type="text"
                                :value="apiKeyDisplay"
                                readonly
                                class="flex-1 px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-xs sm:text-sm font-mono truncate"
                                :class="apiKeyRevealed ? 'tracking-normal' : 'tracking-widest'"
                            />
                            <button
                                v-if="!apiKeyRevealed"
                                type="button"
                                @click="revealOrFetchApiKey"
                                :disabled="loadingApiKey"
                                class="px-3 sm:px-4 py-2 bg-primary text-white text-xs sm:text-sm font-bold rounded-md hover:bg-primary-dark transition-all disabled:opacity-50 flex-shrink-0"
                            >
                                {{ loadingApiKey ? '...' : '查看' }}
                            </button>
                            <template v-else>
                                <button
                                    type="button"
                                    @click="copyApiKey"
                                    class="px-3 sm:px-4 py-2 bg-green-600 text-white text-xs sm:text-sm font-bold rounded-md hover:bg-green-700 transition-all flex-shrink-0"
                                >
                                    复制
                                </button>
                                <button
                                    type="button"
                                    @click="hideApiKey"
                                    class="px-3 sm:px-4 py-2 border border-gray-300 bg-white text-gray-600 text-xs sm:text-sm font-medium rounded-md hover:bg-gray-50 transition-all flex-shrink-0"
                                >
                                    隐藏
                                </button>
                            </template>
                        </div>
                    </div>
                </div>

                <!-- Security Settings -->
                <div class="space-y-4 sm:space-y-6">
                    <h3 class="text-md sm:text-lg font-medium text-gray-900 border-b pb-2">安全设置</h3>
                    
                    <form @submit.prevent="handlePasswordChange" class="space-y-4">
                        <div>
                            <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1.5">新密码</label>
                            <input 
                                v-model="newPassword"
                                type="password" 
                                class="mt-1 block w-full px-3 py-2.5 bg-gray-50 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none text-sm transition-all"
                                placeholder="输入新密码 (至少6位)"
                            />
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1.5">确认新密码</label>
                            <input 
                                v-model="confirmPassword"
                                type="password" 
                                class="mt-1 block w-full px-3 py-2.5 bg-gray-50 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none text-sm transition-all"
                                placeholder="再次输入新密码"
                            />
                        </div>

                        <div class="pt-2">
                            <button 
                                type="submit" 
                                :disabled="loadingPassword || !newPassword"
                                class="w-full flex justify-center py-2.5 px-4 border border-transparent rounded-lg shadow-md text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 active:scale-[0.98] transition-all disabled:opacity-50"
                            >
                                {{ loadingPassword ? '提交中...' : '确认修改密码' }}
                            </button>
                        </div>
                        
                        <div class="bg-amber-50 p-3 sm:p-4 rounded-lg border border-amber-100">
                            <div class="flex">
                                <div class="flex-shrink-0">
                                    <svg class="h-5 w-5 text-amber-400" viewBox="0 0 20 20" fill="currentColor">
                                        <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
                                    </svg>
                                </div>
                                <div class="ml-3">
                                    <h3 class="text-xs sm:text-sm font-bold text-amber-800">安全提醒</h3>
                                    <div class="mt-1 text-[11px] sm:text-xs text-amber-700 leading-relaxed">
                                        <p>修改密码后需要重新登录。此操作不会使您现有的 API Key 失效。</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </form>
                </div>

                <!-- Cloud Browser Cache & Reset -->
                <div class="space-y-4 sm:space-y-6">
                    <h3 class="text-md sm:text-lg font-medium text-gray-900 border-b pb-2">云端浏览器缓存</h3>
                    <div class="space-y-4">
                        <p class="text-xs text-gray-500 leading-relaxed">
                            如果在智能体自动化任务中登录过外部网站，可在此一键重置您的<span class="font-semibold text-gray-700">云端服务端浏览器环境</span>，彻底擦除云端存储的 Cookie、登录状态、历史记录及本地文件缓存（不影响您本地电脑的 Chrome 浏览器数据）。
                        </p>
                        <div>
                            <button
                                type="button"
                                @click="handleClearBrowserData"
                                :disabled="clearingBrowserData"
                                class="w-full flex justify-center items-center gap-1.5 py-2.5 px-4 bg-red-50 border border-red-200 text-red-700 hover:bg-red-100 text-xs sm:text-sm font-bold rounded-lg shadow-sm transition-all disabled:opacity-50"
                            >
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                                {{ clearingBrowserData ? '正在清理中...' : '清除云端自动化浏览器缓存与登录态' }}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Permissions Tab -->
        <div v-else-if="activeTab === 'permissions'">
            <div v-if="loadingPermissions" class="flex justify-center py-10">
                <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
            
            <div v-else class="space-y-4 sm:space-y-6">
                <div v-if="showAboutTab" class="border-b border-gray-200">
                    <nav class="-mb-px flex space-x-6">
                        <button
                            @click="permissionsSubTab = 'list'"
                            class="whitespace-nowrap py-3 px-1 border-b-2 font-medium text-xs sm:text-sm transition-colors"
                            :class="permissionsSubTab === 'list' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
                        >
                            权限清单
                        </button>
                        <button
                            @click="permissionsSubTab = 'about'"
                            class="whitespace-nowrap py-3 px-1 border-b-2 font-medium text-xs sm:text-sm transition-colors"
                            :class="permissionsSubTab === 'about' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
                        >
                            关于
                        </button>
                    </nav>
                </div>

                <div v-if="permissionsSubTab === 'about' && showAboutTab" class="bg-gray-50 border border-gray-100 rounded-xl p-4 sm:p-6">
                    <div class="markdown-body prose prose-sm max-w-none text-gray-700 break-words" v-html="contactHtml"></div>
                </div>

                <template v-else>
                <!-- Helper Text -->
                <div class="bg-gray-50 p-3 sm:p-4 rounded-lg text-xs sm:text-sm text-gray-600 flex items-start gap-3 border border-gray-100">
                    <svg class="w-5 h-5 text-gray-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <div>
                        <p class="font-bold text-gray-900">权限清单</p>
                        <p class="mt-1">列出您当前拥有的所有系统资源访问权限。</p>
                        <p v-if="userInfo.role === 'admin'" class="mt-2 text-purple-600 font-bold">
                            ✨ 您是超级管理员，拥有全局最高权限。
                        </p>
                        <div v-if="permissions.roles && permissions.roles.length" class="mt-2 flex flex-wrap gap-2 items-center">
                            <span class="text-gray-500">角色标识:</span>
                            <span v-for="role in permissions.roles" :key="role" class="px-2 py-0.5 bg-gray-200 text-gray-700 rounded text-[10px] font-mono font-bold">
                                {{ role }}
                            </span>
                        </div>
                    </div>
                </div>

                <!-- Section Grid (Mobile Friendly) -->
                <div v-if="userInfo.role !== 'admin'" class="grid grid-cols-1 gap-4">
                    <!-- Agents -->
                    <div class="border border-gray-200 rounded-lg overflow-hidden bg-white shadow-sm">
                        <div class="bg-gray-50 px-4 py-2.5 border-b border-gray-200 flex items-center justify-between">
                            <h3 class="text-xs sm:text-sm font-bold text-gray-900 flex items-center gap-2">
                                <span class="p-1 bg-blue-100 text-blue-600 rounded">
                                    <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
                                </span>
                                智能体 (Agents)
                            </h3>
                            <span class="text-[10px] font-bold text-gray-400 bg-white px-2 py-0.5 rounded-full border">
                                {{ permissions.details?.agents?.length || 0 }}
                            </span>
                        </div>
                        <div class="p-3">
                            <div v-if="!permissions.details?.agents?.length" class="text-center text-gray-400 py-4 text-xs italic">（暂无授权）</div>
                            <div v-else class="grid grid-cols-1 xs:grid-cols-2 lg:grid-cols-3 gap-2">
                                <div v-for="item in permissions.details.agents" :key="item.id" class="flex flex-col p-2.5 rounded-lg border border-gray-100 bg-white hover:border-blue-200 transition-all shadow-sm">
                                    <span class="font-bold text-gray-800 truncate text-xs">{{ item.display_name || item.name }}</span>
                                    <span class="text-[9px] text-gray-400 font-mono truncate mt-0.5">{{ item.name }}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Knowledge bases (RAGFlow datasets) -->
                    <div class="border border-gray-200 rounded-lg overflow-hidden bg-white shadow-sm">
                        <div class="bg-gray-50 px-4 py-2.5 border-b border-gray-200 flex items-center justify-between">
                            <h3 class="text-xs sm:text-sm font-bold text-gray-900 flex items-center gap-2">
                                <span class="p-1 bg-green-100 text-green-600 rounded">
                                    <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" /></svg>
                                </span>
                                知识库
                            </h3>
                            <span class="text-[10px] font-bold text-gray-400 bg-white px-2 py-0.5 rounded-full border">
                                {{ permissions.details?.datasets?.length || 0 }}
                            </span>
                        </div>
                        <div class="p-3">
                            <div v-if="!permissions.details?.datasets?.length" class="text-center text-gray-400 py-4 text-xs italic">（暂无授权）</div>
                            <div v-else class="grid grid-cols-1 xs:grid-cols-2 lg:grid-cols-3 gap-2">
                                <div v-for="item in permissions.details.datasets" :key="item.id" class="flex flex-col p-2.5 rounded-lg border border-gray-100 bg-white hover:border-green-200 transition-all shadow-sm">
                                    <span class="font-bold text-gray-800 truncate text-xs">{{ item.display_name || item.name }}</span>
                                    <span class="text-[9px] text-gray-400 font-mono truncate mt-0.5">{{ item.id }}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- ChatBI metadata datasets -->
                    <div class="border border-gray-200 rounded-lg overflow-hidden bg-white shadow-sm">
                        <div class="bg-gray-50 px-4 py-2.5 border-b border-gray-200 flex items-center justify-between">
                            <h3 class="text-xs sm:text-sm font-bold text-gray-900 flex items-center gap-2">
                                <span class="p-1 bg-orange-100 text-orange-600 rounded">
                                    <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" /></svg>
                                </span>
                                数据集
                            </h3>
                            <span class="text-[10px] font-bold text-gray-400 bg-white px-2 py-0.5 rounded-full border">
                                {{ permissions.details?.metadata?.length || 0 }}
                            </span>
                        </div>
                        <div class="p-3">
                            <div v-if="!permissions.details?.metadata?.length" class="text-center text-gray-400 py-4 text-xs italic">（暂无授权）</div>
                            <div v-else class="grid grid-cols-1 xs:grid-cols-2 lg:grid-cols-3 gap-2">
                                <div v-for="item in permissions.details.metadata" :key="item.id" class="flex flex-col p-2.5 rounded-lg border border-gray-100 bg-white hover:border-orange-200 transition-all shadow-sm">
                                    <span class="font-bold text-gray-800 truncate text-xs">{{ item.display_name || item.name }}</span>
                                    <span class="text-[9px] text-gray-400 font-mono truncate mt-0.5">ID: {{ item.id }}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Other resources (Menus, Elements) -->
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                         <!-- Menus -->
                        <div class="border border-gray-200 rounded-lg overflow-hidden bg-white shadow-sm">
                            <div class="bg-gray-50 px-4 py-2.5 border-b border-gray-200 flex items-center justify-between">
                                <h3 class="text-xs font-bold text-gray-900 flex items-center gap-2">界面菜单</h3>
                                <span class="text-[10px] font-bold text-gray-400">{{ permissions.details?.menus?.length || 0 }}</span>
                            </div>
                            <div class="p-3 flex flex-wrap gap-1.5">
                                <span v-for="item in permissions.details?.menus" :key="item.id" class="px-2 py-1 bg-indigo-50 text-indigo-700 rounded text-[10px] font-bold border border-indigo-100">{{ item.display_name }}</span>
                            </div>
                        </div>
                         <!-- Elements -->
                        <div class="border border-gray-200 rounded-lg overflow-hidden bg-white shadow-sm">
                            <div class="bg-gray-50 px-4 py-2.5 border-b border-gray-200 flex items-center justify-between">
                                <h3 class="text-xs font-bold text-gray-900 flex items-center gap-2">功能点</h3>
                                <span class="text-[10px] font-bold text-gray-400">{{ permissions.details?.elements?.length || 0 }}</span>
                            </div>
                            <div class="p-3 flex flex-wrap gap-1.5">
                                <span v-for="item in permissions.details?.elements" :key="item.id" class="px-2 py-1 bg-rose-50 text-rose-700 rounded text-[10px] font-bold border border-rose-100">{{ item.display_name }}</span>
                            </div>
                        </div>
                    </div>
                </div>
                </template>
            </div>
        </div>

        <!-- Token Usage Tab -->
        <div v-else-if="activeTab === 'tokens'">
            <PersonalTokenUsage />
        </div>

        <!-- Notifications Tab -->
        <div v-else-if="activeTab === 'notifications'">
            <NotificationConfigs @show-toast="showToast" />
        </div>

        <!-- My Data Tab -->
        <div v-else-if="activeTab === 'data'">
            <DataPortalHome embedded />
        </div>

        <div v-else-if="activeTab === 'skills'" class="px-4 pb-4 sm:px-6 sm:pb-6">
            <SkillsManagement
                personal-only
                :initial-skill-id="skillsInitialId"
                @drawer-closed="clearSkillsDeepLink"
            />
        </div>

        <div v-else-if="activeTab === 'mcp'" class="px-3 pb-4 sm:px-6 sm:pb-6 min-h-[28rem]">
            <McpManagement personal-only />
        </div>

        <div v-else-if="activeTab === 'tasks'" class="px-4 pb-4 sm:px-6 sm:pb-6 min-h-[32rem]">
            <TaskCenter personal-only />
        </div>

        <!-- Memory：keep-alive + v-if，离开 Tab 不销毁，保留 memoryView/筛选状态 -->
        <div v-show="activeTab === 'memory'">
            <keep-alive>
                <PersonalMemoryPanel v-if="activeTab === 'memory'" />
            </keep-alive>
        </div>

        </div>

    </div>

    <Toast 
      v-if="toast.show" 
      :key="toast.key"
      :message="toast.message" 
      :type="toast.type" 
      @close="closeToast" 
    />
</div>
</template>
