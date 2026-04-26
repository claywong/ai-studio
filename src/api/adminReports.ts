import { api } from './client'

export interface OverviewData {
  active_api_keys: number
  active_users: number
  normal_accounts: number
  error_accounts: number
  ratelimit_accounts: number
  overload_accounts: number
  rpm: number
  hourly_active_users: number
  stats_updated_at: string
  period_active_users: number | null
  period_days: number
}

export interface TrendItem {
  date: string
  requests: number
  cost: number
  actual_cost: number
  input_tokens: number
  output_tokens: number
}

export interface TrendData {
  trend: TrendItem[]
  start_date: string
  end_date: string
  granularity: string
}

export interface ModelItem {
  model: string
  requests: number
  cost: number
  actual_cost: number
  input_tokens: number
  output_tokens: number
}

export interface ModelsData {
  models: ModelItem[]
}

export interface AccountItem {
  id: number
  name: string
  platform: string
  status: string
  requests: number
  total_cost: number
  last_used_at: string | null
  expires_at: string | null
}

export interface AccountGroup {
  group_name: string
  account_count: number
  total_requests: number
  total_cost: number
  input_tokens: number
  output_tokens: number
  last_used_at: string | null
  accounts: AccountItem[]
}

export interface DateRange {
  start: string  // YYYY-MM-DD
  end: string    // YYYY-MM-DD
}

function rangeParams(range: DateRange) {
  return { start_date: range.start, end_date: range.end }
}

export async function fetchOverview(range: DateRange): Promise<OverviewData> {
  const res = await api.get<OverviewData>('/admin/reports/overview', { params: rangeParams(range) })
  return res.data
}

export async function fetchTrend(range: DateRange): Promise<TrendData> {
  const res = await api.get<TrendData>('/admin/reports/trend', { params: rangeParams(range) })
  return res.data
}

export async function fetchModels(range: DateRange): Promise<ModelsData> {
  const res = await api.get<ModelsData>('/admin/reports/models', { params: rangeParams(range) })
  return res.data
}

export async function fetchAccounts(range: DateRange): Promise<AccountGroup[]> {
  const res = await api.get<AccountGroup[]>('/admin/reports/accounts', { params: rangeParams(range) })
  return res.data
}
