import { api } from './client'

export interface ModelLatency {
  model: string
  requests: number
  ttft_avg: number | null
  ttft_p90: number | null
  dur_avg: number | null
  dur_p90: number | null
  otps_avg: number | null
  otps_p90: number | null
  recent_requests: number
  recent_ttft_avg: number | null
  recent_ttft_p90: number | null
  recent_dur_avg: number | null
  recent_otps_avg: number | null
  recent_otps_p90: number | null
}

export interface AccountLatency {
  account_id: number
  account_name: string
  group: string
  models: ModelLatency[]
}

export interface AccountLatencyGroup {
  group: string
  accounts: AccountLatency[]
}

export interface AccountLatencyResult {
  groups: AccountLatencyGroup[]
  limit: number
  recent_minutes: number
}

export async function fetchAccountLatency(
  limit = 300,
  recentMinutes = 10,
): Promise<AccountLatencyResult> {
  const res = await api.get<AccountLatencyResult>('/admin/reports/account-latency', {
    params: { limit, recent_minutes: recentMinutes },
  })
  return res.data
}
