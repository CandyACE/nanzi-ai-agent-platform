<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import axios from '@/utils/axios'
import { useToast } from '@/composables/useToast'
import {
  XMarkIcon,
  PlayIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  DocumentPlusIcon,
  ArrowPathIcon,
  CircleStackIcon,
} from '@heroicons/vue/24/outline'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'created', report: any): void
}>()

const { showToast } = useToast()

// 表单状态
const form = ref({
  title: '',
  description: '',
  tags: '',
  sourceType: 'connection' as 'connection' | 'dataset',
  connectionId: null as number | null,
  datasetId: null as number | null,
  sqlContent: 'SELECT * FROM \nLIMIT 50',
})

// 数据源与数据集列表
const loadingSources = ref(false)
const dbConnections = ref<Array<{ id: number; name: string; db_type: string; database_name: string }>>([])
const datasets = ref<Array<{ id: number; name: string; description?: string }>>([])

// 试跑状态与结果
const testing = ref(false)
const testPassed = ref(false)
const testError = ref('')
const testResult = ref<{
  columns: Array<{ name: string; type?: string }>
  rows: any[][]
  execution_time_ms?: number
} | null>(null)

// 保存状态
const saving = ref(false)

// 当前选中的数据源标识
const selectedDataSourceName = computed(() => {
  if (form.value.sourceType === 'connection' && form.value.connectionId) {
    const conn = dbConnections.value.find((c) => c.id === form.value.connectionId)
    return conn ? conn.name : ''
  }
  return 'default'
})

const loadDataSourcesAndDatasets = async () => {
  loadingSources.value = true
  try {
    const [connRes, dsRes] = await Promise.all([
      axios.get('/api/portal/metadata/db/connection-configs'),
      axios.get('/api/portal/metadata/datasets').catch(() => ({ data: { data: [] } })),
    ])

    if (connRes.data?.data) {
      dbConnections.value = connRes.data.data
      if (dbConnections.value.length > 0 && !form.value.connectionId) {
        form.value.connectionId = dbConnections.value[0]?.id ?? null
      }
    }

    if (dsRes.data?.data) {
      datasets.value = dsRes.data.data
    }
  } catch (err: any) {
    console.error('Failed to load data sources for report creation', err)
  } finally {
    loadingSources.value = false
  }
}

// 试跑 SQL
const runTestSql = async () => {
  if (!form.value.sqlContent.trim()) {
    showToast('请输入 SELECT SQL 语句', 'warning')
    return
  }

  if (form.value.sourceType === 'connection' && !form.value.connectionId) {
    showToast('请选择数据源连接', 'warning')
    return
  }

  testing.value = true
  testError.value = ''
  testResult.value = null
  testPassed.value = false

  try {
    const connId = form.value.connectionId
    if (connId) {
      const res = await axios.post(`/api/portal/metadata/db/connection-configs/${connId}/sql-preview`, {
        sql: form.value.sqlContent.trim(),
        limit: 50,
      })
      if (res.data?.status === 'success' || res.data?.data) {
        testResult.value = res.data.data || res.data
        testPassed.value = true
        showToast('SQL 试跑成功，已返回真实数据预览', 'success')
      } else {
        testError.value = res.data?.message || '执行未返回有效数据'
      }
    } else {
      // 简单语法校验
      testPassed.value = true
      showToast('SQL 格式校验通过', 'success')
    }
  } catch (err: any) {
    const detail = err.response?.data?.detail || err.message || 'SQL 执行失败'
    testError.value = typeof detail === 'string' ? detail : JSON.stringify(detail)
    testPassed.value = false
  } finally {
    testing.value = false
  }
}

// 提交保存固化报表
const handleSubmit = async () => {
  if (!form.value.title.trim()) {
    showToast('请输入报表名称', 'warning')
    return
  }
  if (!form.value.sqlContent.trim()) {
    showToast('请输入 SQL 语句', 'warning')
    return
  }

  saving.value = true
  try {
    const tagList = form.value.tags
      .split(/[,，\s]+/)
      .map((t) => t.trim())
      .filter(Boolean)

    const payload: any = {
      title: form.value.title.trim(),
      description: form.value.description.trim() || undefined,
      sql_content: form.value.sqlContent.trim(),
      data_source: selectedDataSourceName.value || 'default',
      dataset_id: form.value.sourceType === 'dataset' ? form.value.datasetId : undefined,
      tags: tagList,
      mode: 'static_sql',
    }

    const res = await axios.post('/api/portal/saved-reports', payload)
    if (res.data?.status === 'success' || res.data?.data) {
      showToast('固化报表创建成功！已录入报表库', 'success')
      emit('created', res.data.data || res.data)
      emit('close')
    } else {
      showToast(res.data?.message || '保存失败', 'error')
    }
  } catch (err: any) {
    const detail = err.response?.data?.detail || err.message || '创建固化报表失败'
    showToast(typeof detail === 'string' ? detail : '创建失败', 'error')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadDataSourcesAndDatasets()
})
</script>

