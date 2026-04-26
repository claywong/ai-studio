<script setup lang="ts">
import { use } from 'echarts/core'
import { LineChart, ScatterChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { computed, onMounted, ref, watch } from 'vue'
import { fetchMonitors, fetchMonitorHistory, type ChannelMonitor, type HistoryItem } from '../api/channelMonitors'

use([CanvasRenderer, LineChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

const loading = ref(true)
const error = ref('')
const monitors = ref<ChannelMonitor[]>([])
const selectedId = ref<number | null>(null)
const historyLoading = ref(false)
const history = ref<HistoryItem[]>([])

const STATUS_COLOR: Record<string, string> = {
  operational: '#16a34a',
  degraded: '#f59e0b',
  error: '#dc2626',
  unknown: '#94a3b8',
}

const STATUS_LABEL: Record<string, string> = {
  operational: '正常',
  degraded: '降级',
  error: '故障',
  unknown: '未知',
}

function statusColor(s: string) { return STATUS_COLOR[s] ?? STATUS_COLOR.unknown }
function statusLabel(s: string) { return STATUS_LABEL[s] ?? s }

function fmtTime(iso: string) {
  const d = new Date(iso)
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function fmtAvail(v: number) { return v.toFixed(2) + '%' }

async function loadMonitors() {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchMonitors()
    monitors.value = data.items ?? []
    if (monitors.value.length > 0 && selectedId.value === null) {
      selectedId.value = monitors.value[0].id
    }
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    error.value = err.response?.data?.detail ?? err.message ?? '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadHistory(id: number) {
  historyLoading.value = true
  history.value = []
  try {
    const data = await fetchMonitorHistory(id, 200)
    history.value = (data.items ?? []).slice().reverse()
  } catch {
    history.value = []
  } finally {
    historyLoading.value = false
  }
}

watch(selectedId, (id) => { if (id !== null) void loadHistory(id) })
onMounted(loadMonitors)

const selectedMonitor = computed(() =>
  monitors.value.find(m => m.id === selectedId.value) ?? null,
)

// 历史图表：延迟折线 + 状态散点
const historyChartOption = computed(() => {
  const items = history.value
  if (!items.length) return {}

  const times = items.map(i => fmtTime(i.checked_at))
  const latencies = items.map(i => i.latency_ms ?? null)
  const pingLatencies = items.map(i => i.ping_latency_ms ?? null)

  // 故障点散点
  const errorPoints = items
    .map((i, idx) => i.status === 'error' ? [idx, i.latency_ms ?? 0] : null)
    .filter(Boolean)
  const degradedPoints = items
    .map((i, idx) => i.status === 'degraded' ? [idx, i.latency_ms ?? 0] : null)
    .filter(Boolean)

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', lineStyle: { color: '#cbd5e1' } },
      backgroundColor: '#ffffff',
      borderColor: '#e2e8f0',
      textStyle: { color: '#0f172a', fontSize: 12 },
      formatter: (params: { dataIndex: number; seriesName: string; value: number | null }[]) => {
        const idx = params[0]?.dataIndex ?? 0
        const item = items[idx]
        if (!item) return ''
        const lines = [
          `<div style="font-weight:600;margin-bottom:4px">${fmtTime(item.checked_at)}</div>`,
          `状态：<span style="color:${statusColor(item.status)};font-weight:600">${statusLabel(item.status)}</span>`,
          `延迟：${item.latency_ms != null ? item.latency_ms + ' ms' : '-'}`,
          `Ping：${item.ping_latency_ms != null ? item.ping_latency_ms + ' ms' : '-'}`,
        ]
        if (item.message) lines.push(`<div style="color:#dc2626;margin-top:4px;max-width:280px;word-break:break-all">${item.message}</div>`)
        return lines.join('<br/>')
      },
    },
    legend: {
      data: ['响应延迟', 'Ping 延迟'],
      textStyle: { color: '#64748b' },
      bottom: 0,
    },
    grid: { left: 60, right: 20, top: 20, bottom: 48 },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: {
        color: '#94a3b8',
        fontSize: 10,
        interval: Math.floor(items.length / 10),
        rotate: 30,
      },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: 'ms',
      nameTextStyle: { color: '#94a3b8' },
      axisLabel: { color: '#64748b', formatter: (v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${v}` },
      splitLine: { lineStyle: { color: '#f1f5f9' } },
    },
    series: [
      {
        name: '响应延迟',
        type: 'line',
        data: latencies,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#2563eb', width: 2 },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(37,99,235,0.15)' }, { offset: 1, color: 'rgba(37,99,235,0)' }] } },
      },
      {
        name: 'Ping 延迟',
        type: 'line',
        data: pingLatencies,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#0891b2', width: 1.5, type: 'dashed' },
      },
      {
        name: '故障',
        type: 'scatter',
        data: errorPoints,
        symbol: 'circle',
        symbolSize: 8,
        itemStyle: { color: '#dc2626' },
        tooltip: { show: false },
      },
      {
        name: '降级',
        type: 'scatter',
        data: degradedPoints,
        symbol: 'circle',
        symbolSize: 8,
        itemStyle: { color: '#f59e0b' },
        tooltip: { show: false },
      },
    ],
  }
})

// 可用率统计
const availStats = computed(() => {
  const items = history.value
  if (!items.length) return null
  const total = items.length
  const ok = items.filter(i => i.status === 'operational').length
  const degraded = items.filter(i => i.status === 'degraded').length
  const err = items.filter(i => i.status === 'error').length
  const avgLatency = Math.round(items.filter(i => i.latency_ms != null).reduce((s, i) => s + (i.latency_ms ?? 0), 0) / (items.filter(i => i.latency_ms != null).length || 1))
  return { total, ok, degraded, err, avail: (ok / total * 100).toFixed(2), avgLatency }
})

// 最近错误
const recentErrors = computed(() =>
  history.value.filter(i => i.status !== 'operational').slice(-20).reverse(),
)
</script>

<template>
  <div class="page">
    <div v-if="loading" class="center-msg">加载中…</div>
    <div v-else-if="error" class="center-msg error">{{ error }}</div>
    <template v-else>
      <!-- 监控列表 -->
      <div class="monitor-list">
        <div
          v-for="m in monitors"
          :key="m.id"
          class="monitor-card"
          :class="{ active: selectedId === m.id }"
          @click="selectedId = m.id"
        >
          <div class="monitor-card-header">
            <span class="dot" :style="{ background: statusColor(m.primary_status) }"></span>
            <span class="monitor-name">{{ m.name }}</span>
          </div>
          <div class="monitor-meta">{{ m.primary_model }}</div>
          <div class="monitor-avail">
            <span class="avail-label">7d 可用率</span>
            <span class="avail-val" :style="{ color: m.availability_7d >= 99 ? '#16a34a' : m.availability_7d >= 95 ? '#f59e0b' : '#dc2626' }">
              {{ fmtAvail(m.availability_7d) }}
            </span>
          </div>
          <div class="monitor-latency" v-if="m.primary_latency_ms != null">
            延迟 {{ m.primary_latency_ms }} ms
          </div>
        </div>
      </div>

      <!-- 详情区 -->
      <div v-if="selectedMonitor" class="detail">
        <div class="detail-header">
          <div class="detail-title">
            <span class="dot lg" :style="{ background: statusColor(selectedMonitor.primary_status) }"></span>
            {{ selectedMonitor.name }}
            <span class="status-badge" :style="{ background: statusColor(selectedMonitor.primary_status) + '22', color: statusColor(selectedMonitor.primary_status) }">
              {{ statusLabel(selectedMonitor.primary_status) }}
            </span>
          </div>
          <div class="detail-meta">
            {{ selectedMonitor.endpoint }} · {{ selectedMonitor.primary_model }} · 每 {{ selectedMonitor.interval_seconds }}s 检测
          </div>
        </div>

        <!-- 统计卡片 -->
        <div v-if="availStats" class="stat-cards">
          <div class="stat-card">
            <div class="stat-val">{{ availStats.avail }}%</div>
            <div class="stat-label">近期可用率</div>
          </div>
          <div class="stat-card">
            <div class="stat-val green">{{ availStats.ok }}</div>
            <div class="stat-label">正常次数</div>
          </div>
          <div class="stat-card">
            <div class="stat-val yellow">{{ availStats.degraded }}</div>
            <div class="stat-label">降级次数</div>
          </div>
          <div class="stat-card">
            <div class="stat-val red">{{ availStats.err }}</div>
            <div class="stat-label">故障次数</div>
          </div>
          <div class="stat-card">
            <div class="stat-val">{{ availStats.avgLatency }} ms</div>
            <div class="stat-label">平均延迟</div>
          </div>
          <div class="stat-card">
            <div class="stat-val">{{ fmtAvail(selectedMonitor.availability_7d) }}</div>
            <div class="stat-label">7天可用率</div>
          </div>
        </div>

        <!-- 延迟图 -->
        <div class="chart-card">
          <div class="card-title">延迟历史（近 200 次）</div>
          <div v-if="historyLoading" class="center-msg sm">加载中…</div>
          <VChart v-else-if="history.length" class="chart" :option="historyChartOption" autoresize />
          <div v-else class="center-msg sm">暂无数据</div>
        </div>

        <!-- 异常记录 -->
        <div class="chart-card" v-if="recentErrors.length">
          <div class="card-title">异常记录</div>
          <table class="err-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>状态</th>
                <th>延迟</th>
                <th>原因</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="e in recentErrors" :key="e.id">
                <td class="mono">{{ fmtTime(e.checked_at) }}</td>
                <td>
                  <span class="status-badge sm" :style="{ background: statusColor(e.status) + '22', color: statusColor(e.status) }">
                    {{ statusLabel(e.status) }}
                  </span>
                </td>
                <td class="mono">{{ e.latency_ms != null ? e.latency_ms + ' ms' : '-' }}</td>
                <td class="err-msg">{{ e.message || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  color: #0f172a;
}

.center-msg {
  text-align: center;
  padding: 48px;
  color: #64748b;
}
.center-msg.error { color: #dc2626; }
.center-msg.sm { padding: 24px; }

.monitor-list {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 24px;
}

.monitor-card {
  background: #fff;
  border: 1.5px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px 18px;
  cursor: pointer;
  min-width: 180px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.monitor-card:hover { border-color: #94a3b8; }
.monitor-card.active { border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }

.monitor-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.monitor-name { font-weight: 600; font-size: 14px; }
.monitor-meta { font-size: 12px; color: #64748b; margin-bottom: 8px; }
.monitor-avail { display: flex; justify-content: space-between; align-items: center; }
.avail-label { font-size: 11px; color: #94a3b8; }
.avail-val { font-size: 14px; font-weight: 700; }
.monitor-latency { font-size: 11px; color: #94a3b8; margin-top: 4px; }

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot.lg { width: 10px; height: 10px; }

.detail-header {
  margin-bottom: 20px;
}
.detail-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 6px;
}
.detail-meta { font-size: 13px; color: #64748b; }

.status-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 99px;
}
.status-badge.sm { font-size: 11px; padding: 1px 6px; }

.stat-cards {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}
.stat-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px 20px;
  min-width: 110px;
  text-align: center;
}
.stat-val {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.2;
}
.stat-val.green { color: #16a34a; }
.stat-val.yellow { color: #f59e0b; }
.stat-val.red { color: #dc2626; }
.stat-label { font-size: 11px; color: #94a3b8; margin-top: 4px; }

.chart-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 20px;
}
.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 16px;
}
.chart { height: 280px; }

.err-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.err-table th {
  text-align: left;
  padding: 8px 12px;
  color: #64748b;
  font-weight: 500;
  border-bottom: 1px solid #e2e8f0;
}
.err-table td {
  padding: 8px 12px;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: top;
}
.err-table tr:last-child td { border-bottom: none; }
.mono { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 12px; }
.err-msg {
  color: #64748b;
  max-width: 500px;
  word-break: break-all;
  font-size: 12px;
}
</style>
