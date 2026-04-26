<script setup lang="ts">
import { use } from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { computed, ref, watch } from 'vue'
import { searchUsers, fetchUserDailyTrend, type UserOption, type DailyTrendItem } from '../api/userTrend'

use([CanvasRenderer, LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent])

function pad2(n: number) { return String(n).padStart(2, '0') }
function toDateStr(d: Date) { return `${d.getFullYear()}-${pad2(d.getMonth()+1)}-${pad2(d.getDate())}` }
function daysAgo(n: number) { const d = new Date(); d.setDate(d.getDate()-n); return toDateStr(d) }
function today() { return toDateStr(new Date()) }

const SHORTCUTS = [
  { label: '近7天',  start: () => daysAgo(6),  end: () => today() },
  { label: '近15天', start: () => daysAgo(14), end: () => today() },
  { label: '近30天', start: () => daysAgo(29), end: () => today() },
  { label: '近60天', start: () => daysAgo(59), end: () => today() },
]

const startDate = ref(daysAgo(29))
const endDate = ref(today())
const activeShortcut = ref('近30天')

function applyShortcut(s: typeof SHORTCUTS[0]) {
  startDate.value = s.start()
  endDate.value = s.end()
  activeShortcut.value = s.label
  if (selectedUser.value) void loadTrend()
}

// 用户搜索
const searchQuery = ref('')
const userOptions = ref<UserOption[]>([])
const searchLoading = ref(false)
const showDropdown = ref(false)
const selectedUser = ref<UserOption | null>(null)

let searchTimer: ReturnType<typeof setTimeout> | null = null
function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(async () => {
    if (!searchQuery.value.trim()) { userOptions.value = []; showDropdown.value = false; return }
    searchLoading.value = true
    try {
      userOptions.value = await searchUsers(searchQuery.value.trim())
      showDropdown.value = true
    } finally {
      searchLoading.value = false
    }
  }, 300)
}

function selectUser(u: UserOption) {
  selectedUser.value = u
  searchQuery.value = u.email + (u.username ? ` (${u.username})` : '')
  showDropdown.value = false
  void loadTrend()
}

function onFocus() { if (userOptions.value.length) showDropdown.value = true }
function hideDropdown() { setTimeout(() => { showDropdown.value = false }, 150) }

function clearUser() {
  searchQuery.value = ''
  trendItems.value = []
}

// 趋势数据
const trendItems = ref<DailyTrendItem[]>([])
const trendLoading = ref(false)
const trendError = ref('')

async function loadTrend() {
  if (!selectedUser.value) return
  trendLoading.value = true
  trendError.value = ''
  try {
    const data = await fetchUserDailyTrend(selectedUser.value.id, startDate.value, endDate.value)
    trendItems.value = data.items ?? []
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    trendError.value = err.response?.data?.detail ?? err.message ?? '加载失败'
  } finally {
    trendLoading.value = false
  }
}

// 统计
const totalCost = computed(() => trendItems.value.reduce((s, i) => s + i.actual_cost, 0).toFixed(4))
const totalAccountCost = computed(() => trendItems.value.reduce((s, i) => s + i.account_cost, 0).toFixed(4))
const totalRequests = computed(() => trendItems.value.reduce((s, i) => s + i.requests, 0).toLocaleString())
const totalTokens = computed(() => {
  const n = trendItems.value.reduce((s, i) => s + i.total_tokens, 0)
  if (n >= 1e9) return `${(n/1e9).toFixed(2)}B`
  if (n >= 1e6) return `${(n/1e6).toFixed(1)}M`
  if (n >= 1e3) return `${(n/1e3).toFixed(1)}K`
  return String(n)
})

