import { api } from './client'

export interface ChannelMonitor {
  id: number
  name: string
  provider: string
  endpoint: string
  primary_model: string
  extra_models: string[]
  enabled: boolean
  interval_seconds: number
  last_checked_at: string | null
  primary_status: string
  primary_latency_ms: number | null
  availability_7d: number
  extra_models_status: { model: string; status: string; latency_ms: number | null }[]
}

export interface HistoryItem {
  id: number
  model: string
  status: string
  latency_ms: number | null
  ping_latency_ms: number | null
  message: string
  checked_at: string
}

export async function fetchMonitors(): Promise<{ items: ChannelMonitor[]; total: number }> {
  const res = await api.get('/admin/reports/channel-monitors')
  return res.data
}

export async function fetchMonitorHistory(
  monitorId: number,
  limit = 200,
  model?: string,
): Promise<{ items: HistoryItem[] }> {
  const params: Record<string, unknown> = { limit }
  if (model) params.model = model
  const res = await api.get(`/admin/reports/channel-monitors/${monitorId}/history`, { params })
  return res.data
}
