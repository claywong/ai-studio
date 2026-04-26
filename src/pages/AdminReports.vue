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

// 日期工具
function toDateStr(d: Date) {
  return d.toISOString().slice(0, 10)
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

function toggleGroup(name: string) {
  expandedGroups.value.has(name)
    ? expandedGroups.value.delete(name)
    : expandedGroups.value.add(name)
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
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['Token 数', '成本($)'], textStyle: { color: '#aaa' }, bottom: 0 },
    grid: { left: 70, right: 60, top: 40, bottom: 50 },
    xAxis: {
      type: 'category',
      data: items.map(i => i.date.slice(5)),
      axisLabel: { color: '#888' },
      axisLine: { lineStyle: { color: '#333' } },
    },
    yAxis: [
      {
        type: 'value',
        name: 'Tokens',
        nameTextStyle: { color: '#888' },
        axisLabel: { color: '#888', formatter: (v: number) => v >= 1e9 ? `${(v/1e9).toFixed(1)}B` : v >= 1e6 ? `${(v/1e6).toFixed(0)}M` : `${(v/1e3).toFixed(0)}K` },
        splitLine: { lineStyle: { color: '#222' } },
      },
      {
        type: 'value',
        name: '成本($)',
        nameTextStyle: { color: '#888' },
        axisLabel: { color: '#888', formatter: (v: number) => `$${v.toFixed(0)}` },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: 'Token 数',
        type: 'bar',
        data: items.map(i => i.input_tokens + i.output_tokens),
        itemStyle: { color: '#3b82f6', borderRadius: [3, 3, 0, 0] },
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
      axisLabel: { color: '#888', formatter: (v: number) => v >= 1e9 ? `${(v/1e9).toFixed(1)}B` : v >= 1e6 ? `${(v/1e6).toFixed(0)}M` : `${(v/1e3).toFixed(0)}K` },
      splitLine: { lineStyle: { color: '#222' } },
    },
    yAxis: {
      type: 'category',
      data: top.map(m => m.model).reverse(),
      axisLabel: { color: '#ccc', fontSize: 11 },
      axisLine: { lineStyle: { color: '#333' } },
    },
    series: [{
      type: 'bar',
      data: top.map(m => m.input_tokens + m.output_tokens).reverse(),
      itemStyle: {
        color: (params: { dataIndex: number }) => {
          const colors = ['#3b82f6','#8b5cf6','#10b981','#f59e0b','#ef4444','#06b6d4','#ec4899','#84cc16']
          return colors[params.dataIndex % colors.length]
        },
        borderRadius: [0, 3, 3, 0],
      },
      barMaxWidth: 20,
      label: {
        show: true, position: 'right', color: '#888', fontSize: 11,
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
  const n = accountGroups.value.reduce((s, g) => s + g.input_tokens + g.output_tokens, 0)
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`
  if (n >= 1_000_000)     return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)         return `${(n / 1_000).toFixed(1)}K`
  return String(n)
})

const periodLabel = computed(() => {
  if (startDate.value === endDate.value) return '当日'
  return `${startDate.value.slice(5)} ~ ${endDate.value.slice(5)}`
})

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
      <div>
        <p class="eyebrow">G7E6 AI Studio</p>
        <h1>管理报表</h1>
      </div>
      <div class="header-right">
        <a class="back-link" href="/">返回主站</a>
      </div>
    </header>

    <!-- 时间选择栏 -->
    <div class="date-bar">
      <div class="shortcuts">
        <button
          v-for="s in SHORTCUTS"
          :key="s.label"
          :class="{ active: activeShortcut === s.label }"
          @click="applyShortcut(s)"
        >{{ s.label }}</button>
      </div>
      <div class="date-inputs">
        <input type="date" v-model="startDate" :max="endDate" @change="onDateChange" />
        <span class="date-sep">—</span>
        <input type="date" v-model="endDate" :min="startDate" :max="today()" @change="onDateChange" />
      </div>
    </div>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <div v-if="loading" class="loading-overlay">
      <div class="spinner-ring"></div>
      <span>加载数据中...</span>
    </div>

    <div v-else class="reports-body">
      <!-- 总览卡片 -->
      <section class="cards-row">
        <div class="stat-card">
          <span class="card-label">正常账号</span>
          <span class="card-value green">{{ overview?.normal_accounts ?? '—' }}</span>
        </div>
        <div class="stat-card">
          <span class="card-label">周期 Token 数</span>
          <span class="card-value">{{ totalTokens }}</span>
        </div>
        <div class="stat-card">
          <span class="card-label">{{ periodLabel }} 活跃用户</span>
          <span class="card-value blue">{{ overview?.period_active_users ?? '—' }}</span>
        </div>
        <div class="stat-card">
          <span class="card-label">周期总请求</span>
          <span class="card-value">{{ totalRequests }}</span>
        </div>
        <div class="stat-card">
          <span class="card-label">周期总成本</span>
          <span class="card-value yellow">${{ totalCost }}</span>
        </div>
      </section>

      <!-- 图表区 -->
      <section class="charts-row">
        <div class="chart-card wide">
          <h2>每日 Token & 成本</h2>
          <VChart class="chart" :option="trendOption" autoresize />
        </div>
        <div class="chart-card">
          <h2>模型 Token 分布</h2>
          <VChart class="chart" :option="modelOption" autoresize />
        </div>
      </section>

      <!-- 账号分组表格 -->
      <section class="table-section">
        <h2>账号分组统计（按名称前缀）</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th class="col-name">账号组</th>
                <th class="col-num">账号数</th>
                <th class="col-num">请求数</th>
                <th class="col-num">输入 Tokens</th>
                <th class="col-num">输出 Tokens</th>
                <th class="col-num">成本($)</th>
                <th class="col-date">最后使用</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="group in accountGroups" :key="group.group_name">
                <tr class="group-row" @click="toggleGroup(group.group_name)">
                  <td class="col-name">
                    <span class="expand-icon">{{ expandedGroups.has(group.group_name) ? '▾' : '▸' }}</span>
                    {{ group.group_name }}
                    <span class="badge">{{ group.account_count }}</span>
                  </td>
                  <td class="col-num">{{ group.account_count }}</td>
                  <td class="col-num">{{ group.total_requests.toLocaleString() }}</td>
                  <td class="col-num dim">{{ fmt(group.input_tokens) }}</td>
                  <td class="col-num dim">{{ fmt(group.output_tokens) }}</td>
                  <td class="col-num yellow">${{ group.total_cost.toFixed(2) }}</td>
                  <td class="col-date dim">{{ fmtDate(group.last_used_at) }}</td>
                </tr>
                <template v-if="expandedGroups.has(group.group_name)">
                  <tr v-for="acc in group.accounts" :key="acc.id" class="account-row">
                    <td class="col-name indent">
                      <span class="status-dot" :class="acc.status === 'active' ? 'active' : 'error'"></span>
                      {{ acc.name }}
                      <span class="platform-tag">{{ acc.platform }}</span>
                    </td>
                    <td class="col-num dim">—</td>
                    <td class="col-num">{{ acc.requests.toLocaleString() }}</td>
                    <td class="col-num dim">—</td>
                    <td class="col-num dim">—</td>
                    <td class="col-num">${{ Number(acc.total_cost).toFixed(2) }}</td>
                    <td class="col-date dim">{{ fmtDate(acc.last_used_at) }}</td>
                  </tr>
                </template>
              </template>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.reports-shell {
  min-height: 100vh;
  background: #0a0a0f;
  color: #e2e8f0;
  padding: 0 0 48px;
}

.reports-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 28px 40px 20px;
  border-bottom: 1px solid #1e1e2e;
}

.eyebrow {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #64748b;
  margin: 0 0 4px;
}

.reports-header h1 { font-size: 22px; font-weight: 600; margin: 0; }

.back-link { font-size: 13px; color: #64748b; text-decoration: none; }
.back-link:hover { color: #e2e8f0; }

/* 时间选择栏 */
.date-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 40px;
  background: #0d0d14;
  border-bottom: 1px solid #1a1a28;
  flex-wrap: wrap;
}

.shortcuts {
  display: flex;
  gap: 4px;
}

.shortcuts button {
  padding: 5px 12px;
  background: transparent;
  border: 1px solid #1e1e2e;
  border-radius: 6px;
  color: #64748b;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s;
  white-space: nowrap;
}

.shortcuts button:hover { border-color: #334155; color: #94a3b8; }
.shortcuts button.active { background: #1e293b; border-color: #334155; color: #e2e8f0; }

.date-inputs {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.date-sep { color: #475569; font-size: 13px; }

.date-inputs input[type="date"] {
  background: #111118;
  border: 1px solid #1e1e2e;
  border-radius: 6px;
  color: #e2e8f0;
  padding: 5px 10px;
  font-size: 13px;
  outline: none;
  cursor: pointer;
}

.date-inputs input[type="date"]:focus { border-color: #334155; }
.date-inputs input[type="date"]::-webkit-calendar-picker-indicator { filter: invert(0.5); cursor: pointer; }

.error-banner {
  margin: 16px 40px;
  padding: 12px 16px;
  background: #2d1a1a;
  border: 1px solid #5c2626;
  border-radius: 8px;
  color: #f87171;
  font-size: 13px;
}

.loading-overlay {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 80px 0;
  color: #64748b;
}

.reports-body { padding: 0 40px; }

/* 卡片 */
.cards-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin: 24px 0;
}

.stat-card {
  background: #111118;
  border: 1px solid #1e1e2e;
  border-radius: 10px;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.card-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #475569;
}

.card-value {
  font-size: 26px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.green  { color: #22c55e; }
.yellow { color: #f59e0b; }
.blue   { color: #3b82f6; }
.dim    { color: #64748b; }

/* 图表 */
.charts-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}

.chart-card {
  background: #111118;
  border: 1px solid #1e1e2e;
  border-radius: 10px;
  padding: 20px;
}

.chart-card h2 {
  font-size: 13px;
  font-weight: 500;
  color: #94a3b8;
  margin: 0 0 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.chart { height: 240px; width: 100%; }

/* 表格 */
.table-section {
  background: #111118;
  border: 1px solid #1e1e2e;
  border-radius: 10px;
  padding: 20px;
}

.table-section h2 {
  font-size: 13px;
  font-weight: 500;
  color: #94a3b8;
  margin: 0 0 16px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.table-wrap { overflow-x: auto; }

table { width: 100%; border-collapse: collapse; font-size: 13px; }

th {
  text-align: left;
  padding: 8px 12px;
  color: #475569;
  font-weight: 500;
  border-bottom: 1px solid #1e1e2e;
  white-space: nowrap;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.col-num  { text-align: right; }
.col-date { text-align: right; white-space: nowrap; }
.col-name { min-width: 180px; }

.group-row { cursor: pointer; transition: background 0.1s; }
.group-row:hover { background: #151520; }
.group-row td { padding: 10px 12px; border-bottom: 1px solid #1a1a28; font-weight: 500; }

.account-row td {
  padding: 7px 12px;
  background: #0d0d15;
  border-bottom: 1px solid #141420;
  color: #94a3b8;
  font-size: 12px;
}

.expand-icon { display: inline-block; width: 14px; color: #475569; font-size: 11px; }

.badge {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  background: #1e293b;
  border-radius: 10px;
  font-size: 10px;
  color: #64748b;
  vertical-align: middle;
}

.indent { padding-left: 28px !important; }

.status-dot {
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}

.status-dot.active { background: #22c55e; }
.status-dot.error  { background: #ef4444; }

.platform-tag {
  margin-left: 6px;
  padding: 1px 5px;
  background: #1e293b;
  border-radius: 4px;
  font-size: 10px;
  color: #64748b;
}

@media (max-width: 1200px) {
  .cards-row { grid-template-columns: repeat(3, 1fr); }
  .charts-row { grid-template-columns: 1fr; }
}

@media (max-width: 768px) {
  .reports-header { padding: 20px; }
  .date-bar { padding: 12px 16px; }
  .reports-body { padding: 0 16px; }
  .cards-row { grid-template-columns: repeat(2, 1fr); }
}
</style>
