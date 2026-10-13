/**
 * 模型下拉（版本配置 / 工具高级配置 / 系统配置）的纯函数集合。
 *
 * 抽出来的目的：模型列表动辄几十条，搜索、过滤与文案必须有确定行为并被单测锁住，
 * 而不是散落在各处的模板表达式里。
 */

export type SelectableModel = {
  model_id: string;
  name?: string | null;
  type?: string | null;
  is_active?: boolean | null;
};

export type ModelSelectOption = { value: string; label: string };

/** 模型数量达到该阈值才展示搜索框（与输入框的模型切换器保持一致） */
export const MODEL_SEARCH_THRESHOLD = 6;

/** 平台里视为「多模态」的模型类型（与系统配置页的判定保持一致） */
export const MULTIMODAL_MODEL_TYPES = ['multimodal', 'vision', 'image2text'];

export function isMultimodalModelType(type?: string | null): boolean {
  return MULTIMODAL_MODEL_TYPES.includes(String(type || '').toLowerCase());
}

/** 可被版本/工具配置选择的模型：仅启用中的 LLM 与多模态模型 */
export function selectableLlmModels<T extends SelectableModel>(models: T[] | null | undefined): T[] {
  return (models || []).filter(
    (model) => (model.type === 'llm' || model.type === 'multimodal') && Boolean(model.is_active),
  );
}

/**
 * 按名称或 model_id 做大小写不敏感匹配；查询为空时返回全部并保持原始顺序。
 * 名称与 ID 都参与匹配，便于用渠道 ID 直接定位同名模型。
 */
export function filterSelectableModels<T extends SelectableModel>(
  models: T[] | null | undefined,
  query: string,
): T[] {
  const list = models || [];
  const keyword = String(query ?? '').trim().toLowerCase();
  if (!keyword) return [...list];
  return list.filter((model) => {
    const name = String(model.name ?? '').toLowerCase();
    const id = String(model.model_id ?? '').toLowerCase();
    return name.includes(keyword) || id.includes(keyword);
  });
}

/** 是否需要展示搜索框：模型太少时搜索框只会挤占空间 */
export function shouldShowModelSearch(modelCount: number): boolean {
  return Number(modelCount) >= MODEL_SEARCH_THRESHOLD;
}

/** 选项文案：多模态带视觉前缀；按需附带 model_id 与「· 多模态」之类的补充标签 */
export function modelOptionLabel(
  model: SelectableModel,
  options: { showModelId?: boolean; multimodalBadge?: string } = {},
): string {
  const prefix = isMultimodalModelType(model.type) ? '🖼️ ' : '';
  const name = String(model.name ?? '').trim() || String(model.model_id ?? '');
  const base = options.showModelId ? `${prefix}${name} (${model.model_id})` : `${prefix}${name}`;
  const badge = options.multimodalBadge && isMultimodalModelType(model.type) ? ` ${options.multimodalBadge}` : '';
  return `${base}${badge}`;
}

/** 候选模型 → 下拉选项 */
export function buildModelOptions(
  models: SelectableModel[] | null | undefined,
  options: { showModelId?: boolean; multimodalBadge?: string } = {},
): ModelSelectOption[] {
  return (models || []).map((model) => ({
    value: model.model_id,
    label: modelOptionLabel(model, options),
  }));
}

/**
 * 始终置顶、且不参与搜索过滤的「钉住」选项：
 * - 列表外的当前值（例如来自环境变量、已被删除或停用的模型），需保留才能看出当前配置是什么；
 * - 允许空值时清空/跟随上层的选项。
 */
export function buildPinnedModelOptions(
  allModels: SelectableModel[] | null | undefined,
  selectedValue: string,
  options: { allowEmpty?: boolean; emptyLabel?: string; unknownOptionLabel?: string } = {},
): ModelSelectOption[] {
  const pinned: ModelSelectOption[] = [];
  const value = String(selectedValue ?? '');
  const known = (allModels || []).some((model) => model.model_id === value);
  if (value && options.unknownOptionLabel && !known) {
    pinned.push({ value, label: `${value} (${options.unknownOptionLabel})` });
  }
  if (options.allowEmpty) {
    pinned.push({ value: '', label: options.emptyLabel ?? '跟随智能体默认配置' });
  }
  return pinned;
}

export type ModelSelectionLabelOptions = {
  allowEmpty?: boolean;
  emptyLabel?: string;
  placeholder?: string;
  showModelId?: boolean;
  unknownOptionLabel?: string;
};

/**
 * 触发器上显示的文案：
 * - 有值时显示命中模型的标签（找不到定义时回退原始 model_id，避免空白触发器）；
 * - 空值时，允许空选项的下拉显示 emptyLabel（例如「跟随编排模型」），否则显示占位提示。
 */
export function resolveModelSelectionLabel(
  models: SelectableModel[] | null | undefined,
  modelValue: string,
  options: ModelSelectionLabelOptions = {},
): string {
  const emptyLabel = options.emptyLabel ?? '跟随智能体默认配置';
  const placeholder = options.placeholder ?? '选择模型...';
  if (!modelValue) return options.allowEmpty ? emptyLabel : placeholder;
  const matched = (models || []).find((model) => model.model_id === modelValue);
  if (matched) return modelOptionLabel(matched, { showModelId: options.showModelId });
  return options.unknownOptionLabel ? `${modelValue} (${options.unknownOptionLabel})` : modelValue;
}
