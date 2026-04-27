import { api } from './client'

export interface ScheduledTestPlan {
  id: number
  account_id: number
  model_id: string
  cron_expression: string
  enabled: boolean
  max_results: number
  auto_recover: boolean
  last_run_at: string | null
  next_run_at: string | null
}

export interface TestResult {
  id: number
  plan_id: number
  status: 'success' | 'failed'
  response_text: string
  error_message: string
  latency_ms: number | null
  started_at: string
  finished_at: string
}

export interface AccountWithPlan {
  account_id: number
  account_name: string
  priority: number
  plan: ScheduledTestPlan
  results: TestResult[]
}

export async function fetchAccountPlans(accountId: number): Promise<ScheduledTestPlan[]> {
  const res = await api.get(`/admin/reports/accounts/${accountId}/scheduled-test-plans`)
  return res.data ?? []
}

export async function fetchPlanResults(planId: number, limit = 48): Promise<TestResult[]> {
  const res = await api.get(`/admin/reports/scheduled-test-plans/${planId}/results`, {
    params: { limit, timezone: 'Asia/Shanghai' },
  })
  return res.data ?? []
}
