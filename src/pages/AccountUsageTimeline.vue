<script setup lang="ts">
import { use } from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { onUnmounted, ref, computed } from 'vue'
import { api } from '../api/client'
import { fetchAccountUsageTimeline, type AccountTimeline } from '../api/accountUsageTimeline'

use([CanvasRenderer, LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent])

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

const HOURS_OPTIONS = [
  { value: 1, label: '1小时' },
  { value: 3, label: '3小时' },
  { value: 6, label: '6小时' },
  { value: 24, label: '24小时' },
]

const loading = ref(false)
const error = ref('')
const lastUpdated = ref('')
const timelines = ref<AccountTimeline[]>([])
const allPlatforms = ref<string[]>([])
const allGroups = ref<{ id: number; name: string }[]>([])

const hours = ref(1)
const filterPlatform = ref('')
const filterStatus = ref('')
const filterGroup = ref('')

let timer: ReturnType<typeof setInterval> | null = null

function fmtBucketTime(iso: string): string {
  const d = new Date(iso)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const HH = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${mm}-${dd} ${HH}:${min}`
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

    const target = accounts.slice(0, 20)
    if (target.length === 0) {
      timelines.value = []
      lastUpdated.value = new Date().toLocaleTimeString()
      return
    }

    const result = await fetchAccountUsageTimeline(
      target.map((a) => a.id),
      hours.value,
    )
    timelines.value = result.data
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

function buildChartOption(item: AccountTimeline) {
  const sorted = [...item.buckets].sort((a, b) => a.time.localeCompare(b.time))
  const times = sorted.map((b) => fmtBucketTime(b.time))
  const ttftData = sorted.map((b) => b.avg_ttft_ms ?? null)
  const tpsData = sorted.map((b) => b.tokens_per_second ?? null)
  const errData = sorted.map((b) => b.error_count)
  const reqData = sorted.map((b) => b.request_count)

  const labelInterval = Math.max(0, Math.floor(times.length / 5) - 1)

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter(params: { seriesName: string; value: number | null; name: string }[]) {
        const time = params[0]?.name ?? ''
        const lines = params.map((p) => {
          if (p.value == null) return `${p.seriesName}: -`
          if (p.seriesName === 'TTFT p90') return `TTFT p90: ${p.value}ms`
          if (p.seriesName === 'Token/s') return `Token/s: ${p.value.toFixed(1)}`
          if (p.seriesName === '请求数') return `请求数: ${p.value}`
          return `错误: ${p.value}`
        })
        return `${time}<br/>${lines.join('<br/>')}`
      },
    },
    legend: {
      data: ['TTFT p90', 'Token/s', '请求数', '错误'],
      top: 0,
      right: 8,
      itemWidth: 12,
      itemHeight: 8,
      textStyle: { fontSize: 10, color: '#64748b' },
    },
    grid: { top: 24, right: 65, bottom: 24, left: 58 },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: { fontSize: 9, color: '#94a3b8', interval: labelInterval },
      axisLine: { lineStyle: { color: '#e5e9f2' } },
    },
    yAxis: [
      {
        type: 'value',
        name: 'ms',
        min: 0,
        max: 20000,
        nameTextStyle: { fontSize: 9, color: '#94a3b8' },
        axisLabel: { fontSize: 9, color: '#94a3b8' },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
      },
      {
        type: 'value',
        name: 'T/s',
        min: 0,
        max: 50,
        position: 'right',
        nameTextStyle: { fontSize: 9, color: '#94a3b8' },
        axisLabel: { fontSize: 9, color: '#94a3b8' },
        splitLine: { show: false },
      },
      {
        type: 'value',
        min: 0,
        max: 100,
        show: false,
      },
      {
        type: 'value',
        min: 0,
        max: 10,
        show: false,
      },
    ],
    series: [
      {
        name: 'TTFT p90',
        type: 'line',
        yAxisIndex: 0,
        data: ttftData,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#3b82f6', width: 1.5 },
        areaStyle: { color: 'rgba(59,130,246,0.06)' },
        connectNulls: false,
      },
      {
        name: 'Token/s',
        type: 'line',
        yAxisIndex: 1,
        data: tpsData,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#10b981', width: 1.5 },
        areaStyle: { color: 'rgba(16,185,129,0.06)' },
        connectNulls: false,
      },
      {
        name: '请求数',
        type: 'line',
        yAxisIndex: 2,
        data: reqData,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#a855f7', width: 1.5 },
        areaStyle: { color: 'rgba(168,85,247,0.06)' },
        connectNulls: false,
      },
      {
        name: '错误',
        type: 'bar',
        yAxisIndex: 3,
        data: errData,
        barMaxWidth: 6,
        itemStyle: { color: 'rgba(239,68,68,0.8)' },
      },
    ],
  }
}

function calcSummary(item: AccountTimeline): { avgTtft: string; avgTps: string; totalErrors: number; totalRequests: number } {
  const buckets = item.buckets
  const ttftVals = buckets.map((b) => b.avg_ttft_ms).filter((v): v is number => v != null && v > 0)
  const tpsVals = buckets.map((b) => b.tokens_per_second).filter((v): v is number => v != null)
  const totalErrors = buckets.reduce((s, b) => s + b.error_count, 0)
  const totalRequests = buckets.reduce((s, b) => s + b.request_count, 0)

  const avgTtft = ttftVals.length > 0
    ? `${Math.round(ttftVals.reduce((s, v) => s + v, 0) / ttftVals.length)}ms`
    : '-'
  const avgTps = tpsVals.length > 0
    ? `${(tpsVals.reduce((s, v) => s + v, 0) / tpsVals.length).toFixed(1)}`
    : '-'

  return { avgTtft, avgTps, totalErrors, totalRequests }
}

const chartOptions = computed(() =>
  timelines.value.map((item) => ({
    key: item.account_id,
    name: item.account_name,
    summary: calcSummary(item),
    option: buildChartOption(item),
  })),
)

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
    <div class="toolbar">
      <span class="title">账号请求监控</span>

      <div class="filter-item">
        <span class="filter-label">时间范围</span>
        <select v-model="hours">
          <option v-for="h in HOURS_OPTIONS" :key="h.value" :value="h.value">{{ h.label }}</option>
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
    <div v-else-if="chartOptions.length === 0 && lastUpdated === ''" class="empty">
      设置筛选条件后点击「查询」加载数据
    </div>
    <div v-else-if="chartOptions.length === 0" class="empty">没有符合条件的账号或暂无请求数据</div>

    <div v-else class="grid">
      <div v-for="chart in chartOptions" :key="chart.key" class="card">
        <div class="card-header">
          <span class="acct-name">{{ chart.name }}</span>
          <span class="stat-tag ttft-tag">TTFT {{ chart.summary.avgTtft }}</span>
          <span class="stat-tag tps-tag">{{ chart.summary.avgTps }} T/s</span>
          <span class="stat-tag req-tag">{{ chart.summary.totalRequests }} 请求</span>
          <span v-if="chart.summary.totalErrors > 0" class="stat-tag err-tag">
            {{ chart.summary.totalErrors }} 错误
          </span>
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

.stat-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 10px;
}

.ttft-tag { background: #dbeafe; color: #1d4ed8; }
.tps-tag  { background: #d1fae5; color: #065f46; }
.req-tag  { background: #f1f5f9; color: #475569; }
.err-tag  { background: #fee2e2; color: #b91c1c; }

.chart { height: 180px; width: 100%; }
</style>
