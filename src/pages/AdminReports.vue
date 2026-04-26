<script setup lang="ts">
import { use } from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { computed, onMounted, ref } from 'vue'
import {
  fetchAccounts, fetchModels, fetchOverview, fetchTrend,
  type AccountGroup, type DateRange, type ModelItem, type OverviewData, type TrendData,
} from '../api/adminReports'

use([CanvasRenderer, LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent])

function pad2(n: number) {
  return String(n).padStart(2, '0')
}

function toDateStr(d: Date) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

function daysAgo(n: number) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return toDateStr(d)
}

function today() { return toDateStr(new Date()) }

const SHORTCUTS = [
  { label: '今天',  start: () => today(),     end: () => today() },
  { label: '近7天', start: () => daysAgo(6),  end: () => today() },
  { label: '近15天',start: () => daysAgo(14), end: () => today() },
  { label: '近30天',start: () => daysAgo(29), end: () => today() },
  { label: '近60天',start: () => daysAgo(59), end: () => today() },
  { label: '近90天',start: () => daysAgo(89), end: () => today() },
]

const startDate = ref(daysAgo(29))
const endDate   = ref(today())
const activeShortcut = ref('近30天')

function applyShortcut(s: typeof SHORTCUTS[0]) {
  startDate.value    = s.start()
  endDate.value      = s.end()
  activeShortcut.value = s.label
  void loadAll()
}

function onDateChange() {
  activeShortcut.value = ''
  void loadAll()
}

const range = computed<DateRange>(() => ({ start: startDate.value, end: endDate.value }))

// 数据
const loading = ref(true)
const error   = ref('')
const overview      = ref<OverviewData | null>(null)
const trendData     = ref<TrendData | null>(null)
const modelsData    = ref<ModelItem[]>([])
const accountGroups = ref<AccountGroup[]>([])
const expandedGroups = ref<Set<string>>(new Set())
const lastUpdatedAt = ref('')

function toggleGroup(name: string) {
  const next = new Set(expandedGroups.value)
  if (next.has(name)) {
    next.delete(name)
  } else {
    next.add(name)
  }
  expandedGroups.value = next
}

function isGroupExpanded(name: string) {
  return expandedGroups.value.has(name)
}

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [ov, tr, md, ac] = await Promise.all([
      fetchOverview(range.value),
      fetchTrend(range.value),
      fetchModels(range.value),
      fetchAccounts(range.value),
    ])
    overview.value      = ov
    trendData.value     = tr
    modelsData.value    = md.models ?? []
    accountGroups.value = ac
    lastUpdatedAt.value = new Date().toISOString()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    error.value = err.response?.data?.detail ?? err.message ?? '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)

// 趋势图
const trendOption = computed(() => {
  const items = trendData.value?.trend ?? []
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line', lineStyle: { color: '#cbd5e1' } },
      backgroundColor: '#ffffff',
      borderColor: '#e2e8f0',
      textStyle: { color: '#0f172a' },
    },
    legend: { data: ['Token 数', '成本($)'], textStyle: { color: '#64748b' }, bottom: 0 },
    grid: { left: 64, right: 54, top: 40, bottom: 48 },
    xAxis: {
      type: 'category',
      data: items.map(i => i.date.slice(5)),
      axisLabel: { color: '#64748b' },
      axisLine: { lineStyle: { color: '#dbe3ef' } },
      axisTick: { show: false },
    },
    yAxis: [
      {
        type: 'value',
        name: 'Tokens',
        nameTextStyle: { color: '#64748b' },
        axisLabel: { color: '#64748b', formatter: (v: number) => v >= 1e9 ? `${(v/1e9).toFixed(1)}B` : v >= 1e6 ? `${(v/1e6).toFixed(0)}M` : `${(v/1e3).toFixed(0)}K` },
        splitLine: { lineStyle: { color: '#eef2f7' } },
      },
      {
        type: 'value',
        name: '成本($)',
        nameTextStyle: { color: '#64748b' },
        axisLabel: { color: '#64748b', formatter: (v: number) => `$${v.toFixed(0)}` },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: 'Token 数',
        type: 'bar',
        data: items.map(i => i.input_tokens + i.output_tokens),
        itemStyle: { color: '#2563eb', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 32,
      },
      {
        name: '成本($)',
        type: 'line',
        yAxisIndex: 1,
        data: items.map(i => Number(i.actual_cost.toFixed(2))),
        smooth: true,
        lineStyle: { color: '#f59e0b', width: 2 },
        itemStyle: { color: '#f59e0b' },
        symbol: 'circle',
        symbolSize: 5,
      },
    ],
  }
})

