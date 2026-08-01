import axios from '@/utils/axios'

export interface AIModel {
  id: string
  name: string
  model_id: string
  provider: string
  type: string
  api_base_url?: string
  context_size?: number | null
  max_output_tokens?: number | null
  has_api_key?: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface AIModelCreate {
  name: string
  model_id: string
  provider: string
  type: string
  api_base_url?: string
  context_size?: number | null
  max_output_tokens?: number | null
  api_key?: string
  is_active?: boolean
}

export interface AIModelUpdate {
  name?: string
  model_id?: string
  provider?: string
  type?: string
  api_base_url?: string
  context_size?: number | null
  max_output_tokens?: number | null
  api_key?: string
  is_active?: boolean
}

export interface AIModelDiscoverRequest {
  provider: string
  api_base_url?: string
  api_key?: string
  model_config_id?: string
}

export interface AIModelOption {
  model_id: string
  name: string
}

export interface AIModelReference {
  kind: string
  key: string
  label: string
  detail: string
}

export interface AIModelTestRequest {
  provider: string
  type: string
  model_id: string
  api_base_url?: string | null
  api_key?: string | null
  context_size?: number | null
  max_output_tokens?: number | null
  model_config_id?: string
}

export const modelApi = {
  list: (type?: string, includeInactive = false) => {
    return axios.get<AIModel[]>('/api/portal/models', { params: { type, include_inactive: includeInactive } })
  },
  
  create: (data: AIModelCreate) => {
    return axios.post<AIModel>('/api/portal/models', data)
  },
  
  update: (id: string, data: AIModelUpdate) => {
    return axios.put<AIModel>(`/api/portal/models/${id}`, data)
  },
  
  delete: (id: string) => {
    return axios.delete(`/api/portal/models/${id}`)
  },

  references: (id: string) => {
    return axios.get<AIModelReference[]>(`/api/portal/models/${id}/references`)
  },

  testConnection: (id: string) => {
    return axios.post<{ status: string; message: string; response?: string }>(`/api/portal/models/${id}/test`)
  },

  testConfig: (data: AIModelTestRequest) => {
    return axios.post<{ status: string; message: string; response?: string }>('/api/portal/models/test-config', data)
  },

  discover: (data: AIModelDiscoverRequest) => {
    return axios.post<AIModelOption[]>('/api/portal/models/discover', data)
  }
}
