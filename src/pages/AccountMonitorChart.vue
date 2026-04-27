<script setup lang="ts">
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { onUnmounted, ref, computed } from 'vue'
import { api } from '../api/client'
import { fetchAccountPlans, fetchPlanResults, type AccountWithPlan, type TestResult } from '../api/scheduledMonitor'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

interface AccountItem {
  id: number
  name: string
  priority: number
  status: string
  platform: string
  groups: { id: number; name: string }[]
  schedulable: boolean
  temp_unschedulable_until: string | null
  temp_unschedulable_reason: string
  rate_limited_at: string | null
  rate_limit_reset_at: string | null
  overload_until: string | null
}

const ACCOUNT_STATUS_OPTIONS = [
  { value: 'active', label: '正常' },
  { value: 'inactive', label: '停用' },
  { value: 'error', label: '错误' },
  { value: 'rate_limited', label: '限流中' },
  { value: 'temp_unschedulable', label: '临时不可调度' },
]

const loading = ref(false)
const error = ref('')
const lastUpdated = ref('')
const accountsWithData = ref<AccountWithPlan[]>([])
const allPlatforms = ref<string[]>([])
const allGroups = ref<{ id: number; name: string }[]>([])

const limit = ref(48)
const filterPlatform = ref('')
const filterStatus = ref('')
const filterGroup = ref('')

let timer: ReturnType<typeof setInterval> | null = null

function fmtTime(iso: string) {
  const d = new Date(iso)
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

async function fetchAllAccounts(): Promise<AccountItem[]> {
  const res = await api.get('/admin/reports/accounts-list')
  return (res.data ?? []) as AccountItem[]
}

async function load() {
  loading.value = true
  try {
    error.value = ''
    let accounts = await fetchAllAccounts()
    accounts.sort((a, b) => a.priority - b.priority)

    const platforms = new Set<string>()
    const groupMap = new Map<number, string>()
    for (const a of accounts) {
      if (a.platform) platforms.add(a.platform)
      for (const g of a.groups) groupMap.set(g.id, g.name)
    }
    allPlatforms.value = [...platforms].sort()
    allGroups.value = [...groupMap.entries()]
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name))

    if (filterPlatform.value) accounts = accounts.filter((a) => a.platform === filterPlatform.value)
    if (filterStatus.value) accounts = accounts.filter((a) => a.status === filterStatus.value)
    if (filterGroup.value) {
      const gid = Number(filterGroup.value)
      accounts = accounts.filter((a) => a.groups.some((g) => g.id === gid))
    }

    accounts = accounts.slice(0, 20)

    const results: AccountWithPlan[] = []
    await Promise.all(
      accounts.map(async (acct) => {
        try {
          const plans = await fetchAccountPlans(acct.id)
          if (!plans || plans.length === 0) return
          const plan = plans[0]
          if (!plan.enabled) return
          const testResults = await fetchPlanResults(plan.id, limit.value)
          if (!testResults || testResults.length === 0) return
          results.push({
            account_id: acct.id,
            account_name: acct.name,
            priority: acct.priority,
            platform: acct.platform,
            groups: acct.groups,
            schedulable: acct.schedulable,
            temp_unschedulable_until: acct.temp_unschedulable_until,
            temp_unschedulable_reason: acct.temp_unschedulable_reason,
            rate_limited_at: acct.rate_limited_at,
            rate_limit_reset_at: acct.rate_limit_reset_at,
            overload_until: acct.overload_until,
            plan,
            results: testResults,
          })
        } catch {
          // 单个账号失败不影响其他
        }
      }),
    )

    results.sort((a, b) => a.priority - b.priority)
    accountsWithData.value = results
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

async function initOptions() {
  try {
    const accounts = await fetchAllAccounts()
    const platforms = new Set<string>()
    const groupMap = new Map<number, string>()
    for (const a of accounts) {
      if (a.platform) platforms.add(a.platform)
      for (const g of a.groups) groupMap.set(g.id, g.name)
    }
    allPlatforms.value = [...platforms].sort()
    allGroups.value = [...groupMap.entries()]
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name))
  } catch {
    // 忽略
  }
}

