import { api } from './client'

export interface UsageLogUser {
  id: number
  email: string
}

export interface UsageLogApiKey {
  id: number
  name: string
}

export interface UsageLogAccount {
  id: number
  name: string
}

export interface UsageLogItem {
  id: number
  created_at: string
  user: UsageLogUser | null
  api_key: UsageLogApiKey | null
  account: UsageLogAccount | null
  model: string
  upstream_model: string | null
  session_id: string | null
  input_tokens: number
  output_tokens: number
  total_cost: number
  actual_cost: number
  first_token_ms: number | null
  duration_ms: number
  request_id: string | null
  request_body: string | null
  response_body: string | null
  stream: boolean | null
}

export interface UsageLogsResponse {
  items: UsageLogItem[]
  total: number
  page: number
  page_size: number
}

export interface UsageLogsParams {
  page?: number
  page_size?: number
  start_date?: string
  end_date?: string
  user_id?: number
  model?: string
  session_id?: string
  account_id?: number
}

export async function fetchUsageLogs(params: UsageLogsParams): Promise<UsageLogsResponse> {
  const res = await api.get<UsageLogsResponse>('/admin/reports/usage-logs', { params })
  return res.data
}
