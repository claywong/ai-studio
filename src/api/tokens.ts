import { api } from './client'

export interface StudioToken {
  id: number
  name: string
  key: string
  status: string
  group_id: number | null
  group_name?: string | null
  platform?: string | null
  created_at?: string
  last_used_at?: string | null
}

export async function listTokens() {
  const response = await api.get('/tokens')
  return response.data.data as StudioToken[]
}

export async function createToken(name = 'G7E6 AI Studio') {
  const response = await api.post('/tokens', { name })
  return response.data.data as StudioToken
}
