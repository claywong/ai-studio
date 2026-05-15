<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { fetchAccountLatency, type AccountLatencyGroup, type AccountLatency, type ModelLatency } from '../api/accountLatency'

const loading = ref(true)
const error = ref('')
const groups = ref<AccountLatencyGroup[]>([])
const limit = ref(300)
const recentMinutes = ref(10)
const expandedGroups = ref<Set<string>>(new Set())
const expandedAccounts = ref<Set<number>>(new Set())
const lastUpdated = ref('')
let timer: ReturnType<typeof setInterval> | null = null

function fmt(ms: number | null): string {
  if (ms == null) return '-'
  if (ms >= 1000) return (ms / 1000).toFixed(1) + 's'
  return ms + 'ms'
}

function fmtOtps(otps: number | null): string {
  if (otps == null) return '-'
  return otps.toFixed(1) + ' t/s'
}

function fmtRate(rate: number | null): string {
  if (rate == null) return '-'
  return rate.toFixed(1) + '%'
}

function latencyClass(ms: number | null): string {
  if (ms == null) return ''
  if (ms < 1000) return 'good'
  if (ms < 3000) return 'ok'
  if (ms < 8000) return 'warn'
  return 'bad'
}

function fmtCost(cost: number | null): string {
  if (cost == null) return '-'
  if (cost < 0.001) return '$' + cost.toFixed(6)
  if (cost < 0.01) return '$' + cost.toFixed(5)
  return '$' + cost.toFixed(4)
}

function cacheRateClass(rate: number | null): string {
  if (rate == null) return ''
  if (rate >= 90) return 'good'
  if (rate >= 85) return 'ok'
  if (rate >= 80) return 'warn'
  return 'bad'
}

// 每个账号合并所有模型的汇总行
function accountSummary(acct: AccountLatency) {
  const models = acct.models
  const total = models.reduce((s, m) => s + m.requests, 0)
  const recentTotal = models.reduce((s, m) => s + m.recent_requests, 0)
  const avg = (vals: (number | null)[]) => {
    const v = vals.filter((x): x is number => x != null)
    return v.length ? Math.round(v.reduce((a, b) => a + b, 0) / v.length) : null
  }
  const avgFloat = (vals: (number | null)[]) => {
    const v = vals.filter((x): x is number => x != null)
    return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null
  }
  const p90 = (vals: (number | null)[]) => {
    const v = vals.filter((x): x is number => x != null).sort((a, b) => a - b)
    return v.length ? v[Math.floor(v.length * 0.9)] : null
  }
  const weightedRate = (rates: (number | null)[], weights: number[]) => {
    let wSum = 0, rSum = 0
    rates.forEach((r, i) => { if (r != null && weights[i] > 0) { wSum += r * weights[i]; rSum += weights[i] } })
    return rSum > 0 ? Math.round(wSum / rSum * 10) / 10 : null
  }
  return {
    requests: total,
    ttft_avg: avg(models.map(m => m.ttft_avg)),
    ttft_p90: p90(models.flatMap(m => Array(m.requests).fill(m.ttft_p90))),
    dur_avg: avg(models.map(m => m.dur_avg)),
    dur_p90: p90(models.flatMap(m => Array(m.requests).fill(m.dur_p90))),
    otps_avg: avgFloat(models.map(m => m.otps_avg)),
    otps_p10: avgFloat(models.map(m => m.otps_p10)),
    cache_hit_rate: weightedRate(models.map(m => m.cache_hit_rate), models.map(m => m.requests)),
    cost_avg: avgFloat(models.map(m => m.cost_avg)),
    recent_requests: recentTotal,
    recent_ttft_avg: avg(models.map(m => m.recent_ttft_avg)),
    recent_ttft_p90: p90(models.flatMap(m => Array(m.recent_requests).fill(m.recent_ttft_p90))),
    recent_dur_avg: avg(models.map(m => m.recent_dur_avg)),
    recent_otps_avg: avgFloat(models.map(m => m.recent_otps_avg)),
    recent_otps_p10: avgFloat(models.map(m => m.recent_otps_p10)),
    recent_cache_hit_rate: weightedRate(models.map(m => m.recent_cache_hit_rate), models.map(m => m.recent_requests)),
    recent_cost_avg: avgFloat(models.map(m => m.recent_cost_avg)),
  }
}

