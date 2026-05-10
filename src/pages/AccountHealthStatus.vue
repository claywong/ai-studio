<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { api } from '../api/client'

interface AccountItem {
  id: number
  name: string
  status: string
  platform: string
  priority: number
  schedulable: boolean
  health_verdict: string | null
  health_verdict_reason: string | null
  groups: { id: number; name: string }[]
}

interface HealthStats {
  available: boolean
  req_count: number
  err_count: number
  err_rate: number
  slow_count: number
  slow_rate: number
  ttft_avg_ms: number
  otps_avg: number
  tcp_conn_avg_ms: number
  ttfb_avg_ms: number
  verdict: string
  verdict_reason: string
  window_seconds: number
}

interface AccountRow extends AccountItem {
  health: HealthStats | null
  healthLoading: boolean
}

const rows = ref<AccountRow[]>([])
const loading = ref(false)
const error = ref('')
const lastUpdated = ref('')
const filterStatus = ref('')
const filterSchedulable = ref('')
const filterVerdict = ref('')
const filterGroup = ref('')
const allGroups = ref<{ id: number; name: string }[]>([])
let timer: ReturnType<typeof setInterval> | null = null

async function fetchAccounts(): Promise<AccountItem[]> {
  const res = await api.get('/admin/reports/accounts-list')
  return (res.data ?? []) as AccountItem[]
}

async function fetchHealth(accountId: number): Promise<HealthStats | null> {
  try {
    const res = await api.get(`/admin/reports/accounts/${accountId}/health-stats`)
    return res.data as HealthStats
  } catch {
    return null
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const accounts = await fetchAccounts()
    accounts.sort((a, b) => a.priority - b.priority)

    // 收集所有分组
    const groupMap = new Map<number, string>()
    for (const a of accounts) {
      for (const g of a.groups) groupMap.set(g.id, g.name)
    }
    allGroups.value = [...groupMap.entries()]
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name))

    // 先渲染账户列表，health 异步填充
    rows.value = accounts.map((a) => ({ ...a, health: null, healthLoading: true }))

    await Promise.all(
      rows.value.map(async (row) => {
        row.health = await fetchHealth(row.id)
        row.healthLoading = false
      }),
    )

    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

const filtered = computed(() => {
  return rows.value.filter((r) => {
    if (filterStatus.value && r.status !== filterStatus.value) return false
    if (filterSchedulable.value === 'yes' && !r.schedulable) return false
    if (filterSchedulable.value === 'no' && r.schedulable) return false
    if (filterVerdict.value) {
      const v = r.health?.verdict ?? 'OK'
      if (v !== filterVerdict.value) return false
    }
    if (filterGroup.value) {
      const gid = Number(filterGroup.value)
      if (!r.groups.some((g) => g.id === gid)) return false
    }
    return true
  })
})

// 统计
const summary = computed(() => {
  const all = rows.value
  return {
    total: all.length,
    active: all.filter((r) => r.status === 'active').length,
    error: all.filter((r) => r.status === 'error').length,
    schedulable: all.filter((r) => r.schedulable).length,
    excluded: all.filter((r) => r.health?.verdict === 'Excluded').length,
    stickyOnly: all.filter((r) => r.health?.verdict === 'StickyOnly').length,
    errRate100: all.filter((r) => (r.health?.err_count ?? 0) > 0 && r.health?.err_count === r.health?.req_count && (r.health?.req_count ?? 0) > 0).length,
  }
})

function verdictClass(verdict: string | undefined): string {
  if (!verdict || verdict === 'OK') return 'verdict-ok'
  if (verdict === 'StickyOnly') return 'verdict-sticky'
  if (verdict === 'Excluded') return 'verdict-excluded'
  return ''
}

function statusClass(s: string): string {
  if (s === 'active') return 'status-active'
  if (s === 'error') return 'status-error'
  if (s === 'inactive') return 'status-inactive'
  return 'status-other'
}

function fmtMs(ms: number): string {
  if (!ms) return '-'
  if (ms >= 1000) return (ms / 1000).toFixed(1) + 's'
  return ms + 'ms'
}

function fmtOtps(v: number): string {
  if (!v) return '-'
  return v.toFixed(1)
}

function errRateClass(rate: number, count: number): string {
  if (count === 0) return ''
  if (rate >= 0.5) return 'err-high'
  if (rate >= 0.2) return 'err-mid'
  return ''
}

function ttftClass(ms: number): string {
  if (!ms) return ''
  if (ms < 2000) return 'ttft-good'
  if (ms < 5000) return 'ttft-ok'
  if (ms < 10000) return 'ttft-warn'
  return 'ttft-bad'
}

