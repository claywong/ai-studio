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

// 筛选条件
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

    // 收集筛选选项（基于全量账号）
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

    // 按筛选条件过滤账号
    if (filterPlatform.value) accounts = accounts.filter((a) => a.platform === filterPlatform.value)
    if (filterStatus.value) accounts = accounts.filter((a) => a.status === filterStatus.value)
    if (filterGroup.value) {
      const gid = Number(filterGroup.value)
      accounts = accounts.filter((a) => a.groups.some((g) => g.id === gid))
    }

    // 最多取前20个
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

// 初始化只加载筛选选项，不加载图表数据
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
      axisPointer: { type: 'cross' },
      formatter(params: { seriesName: string; value: number | null; name: string }[]) {
        const time = params[0]?.name ?? ''
        const lines = params.map((p) => {
          if (p.seriesName === '可用性') {
            return `${p.seriesName}: ${p.value === 1 ? '✓ 成功' : '✗ 失败'}`
          }
          return `${p.seriesName}: ${p.value != null ? p.value + 'ms' : '-'}`
        })
        return `${time}<br/>${lines.join('<br/>')}`
      },
    },
    grid: { top: 16, right: 16, bottom: 24, left: 50 },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: { fontSize: 10, color: '#94a3b8', interval: Math.floor(times.length / 6) },
      axisLine: { lineStyle: { color: '#e5e9f2' } },
    },
    yAxis: [
      {
        type: 'value',
        name: '延迟(ms)',
        min: 0,
        max: 60000,
        nameTextStyle: { fontSize: 10, color: '#94a3b8' },
        axisLabel: { fontSize: 10, color: '#94a3b8', formatter: (v: number) => v >= 1000 ? (v / 1000) + 's' : v },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
      },
      { type: 'value', min: 0, max: 1, show: false },
    ],
    series: [
      {
        name: '延迟',
        type: 'line',
        data: latencyData,
        yAxisIndex: 0,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#3b82f6', width: 1.5 },
        areaStyle: { color: 'rgba(59,130,246,0.08)' },
        connectNulls: false,
      },
      {
        name: '可用性',
        type: 'line',
        data: successData,
        yAxisIndex: 1,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 0 },
        itemStyle: {
          color(params: { value: number }) {
            return params.value === 1 ? '#16a34a' : '#dc2626'
          },
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
    lastStatus: item.results[0]?.status ?? 'unknown',
    option: buildChartOption(item),
  })),
)

function calcSuccessRate(results: TestResult[]) {
  if (!results.length) return '-'
  const ok = results.filter((r) => r.status === 'success').length
  return ((ok / results.length) * 100).toFixed(0) + '%'
}

function startAutoRefresh() {
  if (timer) clearInterval(timer)
  timer = setInterval(() => void load(), 5 * 60 * 1000)
}

// 初始只加载筛选选项
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
    <div class="toolbar">
      <span class="title">账号监控折线图</span>

      <div class="filter-item">
        <span class="filter-label">条数</span>
        <select v-model="limit">
          <option :value="24">24条</option>
          <option :value="48">48条</option>
          <option :value="96">96条</option>
        </select>
      </div>

      <div class="filter-item">
        <span class="filter-label">平台</span>
        <select v-model="filterPlatform">
          <option value="">全部</option>
          <option v-for="p in allPlatforms" :key="p" :value="p">{{ p }}</option>
        </select>
      </div>

      <div class="filter-item">
        <span class="filter-label">状态</span>
        <select v-model="filterStatus">
          <option value="">全部状态</option>
          <option v-for="s in ACCOUNT_STATUS_OPTIONS" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
      </div>

      <div class="filter-item">
        <span class="filter-label">分组</span>
        <select v-model="filterGroup">
          <option value="">全部</option>
          <option v-for="g in allGroups" :key="g.id" :value="g.id">{{ g.name }}</option>
        </select>
      </div>

      <button class="btn-query" :disabled="loading" @click="onQuery">
        {{ loading ? '加载中…' : '查询' }}
      </button>
      <span v-if="lastUpdated" class="updated">更新于 {{ lastUpdated }}</span>
    </div>

    <div v-if="loading" class="loading">加载中…</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="accountsWithData.length === 0 && lastUpdated === ''" class="empty">
      设置筛选条件后点击「查询」加载数据
    </div>
    <div v-else-if="accountsWithData.length === 0" class="empty">没有符合条件的账号</div>

    <div v-else class="grid">
      <div v-for="chart in chartOptions" :key="chart.key" class="card">
        <div class="card-header">
          <span class="acct-name">{{ chart.name }}</span>
          <span class="badge" :class="chart.lastStatus === 'success' ? 'ok' : 'fail'">
            {{ chart.lastStatus === 'success' ? '正常' : '失败' }}
          </span>
          <span class="model-tag">{{ chart.model }}</span>
          <span class="rate">成功率 {{ chart.successRate }}</span>
          <span class="priority">优先级 {{ chart.priority }}</span>
        </div>
        <VChart class="chart" :option="chart.option" autoresize />
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 0 0 40px;
  background: #f5f7fb;
  color: #0f172a;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 40px;
  background: #ffffff;
  border-bottom: 1px solid #e5e9f2;
  flex-wrap: wrap;
}

.title { font-size: 22px; font-weight: 700; color: #0f172a; margin-right: 8px; }

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.filter-label {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  line-height: 1;
}

.filter-item select {
  height: 30px;
  padding: 0 8px;
  border: 1px solid #d7deea;
  border-radius: 6px;
  color: #0f172a;
  background: #ffffff;
  font-size: 12px;
  cursor: pointer;
}

.btn-query {
  height: 32px;
  padding: 0 18px;
  border: 1px solid #2563eb;
  border-radius: 6px;
  color: #ffffff;
  background: #2563eb;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  align-self: flex-end;
}

.btn-query:hover:not(:disabled) { background: #1d4ed8; }
.btn-query:disabled { opacity: 0.6; cursor: not-allowed; }

.updated { font-size: 12px; color: #64748b; margin-left: auto; align-self: center; }

.loading, .error, .empty { padding: 80px; text-align: center; color: #64748b; font-size: 14px; }
.error { color: #dc2626; }
.empty { color: #94a3b8; }

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(480px, 1fr));
  gap: 16px;
  padding: 24px 40px 0;
  max-width: 1600px;
  margin: 0 auto;
}

.card {
  background: #ffffff;
  border: 1px solid #e5e9f2;
  border-radius: 10px;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-bottom: 1px solid #f1f5f9;
  flex-wrap: wrap;
}

.acct-name { font-size: 13px; font-weight: 700; color: #0f172a; }

.badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 10px;
}

.badge.ok { background: #dcfce7; color: #16a34a; }
.badge.fail { background: #fee2e2; color: #dc2626; }

.model-tag {
  font-size: 10px;
  color: #64748b;
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
}

.rate { font-size: 11px; color: #475569; margin-left: auto; }
.priority { font-size: 11px; color: #94a3b8; }

.chart { height: 160px; width: 100%; }
</style>