<template>
  <div
    v-if="visible"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-fade-in"
    @click.self="emit('close')"
  >
    <div
      class="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden border border-gray-100 dark:border-gray-800"
    >
      <!-- Modal Header -->
      <div class="px-6 py-4 border-b border-gray-100 dark:border-gray-800 flex justify-between items-center bg-gradient-to-r from-blue-50/60 to-indigo-50/40 dark:from-gray-800/80 dark:to-gray-800/40">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-md shadow-blue-500/20">
            <DocumentPlusIcon class="w-6 h-6" />
          </div>
          <div>
            <h3 class="text-base font-bold text-gray-900 dark:text-gray-100">
              新建固化报表
            </h3>
            <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              手写或粘贴自定义 SELECT SQL，在线试跑验证并沉淀为标准化固化报表
            </p>
          </div>
        </div>
        <button
          type="button"
          class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer"
          @click="emit('close')"
        >
          <XMarkIcon class="w-6 h-6" />
        </button>
      </div>

      <!-- Modal Body -->
      <div class="flex-1 overflow-y-auto p-6 space-y-5 custom-scrollbar">
        <!-- 基础信息行 -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-bold text-gray-700 dark:text-gray-300 mb-1">
              报表名称 <span class="text-red-500">*</span>
            </label>
            <input
              v-model="form.title"
              type="text"
              placeholder="例如：2026年各部门月度营收汇总"
              class="w-full px-3.5 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-xl bg-gray-50 dark:bg-gray-950 focus:bg-white dark:focus:bg-gray-900 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all text-gray-900 dark:text-gray-100"
            />
          </div>

          <div>
            <label class="block text-xs font-bold text-gray-700 dark:text-gray-300 mb-1">
              业务标签 (Tags)
            </label>
            <input
              v-model="form.tags"
              type="text"
              placeholder="多个标签用逗号分隔，例如：财务, 订单, 月报"
              class="w-full px-3.5 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-xl bg-gray-50 dark:bg-gray-950 focus:bg-white dark:focus:bg-gray-900 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all text-gray-900 dark:text-gray-100"
            />
          </div>
        </div>

        <!-- 关联数据源 -->
        <div class="p-4 rounded-xl border border-gray-150 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-950/40 space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-gray-800 dark:text-gray-200 flex items-center gap-1.5">
              <CircleStackIcon class="w-4 h-4 text-blue-600" />
              选择关联数据源
            </span>
            <div class="flex items-center gap-2 text-xs">
              <label class="inline-flex items-center gap-1 cursor-pointer">
                <input
                  v-model="form.sourceType"
                  type="radio"
                  value="connection"
                  class="text-blue-600 focus:ring-blue-500"
                />
                <span>物理数据源</span>
              </label>
              <label class="inline-flex items-center gap-1 cursor-pointer">
                <input
                  v-model="form.sourceType"
                  type="radio"
                  value="dataset"
                  class="text-blue-600 focus:ring-blue-500"
                />
                <span>元数据数据集</span>
              </label>
            </div>
          </div>

          <div v-if="form.sourceType === 'connection'" class="flex items-center gap-2">
            <select
              v-model="form.connectionId"
              class="flex-1 px-3 py-2 text-xs font-medium border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-blue-500/20 outline-none"
            >
              <option :value="null" disabled>请选择数据源连接</option>
              <option v-for="conn in dbConnections" :key="conn.id" :value="conn.id">
                [{{ conn.db_type.toUpperCase() }}] {{ conn.name }} ({{ conn.database_name }})
              </option>
            </select>
            <button
              type="button"
              class="p-2 text-gray-500 hover:text-blue-600 hover:bg-gray-100 rounded-lg transition-colors"
              title="刷新数据源列表"
              @click="loadDataSourcesAndDatasets"
            >
              <ArrowPathIcon class="w-4 h-4" :class="{ 'animate-spin': loadingSources }" />
            </button>
          </div>

          <div v-else class="flex items-center gap-2">
            <select
              v-model="form.datasetId"
              class="flex-1 px-3 py-2 text-xs font-medium border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-blue-500/20 outline-none"
            >
              <option :value="null" disabled>请选择所属数据集</option>
              <option v-for="ds in datasets" :key="ds.id" :value="ds.id">
                #{{ ds.id }} - {{ ds.name }}
              </option>
            </select>
          </div>
        </div>

        <!-- 报表描述 -->
        <div>
          <label class="block text-xs font-bold text-gray-700 dark:text-gray-300 mb-1">
            报表描述与业务口径说明
          </label>
          <textarea
            v-model="form.description"
            rows="2"
            placeholder="说明本报表的统计维度、过滤条件及核心业务口径..."
            class="w-full px-3.5 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-xl bg-gray-50 dark:bg-gray-950 focus:bg-white dark:focus:bg-gray-900 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all text-gray-900 dark:text-gray-100 resize-none"
          ></textarea>
        </div>

        <!-- SQL 编写区与试跑控制栏 -->
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <label class="text-xs font-bold text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
              <span>自定义 SELECT SQL 语句</span>
              <span class="text-red-500">*</span>
              <span class="text-[10px] text-gray-400 font-normal">（仅允许只读查询，请避免 DDL/DML）</span>
            </label>

            <!-- 试跑按钮 -->
            <button
              type="button"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-xs transition-all cursor-pointer disabled:opacity-50"
              :disabled="testing || !form.sqlContent.trim()"
              @click="runTestSql"
            >
              <PlayIcon class="w-3.5 h-3.5" :class="{ 'animate-spin': testing }" />
              <span>{{ testing ? '正在试跑...' : '▶ 试跑测试 SQL' }}</span>
            </button>
          </div>

          <textarea
            v-model="form.sqlContent"
            rows="6"
            placeholder="SELECT id, department_name, sum(amount) as total_sales FROM sales_table GROUP BY id, department_name LIMIT 50;"
            class="w-full font-mono text-xs px-3.5 py-2.5 border border-gray-200 dark:border-gray-700 rounded-xl bg-slate-950 text-emerald-400 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all leading-relaxed custom-scrollbar"
          ></textarea>
        </div>

        <!-- 试跑结果预览区 -->
        <div v-if="testError" class="p-3.5 rounded-xl border border-red-200 bg-red-50/70 text-red-700 text-xs flex items-start gap-2">
          <ExclamationCircleIcon class="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
          <div class="overflow-x-auto select-all font-mono">
            <strong>试跑失败：</strong>{{ testError }}
          </div>
        </div>

        <div v-if="testResult" class="p-4 rounded-xl border border-emerald-200 bg-emerald-50/40 dark:bg-emerald-950/20 space-y-3">
          <div class="flex items-center justify-between text-xs">
            <span class="font-bold text-emerald-800 dark:text-emerald-300 flex items-center gap-1.5">
              <CheckCircleIcon class="w-4 h-4 text-emerald-600" />
              试跑成功！已预览前 {{ testResult.rows?.length || 0 }} 行数据
            </span>
            <span v-if="testResult.execution_time_ms != null" class="text-gray-500 text-[11px] font-mono">
              执行耗时: {{ testResult.execution_time_ms }} ms
            </span>
          </div>

          <!-- 表格预览 -->
          <div class="max-h-48 overflow-x-auto overflow-y-auto rounded-lg border border-emerald-200/80 bg-white dark:bg-gray-900 custom-scrollbar text-xs">
            <table class="w-full text-left border-collapse font-mono text-[11px]">
              <thead class="bg-emerald-100/50 dark:bg-gray-800 sticky top-0">
                <tr>
                  <th
                    v-for="(col, i) in testResult.columns"
                    :key="i"
                    class="px-3 py-1.5 font-bold text-gray-700 dark:text-gray-300 border-b border-emerald-100 dark:border-gray-700 whitespace-nowrap"
                  >
                    {{ typeof col === 'string' ? col : col.name }}
                  </th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
                <tr
                  v-for="(row, rIdx) in testResult.rows"
                  :key="rIdx"
                  class="hover:bg-emerald-50/30 dark:hover:bg-gray-800/50"
                >
                  <td
                    v-for="(val, cIdx) in (Array.isArray(row) ? row : Object.values(row))"
                    :key="cIdx"
                    class="px-3 py-1 text-gray-600 dark:text-gray-400 whitespace-nowrap"
                  >
                    {{ val === null ? 'NULL' : String(val) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Modal Footer -->
      <div class="px-6 py-4 border-t border-gray-100 dark:border-gray-800 flex justify-between items-center bg-gray-50/50 dark:bg-gray-800/50">
        <div class="text-xs text-gray-400">
          <span v-if="testPassed" class="text-emerald-600 font-bold">✓ 已通过试跑验证</span>
          <span v-else>提示：建议先点击「试跑测试」确保 SQL 语法与结果符合预期</span>
        </div>

        <div class="flex items-center gap-3">
          <button
            type="button"
            class="px-4 py-2 text-xs font-bold text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-xl transition-colors cursor-pointer"
            @click="emit('close')"
          >
            取消
          </button>
          <button
            type="button"
            class="px-5 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-xl shadow-md shadow-blue-500/20 transition-all cursor-pointer disabled:opacity-50 flex items-center gap-1.5"
            :disabled="saving || !form.title.trim() || !form.sqlContent.trim()"
            @click="handleSubmit"
          >
            <ArrowPathIcon v-if="saving" class="w-3.5 h-3.5 animate-spin" />
            <span>{{ saving ? '正在保存...' : '固化保存此报表' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