function buildChartOption(item: AccountWithPlan) {
  const sorted = [...item.results].sort(
    (a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime(),
  )

  const times = sorted.map((r) => fmtTime(r.started_at))
  const successData = sorted.map((r) => (r.status === 'success' ? 1 : 0))
  const latencyData = sorted.map((r) => (r.status === 'success' ? r.latency_ms : null))

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', lineStyle: { color: '#38bdf8', width: 1 } },
      backgroundColor: '#0d1117',
      borderColor: '#1e3a5f',
      borderWidth: 1,
      textStyle: { color: '#94a3b8', fontFamily: 'JetBrains Mono, monospace', fontSize: 11 },
      formatter(params: { seriesName: string; value: number | null; name: string }[]) {
        const time = params[0]?.name ?? ''
        const lines = params.map((p) => {
          if (p.seriesName === '可用性') {
            return `<span style="color:#64748b">${p.seriesName}</span>: <span style="color:${p.value === 1 ? '#22d3ee' : '#f87171'}">${p.value === 1 ? '✓ 成功' : '✗ 失败'}</span>`
          }
          return `<span style="color:#64748b">${p.seriesName}</span>: <span style="color:#38bdf8">${p.value != null ? p.value + 'ms' : '—'}</span>`
        })
        return `<div style="font-family:'JetBrains Mono',monospace;font-size:11px;padding:2px 0"><span style="color:#475569;font-size:10px">${time}</span><br/>${lines.join('<br/>')}</div>`
      },
    },
    grid: { top: 12, right: 12, bottom: 22, left: 52 },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: {
        fontSize: 9,
        color: '#334155',
        interval: Math.floor(times.length / 6),
        fontFamily: 'JetBrains Mono, monospace',
      },
      axisLine: { lineStyle: { color: '#1e293b' } },
      axisTick: { lineStyle: { color: '#1e293b' } },
    },
    yAxis: [
      {
        type: 'value',
        name: 'ms',
        min: 0,
        max: 60000,
        nameTextStyle: { fontSize: 9, color: '#334155', fontFamily: 'JetBrains Mono, monospace' },
        axisLabel: {
          fontSize: 9,
          color: '#334155',
          fontFamily: 'JetBrains Mono, monospace',
          formatter: (v: number) => v >= 1000 ? (v / 1000) + 's' : String(v),
        },
        splitLine: { lineStyle: { color: '#0f1f35', type: 'dashed' } },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      { type: 'value', min: 0, max: 1, show: false },
    ],
    series: [
      {
        name: '延迟',
        type: 'line',
        data: latencyData,
        yAxisIndex: 0,
        smooth: 0.4,
        symbol: 'none',
        lineStyle: { color: '#0ea5e9', width: 1.5 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(14,165,233,0.25)' },
              { offset: 1, color: 'rgba(14,165,233,0.02)' },
            ],
          },
        },
        connectNulls: false,
      },
      {
        name: '可用性',
        type: 'line',
        data: successData,
        yAxisIndex: 1,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { width: 0 },
        itemStyle: {
          color(params: { value: number }) {
            return params.value === 1 ? '#22d3ee' : '#f87171'
          },
          borderWidth: 0,
        },
      },
    ],
  }
}

const chartOptions = computed(() =>
  accountsWithData.value.map((item) => ({
    key: item.account_id,
    name: item.account_name,
    priority: item.priority,
    model: item.plan.model_id,
    successRate: calcSuccessRate(item.results),
    successRateNum: calcSuccessRateNum(item.results),
    lastStatus: item.results[0]?.status ?? 'unknown',
    scheduleTag: getScheduleTag(item),
    schedulable: item.schedulable,
    option: buildChartOption(item),
  })),
)

function parseSchedReason(raw: string): { statusCode?: number; keyword?: string; message?: string } {
  if (!raw) return {}
  try {
    const obj = JSON.parse(raw) as {
      status_code?: number
      matched_keyword?: string
      error_message?: string
    }
    let message = obj.error_message ?? ''
    if (message) {
      try { message = (JSON.parse(message) as { message?: string }).message ?? message } catch { /* raw */ }
      if (message.length > 80) message = message.slice(0, 80) + '…'
    }
    return { statusCode: obj.status_code, keyword: obj.matched_keyword, message: message || undefined }
  } catch {
    const msg = raw.length > 80 ? raw.slice(0, 80) + '…' : raw
    return { message: msg }
  }
}

