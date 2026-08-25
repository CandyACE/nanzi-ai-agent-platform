<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from 'vue'
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
  report?: any | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'created', report: any): void
}>()

const { showToast } = useToast()

type ReportSourceType = 'connection' | 'dataset'

const createEmptyForm = () => ({
  title: '',
  description: '',
  tags: '',
  sourceType: 'connection' as ReportSourceType,
  connectionId: null as number | null,
  datasetId: null as number | null,
  sqlContent: 'SELECT * FROM \nLIMIT 50',
})

// 表单状态
const form = ref(createEmptyForm())

type CustomParameterType = 'text' | 'number' | 'select'
type CustomParameterConfig = {
  name: string
  label: string
  type: CustomParameterType
  required: boolean
  defaultValue: string
  optionsText: string
}

const customParameterConfigs = ref<CustomParameterConfig[]>([])

const sqlEditor = ref<HTMLTextAreaElement | null>(null)
const showSqlHelp = ref(false)

const sqlParameterShortcuts = [
  { label: '开始日期', insert: '{{start_date}}' },
  { label: '结束日期', insert: '{{end_date}}' },
  { label: '开始时间', insert: '{{start_datetime}}' },
  { label: '结束时间', insert: '{{end_datetime}}' },
  { label: '开始月份', insert: '{{start_month}}' },
  { label: '结束月份', insert: '{{end_month}}' },
  {
    label: '日期条件片段',
    insert: 'order_date >= {{start_date}}\nAND order_date < {{end_date}}',
  },
  {
    label: '月份条件片段',
    insert: 'order_month BETWEEN {{start_month}} AND {{end_month}}',
  },
  { label: '插入自定义参数', insert: '{{custom_param}}' },
]

const dateParameterNames = new Set(['start_date', 'end_date', 'start_datetime', 'end_datetime'])
const monthParameterNames = new Set(['start_month', 'end_month'])
const supportedParameterNames = new Set([...dateParameterNames, ...monthParameterNames])
const sqlParameterPattern = /\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}/g

const extractSqlParameterNames = (sql: string) => {
  const names = new Set<string>()
  for (const match of sql.matchAll(sqlParameterPattern)) {
    const name = match[1]?.trim()
    if (name) names.add(name)
  }
  return Array.from(names)
}

const validateSqlParameters = (sql: string) => {
  const names = extractSqlParameterNames(sql)
  const hasDateParameters = names.some((name) => dateParameterNames.has(name))
  const hasMonthParameters = names.some((name) => monthParameterNames.has(name))
  if (hasDateParameters && hasMonthParameters) {
    return '当前一张固化报表请只使用日期范围或月份范围中的一种动态参数。'
  }
  return ''
}

const customParameterNames = (sql: string) =>
  extractSqlParameterNames(sql).filter((name) => !supportedParameterNames.has(name))

const syncCustomParameterConfigs = (sql: string) => {
  const existing = new Map(customParameterConfigs.value.map((item) => [item.name, item]))
  customParameterConfigs.value = customParameterNames(sql).map((name) => existing.get(name) || ({
    name,
    label: name,
    type: 'text',
    required: true,
    defaultValue: '',
    optionsText: '',
  }))
}

const customParameterOptions = (config: CustomParameterConfig) =>
  config.optionsText.split(/[,，\n]+/).map((item) => item.trim()).filter(Boolean)

const validateCustomParameterConfigs = () => {
  for (const config of customParameterConfigs.value) {
    if (!config.label.trim()) return `请填写参数「${config.name}」的显示名称`
    if (config.type === 'select') {
      const options = customParameterOptions(config)
      if (!options.length) return `请为下拉参数「${config.name}」填写候选值`
      if (config.required && !config.defaultValue.trim()) return `请为必填参数「${config.name}」设置默认值`
      if (config.defaultValue.trim() && !options.includes(config.defaultValue.trim())) {
        return `参数「${config.name}」的默认值必须在候选值中`
      }
    }
    if (config.type === 'number' && config.defaultValue.trim() && !Number.isFinite(Number(config.defaultValue))) {
      return `参数「${config.name}」的默认值必须是数字`
    }
    if (config.required && !config.defaultValue.trim()) return `请为必填参数「${config.name}」设置默认值`
  }
  return ''
}

