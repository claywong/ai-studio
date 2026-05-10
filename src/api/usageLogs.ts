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

export interface UsageLogGroup {
  id: number
  name: string
}

export interface UsageLogItem {
  id: number
  created_at: string
  user: UsageLogUser | null
  api_key: UsageLogApiKey | null
  account: UsageLogAccount | null
  group: UsageLogGroup | null
  model: string
  upstream_model: string | null
  session_id: string | null
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_creation_tokens: number
  cache_creation_5m_tokens: number
  cache_creation_1h_tokens: number
  input_cost: number | null
  output_cost: number | null
  cache_read_cost: number | null
  cache_creation_cost: number | null
  total_cost: number
  actual_cost: number
  account_stats_cost: number | null
  rate_multiplier: number | null
  account_rate_multiplier: number | null
  service_tier: string | null
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
  group_id?: number
}

export interface UserOption {
  id: number
  email: string
  username: string
}

export interface AccountOption {
  id: number
  name: string
  platform: string
}

export interface GroupOption {
  id: number
  name: string
}

export interface ModelOption {
  model: string
}

export async function fetchUsageLogs(params: UsageLogsParams): Promise<UsageLogsResponse> {
  const res = await api.get<UsageLogsResponse>('/admin/reports/usage-logs', { params })
  return res.data
}

export async function searchUsers(search: string): Promise<UserOption[]> {
  const res = await api.get<UserOption[]>('/admin/reports/users', { params: { search, page_size: 20 } })
  return res.data
}

export async function fetchAccounts(): Promise<AccountOption[]> {
  const res = await api.get<AccountOption[]>('/admin/reports/accounts-list')
  return res.data
}

export async function fetchGroups(): Promise<GroupOption[]> {
  const res = await api.get<GroupOption[]>('/admin/reports/groups')
  return res.data
}

export async function fetchModels(): Promise<{ models: { model: string }[] }> {
  const res = await api.get<{ models: { model: string }[] }>('/admin/reports/models')
  return res.data
}
