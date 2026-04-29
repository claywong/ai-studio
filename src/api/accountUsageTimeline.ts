import { api } from './client'

export interface UsageBucket {
  time: string
  avg_ttft_ms: number | null
  tokens_per_second: number | null
  request_count: number
  error_count: number
}

export interface AccountTimeline {
  account_id: number
  account_name: string
  buckets: UsageBucket[]
}

export interface AccountUsageTimelineResult {
  data: AccountTimeline[]
  hours: number
  granularity: 'minute' | 'hour'
}

export async function fetchAccountUsageTimeline(
  accountIds: number[],
  hours: number,
): Promise<AccountUsageTimelineResult> {
  const res = await api.get<AccountUsageTimelineResult>('/admin/reports/account-usage-timeline', {
    params: { account_ids: accountIds.join(','), hours },
  })
  return res.data
}
