/**
 * 「继续分析」动作与图标的唯一来源。
 *
 * 文案很长（每个 query 都是一段完整指令），曾经只活在 MessageContinueAnalysis.vue 里；
 * 移动端操作抽屉要复用同一批动作，所以抽到这里，避免第二份副本漂移。
 */
export type ContinueAction = {
  id: string;
  label: string;
  description: string;
  query: string;
};

export const CONTINUE_ANALYSIS_ACTIONS: ContinueAction[] = [
  {
    id: "visual_report",
    label: "生成可视化分析报告",
    description: "基于当前回复中的数据生成图表和结构化结论",
    query: "请基于当前这条 AI 回复中已经存在的文本、Markdown 表格和可核验数据，生成一份结构化可视化分析报告。请先说明数据范围、数据来源、数据完整性和缺失项，再提炼关键发现、趋势、对比、异常和可能原因。适合可视化的数据请使用合法的 ```chart ECharts 代码块输出，并在图表后解释图表结论。图表数据必须完全来自当前回复，不得编造数据；如果数据不足以生成可靠图表，请不要强行出图，并明确说明原因。最后输出结论、风险和建议。报告应包含：分析概览、数据说明、关键发现、可视化图表、图表解读、结论与建议。",
  },
  {
    id: "save_markdown",
    label: "保存为 Markdown",
    description: "保存到工作区 docs 目录并返回实际路径",
    query: "请将刚才这条 AI 回复完整保存为 Markdown 文档，文件名根据内容自动生成，保存到当前工作区的 docs 目录下。保存完成后请返回实际写入的完整路径，并确认文件已经成功保存。不要只给我建议路径或示例路径。",
  },
  {
    id: "save_word",
    label: "保存为 Word",
    description: "生成 .docx 文件并返回下载地址",
    query: "请将刚才这条 AI 回复整理并保存为 Word 文档（.docx），文件名根据内容自动生成，优先使用当前工作区的 docs 目录。请调用可用的 Word 文档工具实际生成文件；完成后原样返回工具提供的实际下载地址或打开地址，并确认文件已经成功生成，不要虚构物理路径。",
  },
  {
    id: "create_skill",
    label: "提炼生成 Skill",
    description: "按 create_skills 工具规范生成个人 Skill",
    query: "请根据刚才这条 AI 回复的内容，直接调用 create_skills 工具提炼并创建一个个人 Skill。请按照工具要求生成合法的 skill_id、名称、用途描述和完整的 SKILL.md 内容：文件必须以包含 name 和 description 的 YAML Frontmatter 开始，后续使用清晰、可执行的 imperative 指令。scope 使用 personal。不要只输出 Skill 草稿，必须实际调用工具创建。创建成功后请返回 Skill 名称、skill_id、作用域和工具返回的完整物理路径，并说明如何使用。",
  },
];

const CONTINUE_ACTION_ICONS: Record<string, string> = {
  visual_report: "▥",
  save_markdown: "M",
  save_word: "W",
  create_skill: "✦",
};

/** 通用沉淀动作的图标（原先内联在 MessageContinueAnalysis.vue 里）。 */
export const continueActionIcon = (id: string): string => CONTINUE_ACTION_ICONS[id] ?? "→";

const CHATBI_ACTION_ICONS: Record<string, string> = {
  trend: "↗",
  ranking: "#",
  contribution: "%",
  anomaly: "!",
  visualize: "▥",
  summary: "≡",
  brief: "▤",
  monitor: "◉",
};

/** ChatBI 追问动作的图标（原先内联在 ChatBIContinueAnalysis.vue 里）。 */
export const chatbiActionIcon = (id: string): string => CHATBI_ACTION_ICONS[id] ?? "→";