function toggleGroup(g: string) {
  const s = new Set(expandedGroups.value)
  s.has(g) ? s.delete(g) : s.add(g)
  expandedGroups.value = s
}

function toggleAccount(id: number) {
  const s = new Set(expandedAccounts.value)
  s.has(id) ? s.delete(id) : s.add(id)
  expandedAccounts.value = s
}

async function load() {
  try {
    const data = await fetchAccountLatency(limit.value, recentMinutes.value)
    groups.value = data.groups
    lastUpdated.value = new Date().toLocaleTimeString()
    error.value = ''
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

function startAutoRefresh() {
  if (timer) clearInterval(timer)
  timer = setInterval(() => void load(), recentMinutes.value * 60 * 1000)
}

onMounted(() => {
  void load()
  startAutoRefresh()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

function onParamChange() {
  loading.value = true
  void load()
  startAutoRefresh()
}
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <span class="title">账号延迟统计</span>
      <label>
        最近条数
        <select v-model="limit" @change="onParamChange">
          <option :value="100">100</option>
          <option :value="300">300</option>
          <option :value="500">500</option>
          <option :value="1000">1000</option>
        </select>
      </label>
      <label>
        实时窗口
        <select v-model="recentMinutes" @change="onParamChange">
          <option :value="5">5分钟</option>
          <option :value="10">10分钟</option>
          <option :value="30">30分钟</option>
          <option :value="60">60分钟</option>
        </select>
      </label>
      <button @click="onParamChange">刷新</button>
      <span v-if="lastUpdated" class="updated">更新于 {{ lastUpdated }}</span>
    </div>

    <div v-if="loading" class="loading">加载中…</div>
    <div v-else-if="error" class="error">{{ error }}</div>

    <div v-else class="groups">
      <div v-for="grp in groups" :key="grp.group" class="group-block">
        <div class="group-header" @click="toggleGroup(grp.group)">
          <span class="chevron">{{ expandedGroups.has(grp.group) ? '▾' : '▸' }}</span>
          <span class="group-name">{{ grp.group }}</span>
          <span class="group-count">{{ grp.accounts.length }} 个账号</span>
        </div>

        <div v-if="expandedGroups.has(grp.group)" class="accounts">
          <table>
            <thead>
              <tr>
                <th class="col-name">账号</th>
                <th colspan="9" class="col-section">最近 {{ limit }} 条</th>
                <th colspan="8" class="col-section recent">最近 {{ recentMinutes }} 分钟</th>
              </tr>
              <tr>
                <th></th>
                <th>请求数</th>
                <th>TTFT均值</th>
                <th>TTFT P90</th>
                <th>总时均值</th>
                <th>总时 P90</th>
                <th>OTPS均值</th>
                <th>OTPS P10</th>
                <th>缓存命中率</th>
                <th>均次成本</th>
                <th class="recent">请求数</th>
                <th class="recent">TTFT均值</th>
                <th class="recent">TTFT P90</th>
                <th class="recent">总时均值</th>
                <th class="recent">OTPS均值</th>
                <th class="recent">OTPS P10</th>
                <th class="recent">缓存命中率</th>
                <th class="recent">均次成本</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="acct in grp.accounts" :key="acct.account_id">
                <tr class="acct-row" @click="toggleAccount(acct.account_id)">
                  <td class="col-name">
                    <span class="chevron">{{ expandedAccounts.has(acct.account_id) ? '▾' : '▸' }}</span>
                    {{ acct.account_name }}
                    <span v-if="acct.models.length > 1" class="model-count">{{ acct.models.length }}模型</span>
                  </td>
                  <template v-if="acct.models.length === 1">
                    <td>{{ acct.models[0].requests }}</td>
                    <td :class="latencyClass(acct.models[0].ttft_avg)">{{ fmt(acct.models[0].ttft_avg) }}</td>
                    <td :class="latencyClass(acct.models[0].ttft_p90)">{{ fmt(acct.models[0].ttft_p90) }}</td>
                    <td :class="latencyClass(acct.models[0].dur_avg)">{{ fmt(acct.models[0].dur_avg) }}</td>
                    <td :class="latencyClass(acct.models[0].dur_p90)">{{ fmt(acct.models[0].dur_p90) }}</td>
                    <td>{{ fmtOtps(acct.models[0].otps_avg) }}</td>
                    <td>{{ fmtOtps(acct.models[0].otps_p10) }}</td>
                    <td :class="cacheRateClass(acct.models[0].cache_hit_rate)">{{ fmtRate(acct.models[0].cache_hit_rate) }}</td>
                    <td>{{ fmtCost(acct.models[0].cost_avg) }}</td>
                    <td class="recent">{{ acct.models[0].recent_requests || '-' }}</td>
                    <td class="recent" :class="latencyClass(acct.models[0].recent_ttft_avg)">{{ fmt(acct.models[0].recent_ttft_avg) }}</td>
                    <td class="recent" :class="latencyClass(acct.models[0].recent_ttft_p90)">{{ fmt(acct.models[0].recent_ttft_p90) }}</td>
                    <td class="recent" :class="latencyClass(acct.models[0].recent_dur_avg)">{{ fmt(acct.models[0].recent_dur_avg) }}</td>
                    <td class="recent">{{ fmtOtps(acct.models[0].recent_otps_avg) }}</td>
                    <td class="recent">{{ fmtOtps(acct.models[0].recent_otps_p10) }}</td>
                    <td class="recent" :class="cacheRateClass(acct.models[0].recent_cache_hit_rate)">{{ fmtRate(acct.models[0].recent_cache_hit_rate) }}</td>
                    <td class="recent">{{ fmtCost(acct.models[0].recent_cost_avg) }}</td>
                  </template>
                  <template v-else>
                    <td>{{ accountSummary(acct).requests }}</td>
                    <td :class="latencyClass(accountSummary(acct).ttft_avg)">{{ fmt(accountSummary(acct).ttft_avg) }}</td>
                    <td :class="latencyClass(accountSummary(acct).ttft_p90)">{{ fmt(accountSummary(acct).ttft_p90) }}</td>
                    <td :class="latencyClass(accountSummary(acct).dur_avg)">{{ fmt(accountSummary(acct).dur_avg) }}</td>
                    <td :class="latencyClass(accountSummary(acct).dur_p90)">{{ fmt(accountSummary(acct).dur_p90) }}</td>
                    <td>{{ fmtOtps(accountSummary(acct).otps_avg) }}</td>
                    <td>{{ fmtOtps(accountSummary(acct).otps_p10) }}</td>
                    <td :class="cacheRateClass(accountSummary(acct).cache_hit_rate)">{{ fmtRate(accountSummary(acct).cache_hit_rate) }}</td>
                    <td>{{ fmtCost(accountSummary(acct).cost_avg) }}</td>
                    <td class="recent">{{ accountSummary(acct).recent_requests || '-' }}</td>
                    <td class="recent" :class="latencyClass(accountSummary(acct).recent_ttft_avg)">{{ fmt(accountSummary(acct).recent_ttft_avg) }}</td>
                    <td class="recent" :class="latencyClass(accountSummary(acct).recent_ttft_p90)">{{ fmt(accountSummary(acct).recent_ttft_p90) }}</td>
                    <td class="recent" :class="latencyClass(accountSummary(acct).recent_dur_avg)">{{ fmt(accountSummary(acct).recent_dur_avg) }}</td>
                    <td class="recent">{{ fmtOtps(accountSummary(acct).recent_otps_avg) }}</td>
                    <td class="recent">{{ fmtOtps(accountSummary(acct).recent_otps_p10) }}</td>
                    <td class="recent" :class="cacheRateClass(accountSummary(acct).recent_cache_hit_rate)">{{ fmtRate(accountSummary(acct).recent_cache_hit_rate) }}</td>
                    <td class="recent">{{ fmtCost(accountSummary(acct).recent_cost_avg) }}</td>
                  </template>
                </tr>
                <!-- 模型展开行 -->
                <template v-if="expandedAccounts.has(acct.account_id) && acct.models.length > 1">
                  <tr v-for="m in acct.models" :key="m.model" class="model-row">
                    <td class="col-name model-name">↳ {{ m.model }}</td>
                    <td>{{ m.requests }}</td>
                    <td :class="latencyClass(m.ttft_avg)">{{ fmt(m.ttft_avg) }}</td>
                    <td :class="latencyClass(m.ttft_p90)">{{ fmt(m.ttft_p90) }}</td>
                    <td :class="latencyClass(m.dur_avg)">{{ fmt(m.dur_avg) }}</td>
                    <td :class="latencyClass(m.dur_p90)">{{ fmt(m.dur_p90) }}</td>
                    <td>{{ fmtOtps(m.otps_avg) }}</td>
                    <td>{{ fmtOtps(m.otps_p10) }}</td>
                    <td :class="cacheRateClass(m.cache_hit_rate)">{{ fmtRate(m.cache_hit_rate) }}</td>
                    <td>{{ fmtCost(m.cost_avg) }}</td>
                    <td class="recent">{{ m.recent_requests || '-' }}</td>
                    <td class="recent" :class="latencyClass(m.recent_ttft_avg)">{{ fmt(m.recent_ttft_avg) }}</td>
                    <td class="recent" :class="latencyClass(m.recent_ttft_p90)">{{ fmt(m.recent_ttft_p90) }}</td>
                    <td class="recent" :class="latencyClass(m.recent_dur_avg)">{{ fmt(m.recent_dur_avg) }}</td>
                    <td class="recent">{{ fmtOtps(m.recent_otps_avg) }}</td>
                    <td class="recent">{{ fmtOtps(m.recent_otps_p10) }}</td>
                    <td class="recent" :class="cacheRateClass(m.recent_cache_hit_rate)">{{ fmtRate(m.recent_cache_hit_rate) }}</td>
                    <td class="recent">{{ fmtCost(m.recent_cost_avg) }}</td>
                  </tr>
                </template>
              </template>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 0 0 40px;
  color: #0f172a;
  background: #f5f7fb;
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

.groups { max-width: 1440px; margin: 0 auto; padding: 24px 40px 0; display: grid; gap: 12px; }

.group-block { border: 1px solid #e5e9f2; border-radius: 10px; overflow: hidden; background: #ffffff; }

.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #ffffff;
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid transparent;
}
.group-header:hover { background: #f8fafc; }
.group-block:has(.accounts) .group-header { border-bottom-color: #e5e9f2; }

.group-name { font-weight: 700; color: #0f172a; font-size: 14px; }
.group-count { font-size: 11px; color: #94a3b8; margin-left: auto; }
.chevron { color: #94a3b8; font-size: 11px; width: 12px; }

table { width: 100%; border-collapse: collapse; }

thead tr:first-child th {
  background: #f8fafc;
  padding: 7px 12px;
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
  text-align: center;
  border-bottom: 1px solid #e5e9f2;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

thead tr:last-child th {
  background: #f8fafc;
  padding: 6px 12px;
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  text-align: right;
  border-bottom: 1px solid #e5e9f2;
}

.col-name { text-align: left !important; }
.col-section { border-left: 1px solid #e5e9f2; }

tbody tr { border-bottom: 1px solid #f1f5f9; }
tbody tr:last-child { border-bottom: none; }

.acct-row { background: #ffffff; cursor: pointer; }
.acct-row:hover { background: #f8fafc; }
.model-row { background: #fafbfd; }

td { padding: 8px 12px; text-align: right; color: #475569; font-size: 13px; }
td.col-name { text-align: left; color: #0f172a; font-weight: 500; }
.model-name { color: #64748b; padding-left: 28px; font-weight: 400; }
.model-count {
  font-size: 10px;
  color: #94a3b8;
  margin-left: 6px;
  background: #f1f5f9;
  padding: 1px 5px;
  border-radius: 4px;
}

.recent { background: #eff6ff; }
thead .recent { color: #2563eb !important; }

/* 延迟颜色 */
td.good { color: #16a34a; font-weight: 600; }
td.ok   { color: #65a30d; font-weight: 600; }
td.warn { color: #d97706; font-weight: 600; }
td.bad  { color: #dc2626; font-weight: 600; }
</style>
