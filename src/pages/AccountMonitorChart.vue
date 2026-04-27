<script setup lang="ts">
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { api } from '../api/client'
import { fetchAccountPlans, fetchPlanResults, type AccountWithPlan, type TestResult } from '../api/scheduledMonitor'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

interface AccountItem {
  id: number
  name: string
  priority: number
  status: string
}

const loading = ref(true)
const error = ref('')
const lastUpdated = ref('')
const accountsWithData = ref<AccountWithPlan[]>([])
const limit = ref(48)
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
  try {
    error.value = ''
    const accounts = await fetchAllAccounts()
    // 按优先级升序
    accounts.sort((a, b) => a.priority - b.priority)

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
            plan,
            results: testResults,
          })
        } catch {
          // 单个账号失败不影响其他
        }
      }),
    )

    // 按优先级升序排列
    results.sort((a, b) => a.priority - b.priority)
    accountsWithData.value = results
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

function buildChartOption(item: AccountWithPlan) {
  const sorted = [...item.results].sort(
    (a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime(),
  )

  const times = sorted.map((r) => fmtTime(r.started_at))
  // 成功=1，失败=0
  const successData = sorted.map((r) => (r.status === 'success' ? 1 : 0))
  // 延迟 ms，失败时显示 null
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
        nameTextStyle: { fontSize: 10, color: '#94a3b8' },
        axisLabel: { fontSize: 10, color: '#94a3b8' },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
      },
      {
        type: 'value',
        min: 0,
        max: 1,
        show: false,
      },
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

onMounted(async () => {
  await load()
  startAutoRefresh()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

async function onRefresh() {
  loading.value = true
  await load()
  startAutoRefresh()
}
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <span class="title">账号监控折线图</span>
      <label>
        条数
        <select v-model="limit" @change="onRefresh">
          <option :value="24">24条</option>
          <option :value="48">48条</option>
          <option :value="96">96条</option>
        </select>
      </label>
      <button @click="onRefresh">刷新</button>
      <span v-if="lastUpdated" class="updated">更新于 {{ lastUpdated }}</span>
    </div>

    <div v-if="loading" class="loading">加载中…</div>
    <div v-else-if="error" class="error">{{ error }}</div>

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
  padding: 22px 40px;
  background: #ffffff;
  border-bottom: 1px solid #e5e9f2;
  flex-wrap: wrap;
}

.title { font-size: 22px; font-weight: 700; color: #0f172a; margin-right: 8px; }

.toolbar label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #334155;
  font-size: 13px;
  font-weight: 600;
}

.toolbar select {
  height: 30px;
  padding: 0 8px;
  border: 1px solid #d7deea;
  border-radius: 6px;
  color: #0f172a;
  background: #ffffff;
  font-size: 12px;
  cursor: pointer;
}

.toolbar button {
  height: 32px;
  padding: 0 14px;
  border: 1px solid #2563eb;
  border-radius: 6px;
  color: #ffffff;
  background: #2563eb;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.toolbar button:hover { background: #1d4ed8; }
.updated { font-size: 12px; color: #64748b; margin-left: auto; }

.loading, .error { padding: 60px; text-align: center; color: #64748b; font-size: 14px; }
.error { color: #dc2626; }

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

.acct-name {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

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

.rate {
  font-size: 11px;
  color: #475569;
  margin-left: auto;
}

.priority {
  font-size: 11px;
  color: #94a3b8;
}

.chart {
  height: 160px;
  width: 100%;
}
</style>