const buildParameterSchema = (sql: string) => {
  const names = extractSqlParameterNames(sql)
  const schema: Array<Record<string, any>> = []
  if (names.some((name) => dateParameterNames.has(name))) {
    schema.push({
      name: 'date_range',
      type: 'date_range',
      label: '日期范围',
      default: 'month_start_to_today',
      options: ['today', 'yesterday', 'last_7_days', 'month_start_to_today', 'year_start_to_today', 'custom_range'],
    })
  } else if (names.some((name) => monthParameterNames.has(name))) {
    schema.push({
      name: 'month_range',
      type: 'month_range',
      label: '月份范围',
      default: 'last_6_completed_months',
      options: ['last_6_completed_months', 'year_start_to_current_month', 'custom_month_range'],
    })
  }
  customParameterConfigs.value.forEach((config) => {
    schema.push({
      name: config.name,
      type: config.type,
      label: config.label.trim(),
      required: config.required,
      default: config.type === 'number' && config.defaultValue.trim()
        ? Number(config.defaultValue)
        : config.defaultValue.trim() || undefined,
      ...(config.type === 'select' ? { options: customParameterOptions(config) } : {}),
    })
  })
  return schema
}

const buildDefaultParams = (parameterSchema: Array<{ name: string; default?: any }>) => {
  const defaults: Record<string, any> = {}
  for (const item of parameterSchema) {
    if (item.default !== undefined) defaults[item.name] = item.default
  }
  return defaults
}

const padNumber = (value: number) => String(value).padStart(2, '0')

const formatDateValue = (value: Date) => (
  `${value.getFullYear()}-${padNumber(value.getMonth() + 1)}-${padNumber(value.getDate())}`
)

const formatMonthValue = (value: Date) => (
  `${value.getFullYear()}-${padNumber(value.getMonth() + 1)}`
)

const buildPreviewSql = (sql: string) => {
  const validationError = validateSqlParameters(sql)
  if (validationError) {
    return { sql: '', error: validationError }
  }
  const customValidationError = validateCustomParameterConfigs()
  if (customValidationError) return { sql: '', error: customValidationError }

  const today = new Date()
  const tomorrow = new Date(today)
  tomorrow.setDate(today.getDate() + 1)
  const previousMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1)
  const sixMonthsBeforePrevious = new Date(today.getFullYear(), today.getMonth() - 6, 1)
  const values: Record<string, string> = {
    start_date: formatDateValue(new Date(today.getFullYear(), today.getMonth(), 1)),
    end_date: formatDateValue(tomorrow),
    start_datetime: `${formatDateValue(new Date(today.getFullYear(), today.getMonth(), 1))} 00:00:00`,
    end_datetime: `${formatDateValue(today)} 23:59:59`,
    start_month: formatMonthValue(sixMonthsBeforePrevious),
    end_month: formatMonthValue(previousMonth),
  }

  const customValues = new Map(customParameterConfigs.value.map((config) => [config.name, config]))

  const renderedSql = sql.replace(sqlParameterPattern, (_match, name: string) => {
    const normalizedName = name.trim()
    const value = values[normalizedName]
    if (value != null) return `'${value}'`
    const config = customValues.get(normalizedName)
    if (!config) return _match
    const customValue = config.defaultValue.trim()
    if (!customValue) return 'NULL'
    if (config.type === 'number') return customValue
    return `'${customValue.replace(/'/g, "''")}'`
  })
  return { sql: renderedSql, error: '' }
}