function tcpConnClass(ms: number): string {
  if (!ms) return ''
  if (ms < 200) return 'ttft-good'
  if (ms < 500) return 'ttft-ok'
  if (ms < 1000) return 'ttft-warn'
  return 'ttft-bad'
}

function ttfbClass(ms: number): string {
  if (!ms) return ''
  if (ms < 1000) return 'ttft-good'
  if (ms < 3000) return 'ttft-ok'
  if (ms < 6000) return 'ttft-warn'
  return 'ttft-bad'
}

onMounted(() => {
  void load()
  timer = setInterval(() => void load(), 60 * 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <span class="title">账号健康状态</span>

      <div class="filter-item">
        <span class="filter-label">状态</span>
        <select v-model="filterStatus">
          <option value="">全部</option>
          <option value="active">正常</option>
          <option value="error">错误</option>
          <option value="inactive">停用</option>
        </select>
      </div>

      <div class="filter-item">
        <span class="filter-label">调度</span>
        <select v-model="filterSchedulable">
          <option value="">全部</option>
          <option value="yes">可调度</option>
          <option value="no">不调度</option>
        </select>
      </div>

      <div class="filter-item">
        <span class="filter-label">健康</span>
        <select v-model="filterVerdict">
          <option value="">全部</option>
          <option value="OK">OK</option>
          <option value="StickyOnly">StickyOnly</option>
          <option value="Excluded">Excluded</option>
        </select>
      </div>

      <div class="filter-item">
        <span class="filter-label">分组</span>
        <select v-model="filterGroup">
          <option value="">全部</option>
          <option v-for="g in allGroups" :key="g.id" :value="g.id">{{ g.name }}</option>
        </select>
      </div>

      <button class="btn-refresh" :disabled="loading" @click="load">
        {{ loading ? '加载中…' : '刷新' }}
      </button>
      <span v-if="lastUpdated" class="updated">{{ lastUpdated }} · 每分钟自动刷新</span>
    </div>

    <!-- 统计卡片 -->
    <div class="summary-bar">
      <div class="sum-card">
        <span class="sum-val">{{ summary.total }}</span>
        <span class="sum-label">总账号</span>
      </div>
      <div class="sum-card">
        <span class="sum-val good">{{ summary.active }}</span>
        <span class="sum-label">active</span>
      </div>
      <div class="sum-card">
        <span class="sum-val" :class="summary.error > 0 ? 'bad' : ''">{{ summary.error }}</span>
        <span class="sum-label">error</span>
      </div>
      <div class="sum-card">
        <span class="sum-val">{{ summary.schedulable }}</span>
        <span class="sum-label">可调度</span>
      </div>
      <div class="sum-card">
        <span class="sum-val" :class="summary.excluded > 0 ? 'bad' : ''">{{ summary.excluded }}</span>
        <span class="sum-label">Excluded</span>
      </div>
      <div class="sum-card">
        <span class="sum-val" :class="summary.stickyOnly > 0 ? 'warn' : ''">{{ summary.stickyOnly }}</span>
        <span class="sum-label">StickyOnly</span>
      </div>
      <div class="sum-card">
        <span class="sum-val" :class="summary.errRate100 > 0 ? 'bad' : ''">{{ summary.errRate100 }}</span>
        <span class="sum-label">全错账号</span>
      </div>
    </div>

    <div v-if="error" class="error-msg">{{ error }}</div>

    <table v-if="filtered.length > 0" class="health-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>账号名</th>
          <th>平台</th>
          <th>状态</th>
          <th>调度</th>
          <th>健康判定</th>
          <th>请求</th>
          <th>错误</th>
          <th>错误率</th>
          <th>TCP连接</th>
          <th>TTFB</th>
          <th>TTFT</th>
          <th>OTPs (tok/s)</th>
          <th>原因</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in filtered"
          :key="row.id"
          :class="{ 'row-error': row.status === 'error', 'row-unschedulable': !row.schedulable }"
        >
          <td class="col-id">{{ row.id }}</td>
          <td class="col-name">{{ row.name }}</td>
          <td class="col-platform">{{ row.platform || '-' }}</td>
          <td><span :class="['badge', statusClass(row.status)]">{{ row.status }}</span></td>
          <td class="col-center">
            <span v-if="row.schedulable" class="sched-yes">✓</span>
            <span v-else class="sched-no">✗</span>
          </td>
          <td>
            <span v-if="row.healthLoading" class="loading-dot">…</span>
            <span v-else :class="['badge', verdictClass(row.health?.verdict)]">
              {{ row.health?.verdict || 'OK' }}
            </span>
          </td>
          <td class="col-num">{{ row.health?.req_count ?? '-' }}</td>
          <td class="col-num" :class="(row.health?.err_count ?? 0) > 0 ? 'err-val' : ''">
            {{ row.health?.err_count ?? '-' }}
          </td>
          <td class="col-num" :class="errRateClass(row.health?.err_rate ?? 0, row.health?.req_count ?? 0)">
            {{ row.health ? (row.health.err_rate * 100).toFixed(0) + '%' : '-' }}
          </td>
          <td class="col-num" :class="tcpConnClass(row.health?.tcp_conn_avg_ms ?? 0)">
            {{ row.health ? fmtMs(row.health.tcp_conn_avg_ms) : '-' }}
          </td>
          <td class="col-num" :class="ttfbClass(row.health?.ttfb_avg_ms ?? 0)">
            {{ row.health ? fmtMs(row.health.ttfb_avg_ms) : '-' }}
          </td>
          <td class="col-num" :class="ttftClass(row.health?.ttft_avg_ms ?? 0)">
            {{ row.health ? fmtMs(row.health.ttft_avg_ms) : '-' }}
          </td>
          <td class="col-num">{{ row.health ? fmtOtps(row.health.otps_avg) : '-' }}</td>
          <td class="col-reason">{{ row.health?.verdict_reason || '' }}</td>
        </tr>
      </tbody>
    </table>

    <div v-else-if="!loading" class="empty">没有符合条件的账号</div>
  </div>
</template>

<style scoped>
.page {
  padding: 20px 40px;
  color: #334155;
  font-size: 13px;
  min-height: 100vh;
  background: #f8fafc;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  margin-right: 8px;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-label {
  color: #64748b;
  font-size: 12px;
}

select {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  color: #334155;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
}

.btn-refresh {
  background: #2563eb;
  color: #ffffff;
  border: none;
  border-radius: 6px;
  padding: 5px 14px;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-refresh:hover:not(:disabled) { background: #1d4ed8; }
.btn-refresh:disabled { opacity: 0.5; cursor: default; }

.updated {
  color: #94a3b8;
  font-size: 11px;
}

/* 统计栏 */
.summary-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.sum-card {
  background: #ffffff;
  border: 1px solid #e5e9f2;
  border-radius: 8px;
  padding: 5px 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.sum-val {
  font-size: 18px;
  font-weight: 700;
  color: #475569;
}
.sum-val.good { color: #16a34a; }
.sum-val.bad  { color: #dc2626; }
.sum-val.warn { color: #d97706; }

.sum-label {
  font-size: 11px;
  color: #94a3b8;
}

/* 表格 */
.health-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  background: #ffffff;
  border: 1px solid #e5e9f2;
  border-radius: 10px;
  overflow: hidden;
}

.health-table th {
  background: #f8fafc;
  color: #64748b;
  font-weight: 600;
  padding: 8px 12px;
  text-align: left;
  border-bottom: 1px solid #e5e9f2;
  white-space: nowrap;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.health-table td {
  padding: 7px 12px;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: middle;
  color: #475569;
}

.health-table tbody tr:last-child td { border-bottom: none; }

.health-table tr:hover td { background: #f8fafc; }

.row-error td { background: rgba(220, 38, 38, 0.04); }
.row-unschedulable td { opacity: 0.55; }

.col-id { color: #94a3b8; width: 40px; }
.col-name { font-weight: 500; color: #0f172a; }
.col-platform { color: #94a3b8; }
.col-num { text-align: right; font-variant-numeric: tabular-nums; }
.col-center { text-align: center; }
.col-reason { color: #94a3b8; font-size: 11px; max-width: 220px; }

/* badge */
.badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.status-active   { background: #dcfce7; color: #16a34a; }
.status-error    { background: #fee2e2; color: #dc2626; }
.status-inactive { background: #f1f5f9; color: #64748b; }
.status-other    { background: #f1f5f9; color: #94a3b8; }

.verdict-ok       { background: #dcfce7; color: #16a34a; }
.verdict-sticky   { background: #fef3c7; color: #d97706; }
.verdict-excluded { background: #fee2e2; color: #dc2626; }

.sched-yes { color: #16a34a; font-weight: 600; }
.sched-no  { color: #cbd5e1; }

/* 数值着色 */
.err-val  { color: #dc2626; }
.err-high { color: #dc2626; font-weight: 600; }
.err-mid  { color: #d97706; }

.ttft-good { color: #16a34a; font-weight: 600; }
.ttft-ok   { color: #65a30d; font-weight: 600; }
.ttft-warn { color: #d97706; font-weight: 600; }
.ttft-bad  { color: #dc2626; font-weight: 600; }

.loading-dot { color: #cbd5e1; }
.error-msg { color: #dc2626; margin-bottom: 12px; }
.empty { color: #94a3b8; padding: 40px; text-align: center; }
</style>