// 模型分布图
const modelOption = computed(() => {
  const top = [...modelsData.value]
    .sort((a, b) => (b.input_tokens + b.output_tokens) - (a.input_tokens + a.output_tokens))
    .slice(0, 8)
  const costMap = Object.fromEntries(top.map(m => [m.model, m.actual_cost]))
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#ffffff',
      borderColor: '#e2e8f0',
      textStyle: { color: '#0f172a' },
      formatter: (params: { name: string; value: number }[]) => {
        const p = params[0]
        const cost = costMap[p.name] ?? 0
        const v = p.value >= 1e9 ? `${(p.value/1e9).toFixed(2)}B` : p.value >= 1e6 ? `${(p.value/1e6).toFixed(1)}M` : `${(p.value/1e3).toFixed(1)}K`
        return `${p.name}<br/>Tokens: ${v}<br/>成本: $${Number(cost).toFixed(2)}`
      },
    },
    grid: { left: 160, right: 60, top: 20, bottom: 20 },
    xAxis: {
      type: 'value',
      axisLabel: { color: '#64748b', formatter: (v: number) => v >= 1e9 ? `${(v/1e9).toFixed(1)}B` : v >= 1e6 ? `${(v/1e6).toFixed(0)}M` : `${(v/1e3).toFixed(0)}K` },
      splitLine: { lineStyle: { color: '#eef2f7' } },
    },
    yAxis: {
      type: 'category',
      data: top.map(m => m.model).reverse(),
      axisLabel: { color: '#334155', fontSize: 11 },
      axisLine: { lineStyle: { color: '#dbe3ef' } },
      axisTick: { show: false },
    },
    series: [{
      type: 'bar',
      data: top.map(m => m.input_tokens + m.output_tokens).reverse(),
      itemStyle: {
        color: (params: { dataIndex: number }) => {
          const colors = ['#2563eb', '#16a34a', '#f59e0b', '#dc2626', '#0891b2', '#7c3aed', '#db2777', '#65a30d']
          return colors[params.dataIndex % colors.length]
        },
        borderRadius: [0, 3, 3, 0],
      },
      barMaxWidth: 20,
      label: {
        show: true, position: 'right', color: '#64748b', fontSize: 11,
        formatter: (p: { value: number }) => p.value >= 1e9 ? `${(p.value/1e9).toFixed(2)}B` : p.value >= 1e6 ? `${(p.value/1e6).toFixed(1)}M` : `${(p.value/1e3).toFixed(1)}K`,
      },
    }],
  }
})

