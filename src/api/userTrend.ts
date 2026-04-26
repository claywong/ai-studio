import { api } from './client'

export interface UserOption {
  id: number
  email: string
  username: string
}

export interface DailyTrendItem {
  date: string
  actual_cost: number
  requests: number
  total_tokens: number
}

export async function searchUsers(search: string): Promise<UserOption[]> {
  const res = await api.get<UserOption[]>('/admin/reports/users', { params: { search, page_size: 20 } })
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