const insertSqlFragment = (fragment: string) => {
  const currentSql = form.value.sqlContent
  const textarea = sqlEditor.value
  const start = textarea?.selectionStart ?? currentSql.length
  const end = textarea?.selectionEnd ?? start
  const nextSql = `${currentSql.slice(0, start)}${fragment}${currentSql.slice(end)}`
  const validationError = validateSqlParameters(nextSql)
  if (validationError) {
    showToast(validationError, 'warning')
    return
  }

  form.value.sqlContent = nextSql
  void nextTick(() => {
    const nextTextarea = sqlEditor.value
    if (!nextTextarea) return
    const nextCursor = start + fragment.length
    nextTextarea.focus()
    nextTextarea.setSelectionRange(nextCursor, nextCursor)
  })
}

const formatDatasetLabel = (dataset: { id: number; name: string; display_name?: string }) => {
  const physicalName = String(dataset.name || '').trim()
  const displayName = String(dataset.display_name || '').trim()
  const namePart = displayName && displayName !== physicalName
    ? `${displayName}（${physicalName}）`
    : physicalName
  return `#${dataset.id} - ${namePart}`
}

// 数据源与数据集列表
const loadingSources = ref(false)
const dbConnections = ref<Array<{ id: number; name: string; source_key?: string; db_type: string; database_name: string }>>([])
const datasets = ref<Array<{ id: number; name: string; display_name?: string; data_source?: string; description?: string }>>([])
const sourceError = ref('')
const pendingSourceName = ref('')

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
    return conn ? (conn.source_key || conn.name) : pendingSourceName.value
  }
  if (form.value.sourceType === 'dataset' && form.value.datasetId) {
    const dataset = datasets.value.find((item) => item.id === form.value.datasetId)
    return dataset?.data_source || 'default_clickhouse'
  }
  return ''
})

const loadDataSourcesAndDatasets = async () => {
  loadingSources.value = true
  sourceError.value = ''
  try {
    const [connResult, dsResult] = await Promise.allSettled([
      axios.get('/api/portal/saved-reports/source-options'),
      axios.get('/api/portal/metadata/datasets/accessible'),
    ])

    const sourceErrors: string[] = []
    if (connResult.status === 'fulfilled') {
      dbConnections.value = Array.isArray(connResult.value.data?.data) ? connResult.value.data.data : []
    } else {
      sourceErrors.push(connResult.reason?.response?.status === 403 ? '当前账号无物理数据源读取权限' : '物理数据源加载失败')
      dbConnections.value = []
    }
    if (form.value.sourceType === 'connection') {
      if (pendingSourceName.value) {
        const matched = dbConnections.value.find((item) => (item.source_key || item.name) === pendingSourceName.value)
        form.value.connectionId = matched?.id ?? null
      }
      if (dbConnections.value.length > 0 && !form.value.connectionId) {
        form.value.connectionId = dbConnections.value[0]?.id ?? null
      }
    }

    if (dsResult.status === 'fulfilled') {
      datasets.value = Array.isArray(dsResult.value.data) ? dsResult.value.data : (dsResult.value.data?.data || [])
    } else {
      sourceErrors.push(dsResult.reason?.response?.status === 403 ? '当前账号无可访问数据集' : '数据集加载失败')
      datasets.value = []
    }
    if (!dbConnections.value.length && datasets.value.length && !pendingSourceName.value) {
      form.value.sourceType = 'dataset'
    }
    if (!dbConnections.value.length && !datasets.value.length) {
      sourceError.value = sourceErrors.length
        ? `${sourceErrors.join('；')}，请联系管理员确认访问权限。`
        : '当前账号暂无可用数据源或数据集，请联系管理员配置访问权限。'
    }
  } catch (err: any) {
    sourceError.value = err.response?.data?.detail || '数据源加载失败，请稍后重试。'
  } finally {
    loadingSources.value = false
  }
}

