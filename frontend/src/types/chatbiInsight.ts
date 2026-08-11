export interface ChatBIInsightAction {
  id: string;
  label: string;
  description?: string;
  action_type: "send_query" | "fill_query" | "local_action";
  query: string;
  priority?: number;
  requires_data_result?: boolean;
  result_id?: string;
}

export interface ChatBIInsightSource {
  dataset_name?: string;
  data_source?: string;
  tables: Array<{ physical_name: string }>;
}

export interface ChatBIEvidenceMeta {
  result_status: string;
  source_ref?: string | null;
  observed_at?: string | null;
  source_as_of?: string | null;
  freshness?: string | null;
}

/** Platform-rendered result table (independent of LLM markdown). */
export interface ChatBIResultTable {
  columns: string[];
  /** Row values aligned to columns. */
  rows: unknown[][];
  total_row_count: number;
  embedded_row_count: number;
  page_size: number;
  truncated?: boolean;
}

/** Whether the model analyzed full rows or a sample. */
export interface ChatBIAnalysisScope {
  mode: "full" | "sample";
  total_row_count: number;
  model_row_count: number;
  user_notice?: string;
}

export interface ChatBIInsightMeta {
  version: number;
  status: "success";
  result_id?: string;
  sources: ChatBIInsightSource[];
  permission?: {
    row_filter_applied?: boolean;
    dataset_name?: string;
    rule_count?: number;
    message?: string;
  };
  evidence?: ChatBIEvidenceMeta;
  execution: {
    mode: "direct" | "repaired" | "federated";
    row_count: number;
    repair_count?: number;
    federated?: boolean;
  };
  final_sql?: string;
  actions: ChatBIInsightAction[];
  table?: ChatBIResultTable | null;
  analysis_scope?: ChatBIAnalysisScope | null;
}