function getScheduleTag(item: AccountWithPlan): { label: string; cls: string; tip: string } | null {
  const now = Date.now()
  if (item.overload_until && new Date(item.overload_until).getTime() > now) {
    return { label: '过载', cls: 'sched-overload', tip: `过载至 ${fmtTime(item.overload_until)}` }
  }
  if (item.rate_limit_reset_at && new Date(item.rate_limit_reset_at).getTime() > now) {
    return { label: '限流', cls: 'sched-ratelimit', tip: `限流重置于 ${fmtTime(item.rate_limit_reset_at)}` }
  }
  if (item.temp_unschedulable_until && new Date(item.temp_unschedulable_until).getTime() > now) {
    const reason = parseSchedReason(item.temp_unschedulable_reason)
    const until = fmtTime(item.temp_unschedulable_until)
    const lines = [`⏱ 截止：${until}`]
    if (reason.statusCode) lines.push(`🔴 状态码：${reason.statusCode}`)
    if (reason.keyword) lines.push(`🔑 触发词：${reason.keyword}`)
    if (reason.message) lines.push(`📄 ${reason.message}`)
    return { label: '临时停调', cls: 'sched-temp', tip: lines.join('\n') }
  }
  return null
}

function calcSuccessRate(results: TestResult[]) {
  if (!results.length) return '-'
  const ok = results.filter((r) => r.status === 'success').length
  return ((ok / results.length) * 100).toFixed(0) + '%'
}

function calcSuccessRateNum(results: TestResult[]) {
  if (!results.length) return 0
  const ok = results.filter((r) => r.status === 'success').length
  return (ok / results.length) * 100
}

function getSignalColor(rate: number) {
  if (rate >= 90) return '#22d3ee'
  if (rate >= 60) return '#f59e0b'
  return '#f87171'
}

function startAutoRefresh() {
  if (timer) clearInterval(timer)
  timer = setInterval(() => void load(), 5 * 60 * 1000)
}

void initOptions()

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

async function onQuery() {
  await load()
  startAutoRefresh()
}
</script>

<template>
  <div class="page">
    <!-- 扫描线纹理叠层 -->
    <div class="scanlines" aria-hidden="true"></div>

    <div class="toolbar">
      <div class="title-block">
        <span class="title-accent">▍</span>
        <span class="title">ACCT MONITOR</span>
        <span class="title-sub">account latency & availability</span>
      </div>

      <div class="filters">
        <div class="filter-item">
          <label class="filter-label">LIMIT</label>
          <select v-model="limit">
            <option :value="24">24</option>
            <option :value="48">48</option>
            <option :value="96">96</option>
          </select>
        </div>

        <div class="filter-item">
          <label class="filter-label">PLATFORM</label>
          <select v-model="filterPlatform">
            <option value="">ALL</option>
            <option v-for="p in allPlatforms" :key="p" :value="p">{{ p }}</option>
          </select>
        </div>

        <div class="filter-item">
          <label class="filter-label">STATUS</label>
          <select v-model="filterStatus">
            <option value="">ALL</option>
            <option v-for="s in ACCOUNT_STATUS_OPTIONS" :key="s.value" :value="s.value">{{ s.label }}</option>
          </select>
        </div>

        <div class="filter-item">
          <label class="filter-label">GROUP</label>
          <select v-model="filterGroup">
            <option value="">ALL</option>
            <option v-for="g in allGroups" :key="g.id" :value="g.id">{{ g.name }}</option>
          </select>
        </div>

        <button class="btn-query" :disabled="loading" @click="onQuery">
          <span class="btn-icon">{{ loading ? '⟳' : '▶' }}</span>
          {{ loading ? 'LOADING' : 'QUERY' }}
        </button>
      </div>

      <div class="toolbar-right">
        <span v-if="lastUpdated" class="updated">
          <span class="pulse-dot"></span>
          {{ lastUpdated }}
        </span>
      </div>
    </div>

    <div v-if="loading" class="state-screen">
      <div class="loader-ring"></div>
      <span class="state-text">FETCHING DATA</span>
    </div>

    <div v-else-if="error" class="state-screen error-state">
      <span class="state-icon">⚠</span>
      <span class="state-text">{{ error }}</span>
    </div>

    <div v-else-if="accountsWithData.length === 0 && lastUpdated === ''" class="state-screen idle-state">
      <span class="state-icon idle-icon">◈</span>
      <span class="state-text">设置筛选条件后点击 QUERY 加载数据</span>
    </div>

    <div v-else-if="accountsWithData.length === 0" class="state-screen">
      <span class="state-text">NO DATA</span>
    </div>

    <div v-else class="grid">
      <div
        v-for="chart in chartOptions"
        :key="chart.key"
        class="card"
        :style="{ '--signal-color': getSignalColor(chart.successRateNum) }"
      >
        <div class="signal-bar"></div>
        <div class="card-header">
          <div class="header-left">
            <span class="acct-name">{{ chart.name }}</span>
            <span class="model-tag">{{ chart.model }}</span>
          </div>
          <div class="header-tags">
            <span class="badge" :class="chart.lastStatus === 'success' ? 'badge-ok' : 'badge-fail'">
              {{ chart.lastStatus === 'success' ? '✓ OK' : '✗ FAIL' }}
            </span>
            <span class="sched-badge" :class="chart.schedulable ? 'sched-ok' : 'sched-off'">
              {{ chart.schedulable ? 'SCH:ON' : 'SCH:OFF' }}
            </span>
            <span
              v-if="chart.scheduleTag"
              class="sched-badge sched-has-tip"
              :class="chart.scheduleTag.cls"
            >
              {{ chart.scheduleTag.label }}
              <span class="sched-tip" v-html="chart.scheduleTag.tip.replace(/\n/g, '<br/>')"></span>
            </span>
          </div>
          <div class="header-right">
            <span class="rate" :style="{ color: getSignalColor(chart.successRateNum) }">
              {{ chart.successRate }}
            </span>
            <span class="priority">P{{ chart.priority }}</span>
          </div>
        </div>
        <VChart class="chart" :option="chart.option" autoresize />
      </div>
    </div>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