const resetForm = (report?: any | null) => {
  const isEditing = Boolean(report?.id)
  pendingSourceName.value = isEditing && !report?.dataset_id ? String(report?.data_source || '') : ''
  form.value = {
    title: report?.title || '',
    description: report?.description || '',
    tags: Array.isArray(report?.tags) ? report.tags.join(', ') : '',
    sourceType: report?.dataset_id ? 'dataset' : 'connection',
    connectionId: null,
    datasetId: report?.dataset_id ?? null,
    sqlContent: report?.sql_template || report?.sql_content || 'SELECT * FROM \nLIMIT 50',
  }
  customParameterConfigs.value = Array.isArray(report?.params_schema)
    ? report.params_schema
      .filter((item: any) => ['text', 'number', 'select'].includes(String(item?.type || '')))
      .map((item: any) => ({
        name: String(item.name),
        label: String(item.label || item.name),
        type: (item.type || 'text') as CustomParameterType,
        required: item.required !== false,
        defaultValue: String(report?.default_params?.[item.name] ?? item.default ?? ''),
        optionsText: Array.isArray(item.options) ? item.options.join(', ') : '',
      }))
    : []
  syncCustomParameterConfigs(form.value.sqlContent)
  testPassed.value = false
  testError.value = ''
  testResult.value = null
  sourceError.value = ''
  showSqlHelp.value = false
}

