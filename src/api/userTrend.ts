import { api } from './client'

export interface UserOption {
  id: number
  email: string
  username: string
}

export interface DailyTrendItem {
  date: string
  actual_cost: number
  account_cost: number
  requests: number
  total_tokens: number
}

export async function searchUsers(search: string): Promise<UserOption[]> {
  const res = await api.get<UserOption[]>('/admin/reports/users', { params: { search, page_size: 20 } })
  return res.data
}

export interface UsageLogItem {
  id: number
  model: string
  input_tokens: number
  output_tokens: number
  cache_creation_tokens: number
  cache_read_tokens: number
  total_cost: number
  actual_cost: number
  duration_ms: number
  request_type: string
  created_at: string
}

export interface UsageLogsResult {
  items: UsageLogItem[]
  total: number
  page: number
  pages: number
}

export async function fetchUserUsageLogs(
  userId: number,
  page: number,
  startDate: string,
  endDate: string,
): Promise<UsageLogsResult> {
  const res = await api.get<UsageLogsResult>(`/admin/reports/users/${userId}/usage-logs`, {
    params: { page, per_page: 20, start_date: startDate, end_date: endDate },
  })
  return res.data
}

export async function fetchUserDailyTrend(
  userId: number,
  startDate: string,
  endDate: string,
): Promise<{ items: DailyTrendItem[] }> {
  const res = await api.get(`/admin/reports/users/${userId}/daily-trend`, {
    params: { start_date: startDate, end_date: endDate },
  })
  return res.data
}