/* ── CSS Variables ── */
:root {
  --bg-base: #060d18;
  --bg-surface: #0a1628;
  --bg-card: #0d1f35;
  --bg-toolbar: #080f1e;
  --border: #112240;
  --border-bright: #1e3a5f;
  --text-primary: #cdd9e5;
  --text-secondary: #5a7a9a;
  --text-dim: #2d4a6a;
  --accent-blue: #0ea5e9;
  --accent-cyan: #22d3ee;
  --accent-amber: #f59e0b;
  --accent-red: #f87171;
  --accent-green: #22d3ee;
  --font-mono: 'JetBrains Mono', 'Courier New', monospace;
  --font-sans: 'IBM Plex Sans', sans-serif;
}

/* ── Base ── */
.page {
  min-height: 100vh;
  background: var(--bg-base);
  color: var(--text-primary);
  font-family: var(--font-sans);
  position: relative;
  padding-bottom: 60px;
}

/* ── Scanlines overlay ── */
.scanlines {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 0, 0, 0.15) 2px,
    rgba(0, 0, 0, 0.15) 4px
  );
  opacity: 0.4;
}

/* ── Toolbar ── */
.toolbar {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 0 32px;
  height: 64px;
  background: var(--bg-toolbar);
  border-bottom: 1px solid var(--border-bright);
  box-shadow: 0 1px 0 rgba(14, 165, 233, 0.08), 0 4px 24px rgba(0, 0, 0, 0.6);
  flex-wrap: wrap;
}

.title-block {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-shrink: 0;
}

.title-accent {
  color: var(--accent-cyan);
  font-size: 20px;
  line-height: 1;
}

.title {
  font-family: var(--font-mono);
  font-size: 15px;
  font-weight: 700;
  color: #e2eaf3;
  letter-spacing: 0.12em;
}

.title-sub {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 400;
  color: var(--text-dim);
  letter-spacing: 0.08em;
}

.filters {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.filter-label {
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 600;
  color: var(--text-dim);
  letter-spacing: 0.15em;
}

.filter-item select {
  height: 28px;
  padding: 0 10px;
  background: var(--bg-surface);
  border: 1px solid var(--border-bright);
  border-radius: 3px;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 11px;
  cursor: pointer;
  outline: none;
  appearance: none;
  min-width: 80px;
  transition: border-color 0.15s;
}

.filter-item select:focus {
  border-color: var(--accent-blue);
  box-shadow: 0 0 0 1px rgba(14, 165, 233, 0.2);
}

.filter-item select option {
  background: #0a1628;
}

.btn-query {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 16px;
  background: transparent;
  border: 1px solid var(--accent-blue);
  border-radius: 3px;
  color: var(--accent-blue);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.1em;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, box-shadow 0.15s;
  align-self: flex-end;
}

.btn-query:hover:not(:disabled) {
  background: var(--accent-blue);
  color: var(--bg-base);
  box-shadow: 0 0 16px rgba(14, 165, 233, 0.4);
}

.btn-query:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-icon {
  font-size: 12px;
  display: inline-block;
  animation: none;
}

.btn-query:disabled .btn-icon {
  display: inline-block;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.toolbar-right {
  margin-left: auto;
  flex-shrink: 0;
}

.updated {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-secondary);
  letter-spacing: 0.06em;
}

.pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent-cyan);
  animation: pulse 2s ease-in-out infinite;
  flex-shrink: 0;
}

@keyframes pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(34, 211, 238, 0.4); }
  50% { opacity: 0.6; box-shadow: 0 0 0 4px rgba(34, 211, 238, 0); }
}