const totalCost = computed(() =>
  accountGroups.value.reduce((s, g) => s + g.total_cost, 0).toFixed(2),
)
const totalRequests = computed(() =>
  accountGroups.value.reduce((s, g) => s + g.total_requests, 0).toLocaleString(),
)
const totalTokens = computed(() => {
  const n = accountGroups.value.reduce((s, g) => s + g.input_tokens + g.output_tokens + (g.cache_creation_tokens ?? 0) + (g.cache_read_tokens ?? 0), 0)
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`
  if (n >= 1_000_000)     return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)         return `${(n / 1_000).toFixed(1)}K`
  return String(n)
})

const periodLabel = computed(() => {
  if (startDate.value === endDate.value) return '当日'
  return `${startDate.value.slice(5)} ~ ${endDate.value.slice(5)}`
})
const isInitialLoading = computed(() =>
  loading.value && !overview.value && !trendData.value && accountGroups.value.length === 0,
)
const hasTrendData = computed(() => (trendData.value?.trend ?? []).length > 0)
const hasModelData = computed(() => modelsData.value.length > 0)
const hasAccountData = computed(() => accountGroups.value.length > 0)

function fmt(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}
function fmtDate(s: string | null) {
  if (!s) return '—'
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(s))
}
</script>

<template>
  <div class="reports-shell">
    <header class="reports-header">
      <div class="header-copy">
        <p class="eyebrow">G7E6 AI Studio</p>
        <h1>管理报表</h1>
        <span>账号、请求、Token 与成本概览</span>
      </div>
      <div class="header-actions">
        <span v-if="lastUpdatedAt" class="updated-at">更新时间 {{ fmtDate(lastUpdatedAt) }}</span>
        <button class="refresh-button" type="button" :disabled="loading" @click="loadAll">
          {{ loading ? '刷新中' : '刷新' }}
        </button>
        <a class="back-link" href="/">返回主站</a>
      </div>
    </header>

    <main class="reports-body">
      <section class="filter-panel" aria-label="报表筛选">
        <div class="filter-group">
          <span class="filter-label">时间范围</span>
          <div class="shortcuts">
            <button
              v-for="s in SHORTCUTS"
              :key="s.label"
              type="button"
              :class="{ active: activeShortcut === s.label }"
              @click="applyShortcut(s)"
            >
              {{ s.label }}
            </button>
          </div>
        </div>
        <div class="date-inputs">
          <input v-model="startDate" type="date" :max="endDate" @change="onDateChange">
          <span class="date-sep">至</span>
          <input v-model="endDate" type="date" :min="startDate" :max="today()" @change="onDateChange">
        </div>
      </section>

      <div v-if="error" class="error-banner">{{ error }}</div>

      <section v-if="isInitialLoading" class="loading-panel">
        <div class="spinner-ring"></div>
        <span>加载数据中...</span>
      </section>

      <template v-else>
        <section class="summary-grid" aria-label="报表总览">
          <div class="stat-card success">
            <span class="card-label">正常账号</span>
            <strong>{{ overview?.normal_accounts ?? '—' }}</strong>
          </div>
          <div class="stat-card">
            <span class="card-label">周期 Token 数</span>
            <strong>{{ totalTokens }}</strong>
          </div>
          <div class="stat-card info">
            <span class="card-label">{{ periodLabel }} 活跃用户</span>
            <strong>{{ overview?.period_active_users ?? '—' }}</strong>
          </div>
          <div class="stat-card">
            <span class="card-label">周期总请求</span>
            <strong>{{ totalRequests }}</strong>
          </div>
          <div class="stat-card warning">
            <span class="card-label">周期总成本</span>
            <strong>${{ totalCost }}</strong>
          </div>
        </section>

        <section class="charts-row">
          <div class="section-card wide">
            <div class="section-heading">
              <div>
                <h2>每日 Token & 成本</h2>
                <span>{{ periodLabel }}</span>
              </div>
            </div>
            <VChart v-if="hasTrendData" class="chart" :option="trendOption" autoresize />
            <div v-else class="empty-panel">暂无趋势数据</div>
          </div>
          <div class="section-card">
            <div class="section-heading">
              <div>
                <h2>模型 Token 分布</h2>
                <span>Top 8</span>
              </div>
            </div>
            <VChart v-if="hasModelData" class="chart" :option="modelOption" autoresize />
            <div v-else class="empty-panel">暂无模型数据</div>
          </div>
        </section>

        <section class="section-card table-section">
          <div class="section-heading">
            <div>
              <h2>账号分组统计</h2>
              <span>{{ accountGroups.length }} 个账号组</span>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th class="col-name">账号组</th>
                  <th class="col-num">账号数</th>
                  <th class="col-num">请求数</th>
                  <th class="col-num">总 Tokens</th>
                  <th class="col-num">输入 / 输出</th>
                  <th class="col-num">缓存 创建 / 命中</th>
                  <th class="col-num">成本($)</th>
                  <th class="col-date">最后使用</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!hasAccountData">
                  <td colspan="8">
                    <div class="empty-table">暂无账号分组数据</div>
                  </td>
                </tr>
                <template v-else v-for="group in accountGroups" :key="group.group_name">
                  <tr class="group-row">
                    <td class="col-name">
                      <div class="group-cell">
                        <button
                          class="expand-button"
                          type="button"
                          :aria-expanded="isGroupExpanded(group.group_name)"
                          @click="toggleGroup(group.group_name)"
                        >
                          <span class="expand-caret" :class="{ open: isGroupExpanded(group.group_name) }"></span>
                          <span class="group-name">{{ group.group_name }}</span>
                        </button>
                        <span class="badge">{{ group.account_count }}</span>
                      </div>
                    </td>
                    <td class="col-num">{{ group.account_count }}</td>
                    <td class="col-num">{{ group.total_requests.toLocaleString() }}</td>
                    <td class="col-num">{{ fmt(group.input_tokens + group.output_tokens + (group.cache_creation_tokens ?? 0) + (group.cache_read_tokens ?? 0)) }}</td>
                    <td class="col-num muted">{{ fmt(group.input_tokens) }} / {{ fmt(group.output_tokens) }}</td>
                    <td class="col-num muted">{{ fmt(group.cache_creation_tokens ?? 0) }} / {{ fmt(group.cache_read_tokens ?? 0) }}</td>
                    <td class="col-num cost">${{ group.total_cost.toFixed(2) }}</td>
                    <td class="col-date muted">{{ fmtDate(group.last_used_at) }}</td>
                  </tr>
                  <template v-if="isGroupExpanded(group.group_name)">
                    <tr v-for="acc in group.accounts" :key="acc.id" class="account-row">
                      <td class="col-name account-name">
                        <span class="status-dot" :class="acc.status === 'active' ? 'active' : 'error'"></span>
                        <span>{{ acc.name }}</span>
                        <span class="platform-tag">{{ acc.platform }}</span>
                      </td>
                      <td class="col-num muted">—</td>
                      <td class="col-num">{{ acc.requests.toLocaleString() }}</td>
                      <td class="col-num">{{ fmt(acc.input_tokens + acc.output_tokens + (acc.cache_creation_tokens ?? 0) + (acc.cache_read_tokens ?? 0)) }}</td>
                      <td class="col-num muted">{{ fmt(acc.input_tokens) }} / {{ fmt(acc.output_tokens) }}</td>
                      <td class="col-num muted">{{ fmt(acc.cache_creation_tokens ?? 0) }} / {{ fmt(acc.cache_read_tokens ?? 0) }}</td>
                      <td class="col-num">${{ Number(acc.total_cost).toFixed(2) }}</td>
                      <td class="col-date muted">{{ fmtDate(acc.last_used_at) }}</td>
                    </tr>
                  </template>
                </template>
              </tbody>
            </table>
          </div>
        </section>
      </template>
    </main>
  </div>
</template>

<style scoped>
.reports-shell {
  min-height: 100vh;
  padding: 0 0 40px;
  color: #0f172a;
  background: #f5f7fb;
}

.reports-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 22px 40px;
  background: #ffffff;
  border-bottom: 1px solid #e5e9f2;
}

.header-copy {
  display: grid;
  gap: 4px;
}

.header-copy span {
  color: #64748b;
  font-size: 13px;
}

.eyebrow {
  margin: 0;
  color: #2563eb;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.reports-header h1 {
  margin: 0;
  color: #0f172a;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.updated-at {
  color: #64748b;
  font-size: 12px;
  white-space: nowrap;
}

.refresh-button,
.back-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 32px;
  padding: 0 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
}

.refresh-button {
  border: 1px solid #2563eb;
  color: #ffffff;
  background: #2563eb;
  cursor: pointer;
}

.refresh-button:disabled {
  cursor: not-allowed;
  border-color: #cbd5e1;
  color: #64748b;
  background: #f1f5f9;
}

.back-link {
  border: 1px solid #d7deea;
  color: #334155;
  background: #ffffff;
}

.back-link:hover {
  border-color: #b7c3d7;
  color: #0f172a;
}

.reports-body {
  display: grid;
  max-width: 1440px;
  gap: 16px;
  margin: 0 auto;
  padding: 24px 40px 0;
}

.filter-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
  padding: 14px 16px;
  border: 1px solid #e5e9f2;
  border-radius: 8px;
  background: #ffffff;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  flex-wrap: wrap;
}

.filter-label {
  color: #334155;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}

.shortcuts {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.shortcuts button {
  height: 30px;
  padding: 0 12px;
  border: 1px solid #d7deea;
  border-radius: 6px;
  color: #475569;
  background: #ffffff;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.shortcuts button:hover {
  border-color: #9fb0c8;
  color: #0f172a;
}

.shortcuts button.active {
  border-color: #2563eb;
  color: #ffffff;
  background: #2563eb;
}

.date-inputs {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.date-sep {
  color: #64748b;
  font-size: 13px;
}

.date-inputs input[type="date"] {
  height: 32px;
  border: 1px solid #d7deea;
  border-radius: 6px;
  color: #0f172a;
  background: #ffffff;
  padding: 0 10px;
  font-size: 13px;
  outline: none;
  cursor: pointer;
}

.date-inputs input[type="date"]:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.error-banner {
  padding: 12px 16px;
  background: #fff1f2;
  border: 1px solid #fecdd3;
  border-radius: 8px;
  color: #be123c;
  font-size: 13px;
  font-weight: 600;
}

.loading-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  min-height: 360px;
  justify-content: center;
  border: 1px solid #e5e9f2;
  border-radius: 8px;
  background: #ffffff;
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  padding: 16px;
  border: 1px solid #e5e9f2;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.card-label {
  overflow: hidden;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stat-card strong {
  color: #0f172a;
  font-size: 26px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
  white-space: nowrap;
}

.stat-card.success {
  border-top: 3px solid #16a34a;
}

.stat-card.info {
  border-top: 3px solid #2563eb;
}

.stat-card.warning {
  border-top: 3px solid #f59e0b;
}

.charts-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
}

.section-card {
  padding: 20px;
  border: 1px solid #e5e9f2;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.section-heading div {
  display: grid;
  gap: 4px;
}

.section-heading h2 {
  margin: 0;
  color: #0f172a;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0;
}

.section-heading span {
  color: #64748b;
  font-size: 12px;
}

.chart {
  width: 100%;
  height: 270px;
}

.table-section {
  min-width: 0;
}

.table-wrap {
  overflow-x: auto;
  border: 1px solid #e5e9f2;
  border-radius: 8px;
}

table {
  width: 100%;
  min-width: 940px;
  border-collapse: collapse;
  font-size: 13px;
}

th {
  height: 40px;
  padding: 0 12px;
  border-bottom: 1px solid #e5e9f2;
  color: #64748b;
  background: #f8fafc;
  font-size: 12px;
  font-weight: 700;
  text-align: left;
  white-space: nowrap;
}

.col-num  { text-align: right; }
.col-date { text-align: right; white-space: nowrap; }
.col-name { min-width: 240px; }

td {
  height: 44px;
  padding: 0 12px;
  border-bottom: 1px solid #eef2f7;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

tbody tr:last-child td {
  border-bottom: 0;
}

.group-row:hover td {
  background: #f8fafc;
}

.account-row td {
  height: 38px;
  color: #475569;
  background: #fbfdff;
  font-size: 12px;
}

.group-cell {
  display: inline-flex;
  max-width: 100%;
  align-items: center;
  gap: 8px;
}

.expand-button {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
  border: 0;
  padding: 0;
  color: #0f172a;
  background: transparent;
  cursor: pointer;
  font: inherit;
  font-weight: 700;
}

.expand-button:focus-visible {
  outline: 3px solid rgba(37, 99, 235, 0.18);
  outline-offset: 3px;
  border-radius: 4px;
}

.expand-caret {
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  border-right: 1.5px solid #64748b;
  border-bottom: 1.5px solid #64748b;
  transform: rotate(-45deg);
  transition: transform 0.15s;
}

.expand-caret.open {
  transform: rotate(45deg);
}

.group-name {
  overflow: hidden;
  text-overflow: ellipsis;
}

.badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 999px;
  color: #475569;
  background: #eef2f7;
  font-size: 11px;
  font-weight: 700;
  vertical-align: middle;
}

.account-name {
  padding-left: 38px;
}

.status-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  margin-right: 6px;
  border-radius: 50%;
  vertical-align: middle;
}

.status-dot.active { background: #16a34a; }
.status-dot.error  { background: #ef4444; }

.platform-tag {
  margin-left: 6px;
  padding: 2px 6px;
  border-radius: 4px;
  color: #2563eb;
  background: #eff6ff;
  font-size: 11px;
  font-weight: 700;
}

.muted {
  color: #64748b;
}

.cost {
  color: #b45309;
  font-weight: 700;
}

.empty-panel,
.empty-table {
  display: grid;
  place-items: center;
  min-height: 220px;
  color: #94a3b8;
  font-size: 13px;
  font-weight: 600;
}

.empty-table {
  min-height: 120px;
}

@media (max-width: 1200px) {
  .summary-grid { grid-template-columns: repeat(3, 1fr); }
  .charts-row { grid-template-columns: 1fr; }
}

@media (max-width: 768px) {
  .reports-header {
    align-items: flex-start;
    padding: 18px;
    flex-direction: column;
  }

  .header-actions {
    justify-content: flex-start;
  }

  .reports-body {
    padding: 18px;
  }

  .filter-panel,
  .filter-group,
  .date-inputs {
    align-items: stretch;
    width: 100%;
  }

  .date-inputs input[type="date"] {
    flex: 1 1 140px;
  }

  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .section-card {
    padding: 16px;
  }
}

@media (max-width: 520px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