// 图表
const chartOption = computed(() => {
  const items = trendItems.value
  if (!items.length) return {}
  const dates = items.map(i => i.date.slice(5))
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', lineStyle: { color: '#cbd5e1' } },
      backgroundColor: '#fff',
      borderColor: '#e2e8f0',
      textStyle: { color: '#0f172a', fontSize: 12 },
      formatter: (params: { seriesName: string; value: number; dataIndex: number }[]) => {
        const idx = params[0]?.dataIndex ?? 0
        const item = items[idx]
        if (!item) return ''
        const n = item.total_tokens
        const tok = n >= 1e9 ? `${(n/1e9).toFixed(2)}B` : n >= 1e6 ? `${(n/1e6).toFixed(1)}M` : `${(n/1e3).toFixed(1)}K`
        return [
          `<b>${item.date}</b>`,
          `费用：$${item.actual_cost.toFixed(4)}`,
          `成本：$${item.account_cost.toFixed(4)}`,
          `请求：${item.requests.toLocaleString()}`,
          `Token：${tok}`,
        ].join('<br/>')
      },
    },
    legend: { data: ['费用($)', '成本($)', '请求数'], textStyle: { color: '#64748b' }, bottom: 0 },
    grid: { left: 64, right: 64, top: 20, bottom: 48 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { color: '#64748b', fontSize: 11 },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisTick: { show: false },
    },
    yAxis: [
      {
        type: 'value',
        name: '费用($)',
        nameTextStyle: { color: '#64748b' },
        axisLabel: { color: '#64748b', formatter: (v: number) => `$${v.toFixed(2)}` },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
      },
      {
        type: 'value',
        name: '请求数',
        nameTextStyle: { color: '#64748b' },
        axisLabel: { color: '#64748b' },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '费用($)',
        type: 'bar',
        yAxisIndex: 0,
        data: items.map(i => i.actual_cost),
        itemStyle: { color: '#2563eb', borderRadius: [3, 3, 0, 0] },
        barMaxWidth: 24,
      },
      {
        name: '成本($)',
        type: 'bar',
        yAxisIndex: 0,
        data: items.map(i => i.account_cost),
        itemStyle: { color: '#0891b2', borderRadius: [3, 3, 0, 0] },
        barMaxWidth: 24,
      },
      {
        name: '请求数',
        type: 'line',
        yAxisIndex: 1,
        data: items.map(i => i.requests),
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { color: '#f59e0b', width: 2 },
        itemStyle: { color: '#f59e0b' },
      },
    ],
  }
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <!-- 用户搜索 -->
      <div class="search-wrap">
        <input
          v-model="searchQuery"
          class="search-input"
          placeholder="搜索用户（邮箱/姓名）"
          @input="onSearchInput"
          @blur="hideDropdown"
          @focus="onFocus"
        />
        <button v-if="selectedUser" class="clear-btn" @click="clearUser">×</button>
        <div v-if="showDropdown && userOptions.length" class="dropdown">
          <div
            v-for="u in userOptions"
            :key="u.id"
            class="dropdown-item"
            @mousedown.prevent="selectUser(u)"
          >
            <span class="user-email">{{ u.email }}</span>
            <span v-if="u.username" class="user-name">{{ u.username }}</span>
          </div>
        </div>
        <div v-if="searchLoading" class="search-hint">搜索中…</div>
      </div>

      <!-- 日期快捷 -->
      <div class="shortcuts">
        <button
          v-for="s in SHORTCUTS"
          :key="s.label"
          class="shortcut-btn"
          :class="{ active: activeShortcut === s.label }"
          @click="applyShortcut(s)"
        >{{ s.label }}</button>
      </div>

      <div class="date-range">
        <input type="date" v-model="startDate" class="date-input" @change="activeShortcut=''; if(selectedUser) loadTrend()" />
        <span class="date-sep">~</span>
        <input type="date" v-model="endDate" class="date-input" @change="activeShortcut=''; if(selectedUser) loadTrend()" />
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!selectedUser" class="empty">请搜索并选择一个用户</div>

    <template v-else>
      <div v-if="trendLoading" class="center-msg">加载中…</div>
      <div v-else-if="trendError" class="center-msg error">{{ trendError }}</div>
      <template v-else>
        <!-- 统计卡片 -->
        <div class="stat-cards">
          <div class="stat-card">
            <div class="stat-val">${{ totalCost }}</div>
            <div class="stat-label">费用</div>
          </div>
          <div class="stat-card">
            <div class="stat-val">${{ totalAccountCost }}</div>
            <div class="stat-label">成本</div>
          </div>
          <div class="stat-card">
            <div class="stat-val">{{ totalRequests }}</div>
            <div class="stat-label">总请求数</div>
          </div>
          <div class="stat-card">
            <div class="stat-val">{{ totalTokens }}</div>
            <div class="stat-label">总 Token</div>
          </div>
        </div>

        <!-- 图表 -->
        <div class="chart-card">
          <div class="card-title">每日费用 & 请求数</div>
          <VChart v-if="trendItems.length" class="chart" :option="chartOption" autoresize />
          <div v-else class="center-msg sm">该时间段无数据</div>
        </div>

        <!-- 明细表 -->
        <div class="chart-card">
          <div class="card-title">每日明细</div>
          <table class="detail-table">
            <thead>
              <tr><th>日期</th><th>费用($)</th><th>成本($)</th><th>请求数</th><th>Token</th></tr>
            </thead>
            <tbody>
              <tr v-for="item in [...trendItems].reverse()" :key="item.date">
                <td class="mono">{{ item.date }}</td>
                <td class="mono">${{ item.actual_cost.toFixed(4) }}</td>
                <td class="mono">${{ item.account_cost.toFixed(4) }}</td>
                <td class="mono">{{ item.requests.toLocaleString() }}</td>
                <td class="mono">{{
                  item.total_tokens >= 1e9 ? `${(item.total_tokens/1e9).toFixed(2)}B`
                  : item.total_tokens >= 1e6 ? `${(item.total_tokens/1e6).toFixed(1)}M`
                  : item.total_tokens >= 1e3 ? `${(item.total_tokens/1e3).toFixed(1)}K`
                  : item.total_tokens
                }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </template>
  </div>
</template>

<style scoped>
.page { padding: 24px; max-width: 1100px; margin: 0 auto; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #0f172a; }

.toolbar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }

.search-wrap { position: relative; }
.search-input { width: 280px; padding: 7px 32px 7px 12px; border: 1.5px solid #e2e8f0; border-radius: 8px; font-size: 14px; outline: none; }
.search-input:focus { border-color: #2563eb; }
.clear-btn { position: absolute; right: 8px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; color: #94a3b8; font-size: 16px; line-height: 1; }
.search-hint { position: absolute; top: 100%; left: 0; font-size: 12px; color: #94a3b8; padding: 4px 0; }
.dropdown { position: absolute; top: calc(100% + 4px); left: 0; width: 100%; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,0.08); z-index: 100; max-height: 240px; overflow-y: auto; }
.dropdown-item { padding: 8px 12px; cursor: pointer; display: flex; align-items: center; gap: 8px; }
.dropdown-item:hover { background: #f8fafc; }
.user-email { font-size: 13px; color: #0f172a; }
.user-name { font-size: 12px; color: #64748b; }

.shortcuts { display: flex; gap: 6px; }
.shortcut-btn { padding: 6px 12px; border: 1.5px solid #e2e8f0; border-radius: 6px; background: #fff; font-size: 13px; cursor: pointer; color: #374151; }
.shortcut-btn:hover { border-color: #94a3b8; }
.shortcut-btn.active { border-color: #2563eb; color: #2563eb; background: #eff6ff; }

.date-range { display: flex; align-items: center; gap: 6px; }
.date-input { padding: 6px 10px; border: 1.5px solid #e2e8f0; border-radius: 6px; font-size: 13px; outline: none; }
.date-input:focus { border-color: #2563eb; }
.date-sep { color: #94a3b8; }

.empty { text-align: center; padding: 80px; color: #94a3b8; font-size: 15px; }
.center-msg { text-align: center; padding: 48px; color: #64748b; }
.center-msg.error { color: #dc2626; }
.center-msg.sm { padding: 24px; }

.stat-cards { display: flex; gap: 12px; margin-bottom: 20px; }
.stat-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px 24px; flex: 1; text-align: center; }
.stat-val { font-size: 24px; font-weight: 700; color: #0f172a; }
.stat-label { font-size: 12px; color: #94a3b8; margin-top: 4px; }

.chart-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 20px; margin-bottom: 20px; }
.card-title { font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 16px; }
.chart { height: 300px; }

.detail-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.detail-table th { text-align: left; padding: 8px 12px; color: #64748b; font-weight: 500; border-bottom: 1px solid #e2e8f0; }
.detail-table td { padding: 8px 12px; border-bottom: 1px solid #f1f5f9; }
.detail-table tr:last-child td { border-bottom: none; }
.mono { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 12px; }
</style>