/* ── State screens ── */
.state-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  min-height: 50vh;
  position: relative;
  z-index: 1;
}

.state-text {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-secondary);
  letter-spacing: 0.15em;
}

.state-icon {
  font-size: 28px;
  color: var(--text-dim);
}

.idle-icon {
  color: var(--accent-blue);
  opacity: 0.5;
  animation: idle-pulse 3s ease-in-out infinite;
}

@keyframes idle-pulse {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 0.7; }
}

.error-state .state-icon { color: var(--accent-red); }
.error-state .state-text { color: var(--accent-red); }

.loader-ring {
  width: 32px;
  height: 32px;
  border: 2px solid var(--border-bright);
  border-top-color: var(--accent-cyan);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* ── Grid ── */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(460px, 1fr));
  gap: 1px;
  padding: 24px 32px 0;
  max-width: 1680px;
  margin: 0 auto;
  position: relative;
  z-index: 1;
}

/* ── Card ── */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 2px;
  overflow: visible;
  position: relative;
  transition: border-color 0.2s;
  display: flex;
  flex-direction: column;
}

.card:hover {
  border-color: var(--border-bright);
}

/* 左侧活体信号条 */
.signal-bar {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--signal-color, var(--accent-cyan));
  border-radius: 2px 0 0 2px;
  opacity: 0.8;
  box-shadow: 1px 0 8px var(--signal-color, var(--accent-cyan));
}

/* ── Card Header ── */
.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 14px 9px 18px;
  border-bottom: 1px solid var(--border);
  overflow: visible;
  background: rgba(0, 0, 0, 0.2);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.acct-name {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  color: #d0dce8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  letter-spacing: 0.02em;
}

.model-tag {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--text-dim);
  background: rgba(30, 58, 95, 0.4);
  border: 1px solid var(--border);
  padding: 1px 5px;
  border-radius: 2px;
  white-space: nowrap;
  flex-shrink: 0;
  letter-spacing: 0.04em;
}

.header-tags {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.badge {
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 2px;
  letter-spacing: 0.08em;
}

.badge-ok {
  background: rgba(34, 211, 238, 0.1);
  color: var(--accent-cyan);
  border: 1px solid rgba(34, 211, 238, 0.25);
}

.badge-fail {
  background: rgba(248, 113, 113, 0.1);
  color: var(--accent-red);
  border: 1px solid rgba(248, 113, 113, 0.25);
}

.sched-badge {
  position: relative;
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 600;
  padding: 2px 5px;
  border-radius: 2px;
  cursor: default;
  white-space: nowrap;
  letter-spacing: 0.06em;
}

.sched-has-tip { cursor: pointer; }

.sched-ok {
  background: rgba(34, 211, 238, 0.08);
  color: #0d9488;
  border: 1px solid rgba(34, 211, 238, 0.15);
}

.sched-off {
  background: rgba(30, 58, 95, 0.3);
  color: var(--text-dim);
  border: 1px solid var(--border);
}

.sched-temp {
  background: rgba(245, 158, 11, 0.1);
  color: var(--accent-amber);
  border: 1px solid rgba(245, 158, 11, 0.25);
}

.sched-ratelimit {
  background: rgba(251, 146, 60, 0.1);
  color: #fb923c;
  border: 1px solid rgba(251, 146, 60, 0.25);
}

.sched-overload {
  background: rgba(248, 113, 113, 0.1);
  color: var(--accent-red);
  border: 1px solid rgba(248, 113, 113, 0.25);
}

/* Tooltip */
.sched-tip {
  display: none;
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 200;
  background: #060d18;
  border: 1px solid var(--border-bright);
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 400;
  line-height: 1.8;
  padding: 8px 12px;
  border-radius: 3px;
  white-space: nowrap;
  pointer-events: none;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(14, 165, 233, 0.1);
  min-width: 200px;
}

.sched-tip::before {
  content: '';
  position: absolute;
  top: -4px;
  left: 8px;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-bottom: 4px solid var(--border-bright);
}

.sched-has-tip:hover .sched-tip { display: block; }

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
  flex-shrink: 0;
}

.rate {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.priority {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--text-dim);
  letter-spacing: 0.1em;
}

/* ── Chart ── */
.chart {
  height: 160px;
  width: 100%;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .toolbar { padding: 12px 16px; height: auto; gap: 12px; }
  .grid { grid-template-columns: 1fr; padding: 16px; gap: 8px; }
  .title-sub { display: none; }
}
</style>