// 试跑 SQL
const runTestSql = async () => {
  if (!form.value.sqlContent.trim()) {
    showToast('请输入 SELECT SQL 语句', 'warning')
    return
  }

  const previewSql = buildPreviewSql(form.value.sqlContent.trim())
  if (previewSql.error) {
    testError.value = previewSql.error
    showToast(previewSql.error, 'warning')
    return
  }

  if (form.value.sourceType === 'connection' && !form.value.connectionId) {
    showToast('请选择数据源连接', 'warning')
    return
  }
  if (form.value.sourceType === 'dataset' && !form.value.datasetId) {
    showToast('请选择所属数据集', 'warning')
    return
  }

  testing.value = true
  testError.value = ''
  testResult.value = null
  testPassed.value = false

  try {
    const res = await axios.post('/api/portal/saved-reports/preview-sql', {
      sql: previewSql.sql,
      source_type: form.value.sourceType,
      connection_id: form.value.sourceType === 'connection' ? form.value.connectionId : undefined,
      dataset_id: form.value.sourceType === 'dataset' ? form.value.datasetId : undefined,
      limit: 50,
    })
      if (res.data?.status === 'success' || res.data?.data) {
        testResult.value = res.data.data || res.data
        testPassed.value = true
        showToast('SQL 试跑成功，已返回真实数据预览', 'success')
      } else {
        testError.value = res.data?.message || '执行未返回有效数据'
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
  const sqlContent = form.value.sqlContent.trim()
  const parameterError = validateSqlParameters(sqlContent)
  if (parameterError) {
    showToast(parameterError, 'warning')
    return
  }
  const customParameterError = validateCustomParameterConfigs()
  if (customParameterError) {
    showToast(customParameterError, 'warning')
    return
  }
  if (!testPassed.value) {
    showToast('请先试跑 SQL，确认结果后再保存', 'warning')
    return
  }
  if (!selectedDataSourceName.value) {
    showToast('请选择有效的数据源或数据集', 'warning')
    return
  }

  saving.value = true
  try {
    const tagList = form.value.tags
      .split(/[,，\s]+/)
      .map((t) => t.trim())
      .filter(Boolean)
    const currentParameterNames = extractSqlParameterNames(sqlContent).sort().join(',')
    const existingParameterNames = extractSqlParameterNames(String(props.report?.sql_template || '')).sort().join(',')
    const preserveExistingParameterConfig = Boolean(
      props.report?.id
      && props.report?.sql_template
      && Array.isArray(props.report?.params_schema)
      && props.report.params_schema.length
      && currentParameterNames === existingParameterNames,
    )
    const parameterSchema = preserveExistingParameterConfig
      ? props.report.params_schema
      : buildParameterSchema(sqlContent)
    const defaultParams = preserveExistingParameterConfig
      ? (props.report?.default_params || {})
      : buildDefaultParams(parameterSchema)

    const payload: any = {
      title: form.value.title.trim(),
      description: form.value.description.trim() || undefined,
      sql_content: sqlContent,
      data_source: selectedDataSourceName.value,
      dataset_id: form.value.sourceType === 'dataset' ? form.value.datasetId : null,
      tags: tagList,
      mode: parameterSchema.length ? 'param_sql' : 'static_sql',
      sql_template: parameterSchema.length ? sqlContent : undefined,
      params_schema: parameterSchema,
      default_params: defaultParams,
    }

    const res = props.report?.id
      ? await axios.put(`/api/portal/saved-reports/${props.report.id}`, payload)
      : await axios.post('/api/portal/saved-reports', payload)
    if (res.data?.status === 'success' || res.data?.data) {
      showToast(props.report?.id ? '固化报表已更新' : '固化报表创建成功！已录入报表库', 'success')
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

watch(
  () => [form.value.sqlContent, form.value.sourceType, form.value.connectionId, form.value.datasetId, JSON.stringify(customParameterConfigs.value)],
  () => {
    testPassed.value = false
    testResult.value = null
    testError.value = ''
  },
)

watch(
  () => form.value.sqlContent,
  (sql) => syncCustomParameterConfigs(sql),
)

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return
    resetForm(props.report)
    loadDataSourcesAndDatasets()
  },
)

onMounted(() => {
  if (props.visible) {
    resetForm(props.report)
    loadDataSourcesAndDatasets()
  }
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
              {{ props.report?.id ? '编辑固化报表' : '新建固化报表' }}
            </h3>
            <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              手写或粘贴自定义 SELECT SQL，在线试跑验证后保存为标准化固化报表
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
                {{ formatDatasetLabel(ds) }}
              </option>
            </select>
          </div>
          <p v-if="sourceError" class="text-[11px] text-amber-600 dark:text-amber-300">
            {{ sourceError }}
          </p>
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
            <div class="flex items-center gap-1.5">
              <label class="text-xs font-bold text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
              <span>自定义 SELECT SQL 语句</span>
              <span class="text-red-500">*</span>
              <span class="text-[10px] text-gray-400 font-normal">（仅允许只读查询，请避免 DDL/DML）</span>
              </label>
              <button
                type="button"
                class="inline-flex h-4 w-4 items-center justify-center rounded-full border border-blue-300 text-[10px] font-bold text-blue-600 hover:bg-blue-50 dark:border-blue-700 dark:text-blue-300 dark:hover:bg-blue-950"
                aria-label="查看动态参数 SQL 写法说明"
                title="查看动态参数 SQL 写法说明"
                @click="showSqlHelp = !showSqlHelp"
              >
                ?
              </button>
            </div>

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

          <div
            v-if="showSqlHelp"
            class="rounded-xl border border-blue-100 bg-blue-50/70 p-3 text-[11px] leading-5 text-blue-900 dark:border-blue-900/50 dark:bg-blue-950/30 dark:text-blue-100"
          >
            <p class="font-bold">动态参数说明</p>
            <p>快捷按钮会在光标位置插入占位符，参数不要再额外套单引号；试跑时系统会先用默认日期或月份替换后再执行。</p>
            <p>
              日期范围：<code v-pre>{{start_date}}</code> / <code v-pre>{{end_date}}</code>；日期时间：<code v-pre>{{start_datetime}}</code> / <code v-pre>{{end_datetime}}</code>；月份范围：<code v-pre>{{start_month}}</code> / <code v-pre>{{end_month}}</code>。
            </p>
            <p>保存后运行报表时可选择日期、月份，或填写自定义文本、数字、下拉参数。参数占位符不要额外套单引号，系统会按参数类型安全转义。</p>
          </div>

          <div class="flex flex-wrap items-center gap-1.5">
            <span class="mr-1 text-[10px] font-bold text-gray-400">快捷插入</span>
            <button
              v-for="shortcut in sqlParameterShortcuts"
              :key="shortcut.label"
              type="button"
              class="rounded-lg border border-gray-200 bg-white px-2 py-1 text-[10px] font-medium text-gray-600 transition-colors hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:border-blue-700 dark:hover:bg-blue-950 dark:hover:text-blue-200"
              :title="`插入 ${shortcut.insert}`"
              @click="insertSqlFragment(shortcut.insert)"
            >
              {{ shortcut.label }}
            </button>
          </div>

          <textarea
            ref="sqlEditor"
            v-model="form.sqlContent"
            rows="6"
            placeholder="SELECT id, department_name, sum(amount) as total_sales FROM sales_table GROUP BY id, department_name LIMIT 50;"
            class="w-full font-mono text-xs px-3.5 py-2.5 border border-gray-200 dark:border-gray-700 rounded-xl bg-slate-950 text-emerald-400 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all leading-relaxed custom-scrollbar"
          ></textarea>

          <div
            v-if="customParameterConfigs.length"
            class="space-y-3 rounded-xl border border-violet-100 bg-violet-50/50 p-3 dark:border-violet-900/40 dark:bg-violet-950/20"
          >
            <div class="flex items-center justify-between gap-2">
              <div>
                <p class="text-xs font-bold text-violet-900 dark:text-violet-200">自定义参数配置</p>
                <p class="mt-0.5 text-[10px] text-violet-700/80 dark:text-violet-300/80">运行报表时会显示这些参数；试跑使用这里配置的默认值。</p>
              </div>
              <span class="text-[10px] text-violet-600 dark:text-violet-300">{{ customParameterConfigs.length }} 个参数</span>
            </div>
            <div
              v-for="config in customParameterConfigs"
              :key="config.name"
              class="grid grid-cols-1 gap-2 rounded-lg border border-violet-100 bg-white/80 p-2.5 dark:border-violet-900/40 dark:bg-gray-900/60 md:grid-cols-[1fr_110px_1fr]"
            >
              <div class="min-w-0">
                <div class="mb-1 flex items-center gap-2">
                  <code class="text-[11px] font-bold text-violet-700 dark:text-violet-300" v-text="'{{' + config.name + '}}'"></code>
                  <span class="text-[10px] text-gray-400">参数配置</span>
                </div>
                <input
                  v-model="config.label"
                  type="text"
                  class="w-full rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 outline-none focus:border-violet-400 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-200"
                  placeholder="显示名称，例如：部门"
                />
              </div>
              <select
                v-model="config.type"
                class="h-8 rounded-lg border border-gray-200 bg-white px-2 text-xs text-gray-700 outline-none focus:border-violet-400 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-200"
              >
                <option value="text">文本</option>
                <option value="number">数字</option>
                <option value="select">下拉选择</option>
              </select>
              <div>
                <input
                  v-model="config.defaultValue"
                  :type="config.type === 'number' ? 'number' : 'text'"
                  class="w-full rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 outline-none focus:border-violet-400 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-200"
                  :placeholder="config.type === 'select' ? '默认值' : '默认值（试跑使用）'"
                />
                <input
                  v-if="config.type === 'select'"
                  v-model="config.optionsText"
                  type="text"
                  class="mt-1.5 w-full rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 outline-none focus:border-violet-400 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-200"
                  placeholder="候选值，用逗号分隔，例如：华东, 华南"
                />
                <label class="mt-1.5 inline-flex items-center gap-1.5 text-[10px] text-gray-500 dark:text-gray-400">
                  <input v-model="config.required" type="checkbox" class="rounded border-gray-300 text-violet-600 focus:ring-violet-500" />
                  必填参数
                </label>
              </div>
            </div>
          </div>
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
            :disabled="saving || !form.title.trim() || !form.sqlContent.trim() || !testPassed"
            @click="handleSubmit"
          >
            <ArrowPathIcon v-if="saving" class="w-3.5 h-3.5 animate-spin" />
            <span>{{ saving ? '正在保存...' : props.report?.id ? '保存报表修改' : '固化保存此报表' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
