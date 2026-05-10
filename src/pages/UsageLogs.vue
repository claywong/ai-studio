<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { fetchUsageLogs, type UsageLogItem, type UsageLogsParams } from '../api/usageLogs'

// 筛选
const filterStartDate = ref('')
const filterEndDate = ref('')
const filterUserId = ref('')
const filterModel = ref('')
const filterSessionId = ref('')
const filterAccountId = ref('')

// 列表状态
const items = ref<UsageLogItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const error = ref('')

// 展开详情
const expandedId = ref<number | null>(null)

// Token tooltip
const tokenTooltipVisible = ref(false)
const tokenTooltipPos = ref({ x: 0, y: 0 })
const tokenTooltipData = ref<UsageLogItem | null>(null)

// 费用 tooltip
const costTooltipVisible = ref(false)
const costTooltipPos = ref({ x: 0, y: 0 })
const costTooltipData = ref<UsageLogItem | null>(null)

function defaultDateRange() {
  const end = new Date()
  const start = new Date(end.getTime() - 24 * 60 * 60 * 1000)
  const fmt = (d: Date) => d.toISOString().slice(0, 10)
  return { start: fmt(start), end: fmt(end) }
}

const totalPages = computed(() => Math.ceil(total.value / pageSize.value))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params: UsageLogsParams = {
      page: page.value,
      page_size: pageSize.value,
      start_date: filterStartDate.value || undefined,
      end_date: filterEndDate.value || undefined,
      user_id: filterUserId.value ? Number(filterUserId.value) : undefined,
      model: filterModel.value || undefined,
      session_id: filterSessionId.value || undefined,
      account_id: filterAccountId.value ? Number(filterAccountId.value) : undefined,
    }
    const res = await fetchUsageLogs(params)
    items.value = (res as any)?.items ?? []
    total.value = (res as any)?.total ?? 0
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void load()
}

function reset() {
  const range = defaultDateRange()
  filterStartDate.value = range.start
  filterEndDate.value = range.end
  filterUserId.value = ''
  filterModel.value = ''
  filterSessionId.value = ''
  filterAccountId.value = ''
  page.value = 1
  void load()
}

function toggleExpand(item: UsageLogItem) {
  expandedId.value = expandedId.value === item.id ? null : item.id
}

function fmtTime(s: string): string {
  return new Date(s).toLocaleString('zh-CN', { hour12: false })
}

function fmtMs(ms: number | null): string {
  if (ms == null) return '-'
  if (ms >= 1000) return (ms / 1000).toFixed(2) + 's'
  return ms + 'ms'
}

function fmtJson(raw: string | null): string {
  if (!raw) return ''
  try {
    return JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    return raw
  }
}

function fmtCacheTokens(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return String(n)
}

function totalTokens(item: UsageLogItem): number {
  return (item.input_tokens || 0) + (item.output_tokens || 0) +
    (item.cache_read_tokens || 0) + (item.cache_creation_tokens || 0)
}

function accountBilled(item: UsageLogItem): number {
  const base = item.account_stats_cost != null ? item.account_stats_cost : (item.total_cost ?? 0)
  return base * (item.account_rate_multiplier ?? 1)
}

function fmtMultiplier(v: number | null): string {
  if (v == null) return '1.00'
  return v.toPrecision(4)
}

function tokenPricePerMillion(cost: number | null, tokens: number): string {
  if (!cost || !tokens) return '$0.0000'
  return '$' + ((cost / tokens) * 1_000_000).toFixed(4)
}

// Token tooltip 显示
function showTokenTooltip(event: MouseEvent, item: UsageLogItem) {
  const el = event.currentTarget as HTMLElement
  const rect = el.getBoundingClientRect()
  tokenTooltipPos.value = { x: rect.right + 8, y: rect.top + rect.height / 2 }
  tokenTooltipData.value = item
  tokenTooltipVisible.value = true
}

function hideTokenTooltip() {
  tokenTooltipVisible.value = false
  tokenTooltipData.value = null
}

// 费用 tooltip 显示
function showCostTooltip(event: MouseEvent, item: UsageLogItem) {
  const el = event.currentTarget as HTMLElement
  const rect = el.getBoundingClientRect()
  costTooltipPos.value = { x: rect.right + 8, y: rect.top + rect.height / 2 }
  costTooltipData.value = item
  costTooltipVisible.value = true
}

function hideCostTooltip() {
  costTooltipVisible.value = false
  costTooltipData.value = null
}

function prevPage() {
  if (page.value > 1) { page.value--; void load() }
}

function nextPage() {
  if (page.value < totalPages.value) { page.value++; void load() }
}

function goPage(p: number) {
  page.value = p
  void load()
}

function hideAllTooltips() {
  tokenTooltipVisible.value = false
  costTooltipVisible.value = false
}

onMounted(() => {
  const range = defaultDateRange()
  filterStartDate.value = range.start
  filterEndDate.value = range.end
  void load()
  document.addEventListener('scroll', hideAllTooltips, true)
})

onUnmounted(() => {
  document.removeEventListener('scroll', hideAllTooltips, true)
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <span class="title">请求日志</span>

      <div class="filter-item">
        <span class="filter-label">开始日期</span>
        <input type="date" v-model="filterStartDate" />
      </div>

      <div class="filter-item">
        <span class="filter-label">结束日期</span>
        <input type="date" v-model="filterEndDate" />
      </div>

      <div class="filter-item">
        <span class="filter-label">用户 ID</span>
        <input type="number" v-model="filterUserId" placeholder="可选" class="input-sm" />
      </div>

      <div class="filter-item">
        <span class="filter-label">账号 ID</span>
        <input type="number" v-model="filterAccountId" placeholder="可选" class="input-sm" />
      </div>

      <div class="filter-item">
        <span class="filter-label">模型</span>
        <input type="text" v-model="filterModel" placeholder="可选" class="input-md" />
      </div>

      <div class="filter-item">
        <span class="filter-label">Session ID</span>
        <input type="text" v-model="filterSessionId" placeholder="可选" class="input-lg" />
      </div>

      <button class="btn-primary" :disabled="loading" @click="search">
        {{ loading ? '加载中…' : '查询' }}
      </button>
      <button class="btn-secondary" @click="reset">重置</button>
    </div>

    <div v-if="error" class="error-msg">{{ error }}</div>

    <div class="total-info" v-if="!loading">
      共 {{ total }} 条记录，第 {{ page }} / {{ totalPages || 1 }} 页
    </div>

    <table v-if="items.length > 0" class="log-table">
      <thead>
        <tr>
          <th>时间</th>
          <th>用户</th>
          <th>账号</th>
          <th>模型</th>
          <th>Session ID</th>
          <th>TOKEN</th>
          <th>费用</th>
          <th>首 Token</th>
          <th>耗时</th>
          <th>详情</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="item in items" :key="item.id">
          <tr :class="{ 'row-expanded': expandedId === item.id }" @click="toggleExpand(item)">
            <td class="col-time">{{ fmtTime(item.created_at) }}</td>
            <td class="col-user">{{ item.user?.email ?? '-' }}</td>
            <td class="col-account">{{ item.account?.name ?? '-' }}</td>
            <td class="col-model">{{ item.model }}</td>
            <td class="col-session">
              <span v-if="item.session_id" class="session-tag" :title="item.session_id">
                {{ item.session_id.slice(0, 12) }}…
              </span>
              <span v-else class="muted">-</span>
            </td>

            <!-- TOKEN 列 -->
            <td class="col-token" @click.stop>
              <div class="token-cell">
                <div class="token-main">
                  <div class="token-row">
                    <span class="arrow-in">↓</span>
                    <span class="token-val">{{ (item.input_tokens || 0).toLocaleString() }}</span>
                    <span class="arrow-out">↑</span>
                    <span class="token-val">{{ (item.output_tokens || 0).toLocaleString() }}</span>
                  </div>
                  <div v-if="item.cache_read_tokens > 0" class="token-cache-row">
                    <span class="cache-icon">🗃</span>
                    <span class="cache-val">{{ fmtCacheTokens(item.cache_read_tokens) }}</span>
                  </div>
                </div>
                <button
                  class="info-btn"
                  @mouseenter="showTokenTooltip($event, item)"
                  @mouseleave="hideTokenTooltip"
                >ⓘ</button>
              </div>
            </td>

            <!-- 费用列 -->
            <td class="col-cost" @click.stop>
              <div class="cost-cell">
                <div class="cost-main">
                  <div class="cost-user">${{ (item.actual_cost ?? item.total_cost ?? 0).toFixed(6) }}</div>
                  <div v-if="item.account_rate_multiplier != null" class="cost-account">
                    A ${{ accountBilled(item).toFixed(6) }}
                  </div>
                </div>
                <button
                  class="info-btn"
                  @mouseenter="showCostTooltip($event, item)"
                  @mouseleave="hideCostTooltip"
                >ⓘ</button>
              </div>
            </td>

            <td class="col-num">{{ fmtMs(item.first_token_ms) }}</td>
            <td class="col-num">{{ fmtMs(item.duration_ms) }}</td>
            <td class="col-expand">
              <span class="expand-icon" :class="{ open: expandedId === item.id }">▶</span>
            </td>
          </tr>

          <!-- 展开详情行 -->
          <tr v-if="expandedId === item.id" class="detail-row">
            <td colspan="10">
              <div class="detail-box">
                <div class="detail-meta">
                  <span><b>Request ID:</b> {{ item.request_id ?? '-' }}</span>
                  <span><b>Session ID:</b> {{ item.session_id ?? '-' }}</span>
                  <span><b>上游模型:</b> {{ item.upstream_model ?? '-' }}</span>
                  <span><b>类型:</b> {{ item.stream ? 'Stream' : 'Sync' }}</span>
                </div>
                <div class="body-panels">
                  <div class="body-panel">
                    <div class="panel-title">Request Body</div>
                    <pre class="body-pre">{{ fmtJson(item.request_body) || '(无)' }}</pre>
                  </div>
                  <div class="body-panel">
                    <div class="panel-title">Response Body</div>
                    <pre class="body-pre">{{ fmtJson(item.response_body) || '(无)' }}</pre>
                  </div>
                </div>
              </div>
            </td>
          </tr>
        </template>
      </tbody>
    </table>

    <div v-else-if="!loading" class="empty">没有符合条件的记录</div>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="pagination">
      <button :disabled="page <= 1" @click="prevPage">上一页</button>
      <template v-for="p in totalPages" :key="p">
        <button
          v-if="p === 1 || p === totalPages || Math.abs(p - page) <= 2"
          :class="{ active: p === page }"
          @click="goPage(p)"
        >{{ p }}</button>
        <span v-else-if="p === 2 && page > 4" class="page-ellipsis">…</span>
        <span v-else-if="p === totalPages - 1 && page < totalPages - 3" class="page-ellipsis">…</span>
      </template>
      <button :disabled="page >= totalPages" @click="nextPage">下一页</button>

      <select class="page-size-select" v-model.number="pageSize" @change="search">
        <option :value="20">20条/页</option>
        <option :value="50">50条/页</option>
        <option :value="100">100条/页</option>
      </select>
    </div>
  </div>

  <!-- Token 详情 tooltip -->
  <Teleport to="body">
    <div
      v-if="tokenTooltipVisible && tokenTooltipData"
      class="tooltip-popup"
      :style="{ left: tokenTooltipPos.x + 'px', top: tokenTooltipPos.y + 'px' }"
    >
      <div class="tooltip-inner">
        <div class="tooltip-title">Token 明细</div>
        <div v-if="tokenTooltipData.input_tokens > 0" class="tooltip-row">
          <span class="tooltip-label">输入 Token</span>
          <span class="tooltip-val">{{ tokenTooltipData.input_tokens.toLocaleString() }}</span>
        </div>
        <div v-if="tokenTooltipData.output_tokens > 0" class="tooltip-row">
          <span class="tooltip-label">输出 Token</span>
          <span class="tooltip-val">{{ tokenTooltipData.output_tokens.toLocaleString() }}</span>
        </div>
        <div v-if="tokenTooltipData.cache_creation_tokens > 0" class="tooltip-row">
          <span class="tooltip-label">缓存写入 Token</span>
          <span class="tooltip-val">{{ tokenTooltipData.cache_creation_tokens.toLocaleString() }}</span>
        </div>
        <div v-if="tokenTooltipData.cache_read_tokens > 0" class="tooltip-row">
          <span class="tooltip-label">缓存读取 Token</span>
          <span class="tooltip-val">{{ tokenTooltipData.cache_read_tokens.toLocaleString() }}</span>
        </div>
        <div class="tooltip-divider" />
        <div class="tooltip-row">
          <span class="tooltip-label">总 Token</span>
          <span class="tooltip-val total-blue">{{ totalTokens(tokenTooltipData).toLocaleString() }}</span>
        </div>
      </div>
      <div class="tooltip-arrow-left" />
    </div>
  </Teleport>

  <!-- 费用详情 tooltip -->
  <Teleport to="body">
    <div
      v-if="costTooltipVisible && costTooltipData"
      class="tooltip-popup"
      :style="{ left: costTooltipPos.x + 'px', top: costTooltipPos.y + 'px' }"
    >
      <div class="tooltip-inner">
        <div class="tooltip-title">成本明细</div>
        <div v-if="(costTooltipData.input_cost ?? 0) > 0" class="tooltip-row">
          <span class="tooltip-label">输入成本</span>
          <span class="tooltip-val">${{ (costTooltipData.input_cost ?? 0).toFixed(6) }}</span>
        </div>
        <div v-if="(costTooltipData.output_cost ?? 0) > 0" class="tooltip-row">
          <span class="tooltip-label">输出成本</span>
          <span class="tooltip-val">${{ (costTooltipData.output_cost ?? 0).toFixed(6) }}</span>
        </div>
        <div v-if="costTooltipData.input_tokens > 0 && (costTooltipData.input_cost ?? 0) > 0" class="tooltip-row">
          <span class="tooltip-label">输入单价</span>
          <span class="tooltip-val price-violet">{{ tokenPricePerMillion(costTooltipData.input_cost, costTooltipData.input_tokens) }} / 1M Token</span>
        </div>
        <div v-if="costTooltipData.output_tokens > 0 && (costTooltipData.output_cost ?? 0) > 0" class="tooltip-row">
          <span class="tooltip-label">输出单价</span>
          <span class="tooltip-val price-violet">{{ tokenPricePerMillion(costTooltipData.output_cost, costTooltipData.output_tokens) }} / 1M Token</span>
        </div>
        <div v-if="(costTooltipData.cache_read_cost ?? 0) > 0" class="tooltip-row">
          <span class="tooltip-label">缓存读取成本</span>
          <span class="tooltip-val">${{ (costTooltipData.cache_read_cost ?? 0).toFixed(6) }}</span>
        </div>
        <div v-if="(costTooltipData.cache_creation_cost ?? 0) > 0" class="tooltip-row">
          <span class="tooltip-label">缓存写入成本</span>
          <span class="tooltip-val">${{ (costTooltipData.cache_creation_cost ?? 0).toFixed(6) }}</span>
        </div>
        <div class="tooltip-divider" />
        <div v-if="costTooltipData.service_tier" class="tooltip-row">
          <span class="tooltip-label">服务档位</span>
          <span class="tooltip-val price-cyan">{{ costTooltipData.service_tier }}</span>
        </div>
        <div class="tooltip-row">
          <span class="tooltip-label">倍率</span>
          <span class="tooltip-val price-blue">{{ fmtMultiplier(costTooltipData.rate_multiplier) }}x</span>
        </div>
        <div class="tooltip-row">
          <span class="tooltip-label">原始</span>
          <span class="tooltip-val">${{ (costTooltipData.total_cost ?? 0).toFixed(6) }}</span>
        </div>
        <div class="tooltip-row">
          <span class="tooltip-label">用户扣费</span>
          <span class="tooltip-val price-green">${{ (costTooltipData.actual_cost ?? 0).toFixed(6) }}</span>
        </div>
        <div v-if="costTooltipData.account_rate_multiplier != null" class="tooltip-divider" />
        <div v-if="costTooltipData.account_rate_multiplier != null" class="tooltip-row">
          <span class="tooltip-label">账号倍率</span>
          <span class="tooltip-val price-blue">{{ fmtMultiplier(costTooltipData.account_rate_multiplier) }}x</span>
        </div>
        <div v-if="costTooltipData.account_rate_multiplier != null" class="tooltip-row">
          <span class="tooltip-label">账号计费</span>
          <span class="tooltip-val price-green">${{ accountBilled(costTooltipData).toFixed(6) }}</span>
        </div>
      </div>
      <div class="tooltip-arrow-left" />
    </div>
  </Teleport>
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
  gap: 10px;
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
  gap: 5px;
}

.filter-label {
  color: #64748b;
  font-size: 12px;
  white-space: nowrap;
}

input[type="date"],
input[type="text"],
input[type="number"] {
  background: #fff;
  border: 1px solid #e2e8f0;
  color: #334155;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
}

.input-sm { width: 80px; }
.input-md { width: 120px; }
.input-lg { width: 200px; }

.btn-primary {
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 5px 16px;
  font-size: 12px;
  cursor: pointer;
}
.btn-primary:hover:not(:disabled) { background: #1d4ed8; }
.btn-primary:disabled { opacity: 0.5; cursor: default; }

.btn-secondary {
  background: #f1f5f9;
  color: #475569;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 5px 14px;
  font-size: 12px;
  cursor: pointer;
}
.btn-secondary:hover { background: #e2e8f0; }

.error-msg { color: #dc2626; margin-bottom: 12px; }

.total-info {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 10px;
}

.log-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  background: #fff;
  border: 1px solid #e5e9f2;
  border-radius: 10px;
  overflow: hidden;
}

.log-table th {
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

.log-table td {
  padding: 7px 12px;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: middle;
  color: #475569;
}

.log-table tbody tr:last-child td { border-bottom: none; }
.log-table tbody tr:hover td { background: #f8fafc; cursor: pointer; }
.log-table tbody tr.row-expanded td { background: #eff6ff; }

.col-time { white-space: nowrap; color: #64748b; }
.col-user { max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-account { max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-model { font-weight: 500; color: #0f172a; }
.col-session { max-width: 120px; }
.col-num { text-align: right; font-variant-numeric: tabular-nums; }
.col-expand { text-align: center; width: 36px; }

/* TOKEN 列 */
.col-token { white-space: nowrap; }
.token-cell { display: flex; align-items: center; gap: 6px; }
.token-main { display: flex; flex-direction: column; gap: 2px; }
.token-row { display: flex; align-items: center; gap: 4px; font-variant-numeric: tabular-nums; }
.token-val { font-weight: 500; color: #0f172a; font-size: 12px; }
.arrow-in { color: #16a34a; font-weight: 700; }
.arrow-out { color: #7c3aed; font-weight: 700; }
.token-cache-row { display: flex; align-items: center; gap: 4px; }
.cache-icon { font-size: 11px; color: #0891b2; }
.cache-val { font-weight: 500; color: #0891b2; font-size: 12px; }

/* 费用列 */
.col-cost { white-space: nowrap; }
.cost-cell { display: flex; align-items: center; gap: 6px; }
.cost-main { display: flex; flex-direction: column; gap: 2px; }
.cost-user { font-weight: 600; color: #16a34a; font-variant-numeric: tabular-nums; }
.cost-account { font-size: 11px; color: #f97316; font-variant-numeric: tabular-nums; }

/* info 按钮 */
.info-btn {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #e2e8f0;
  border: none;
  color: #94a3b8;
  font-size: 10px;
  cursor: help;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  line-height: 1;
  transition: background 0.15s, color 0.15s;
}
.info-btn:hover { background: #bfdbfe; color: #2563eb; }

.session-tag {
  display: inline-block;
  background: #ede9fe;
  color: #7c3aed;
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 11px;
  font-family: monospace;
}

.muted { color: #cbd5e1; }

.expand-icon {
  display: inline-block;
  color: #94a3b8;
  font-size: 10px;
  transition: transform 0.2s;
}
.expand-icon.open { transform: rotate(90deg); }

/* 详情行 */
.detail-row td { padding: 0; background: #f8fafc; border-bottom: 1px solid #e5e9f2; }

.detail-box { padding: 16px 20px; }

.detail-meta {
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
  font-size: 12px;
  color: #475569;
  flex-wrap: wrap;
}

.body-panels {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.body-panel {
  background: #1e293b;
  border-radius: 8px;
  overflow: hidden;
}

.panel-title {
  background: #334155;
  color: #94a3b8;
  font-size: 11px;
  font-weight: 600;
  padding: 6px 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.body-pre {
  color: #e2e8f0;
  font-family: 'JetBrains Mono', 'Fira Code', 'Menlo', monospace;
  font-size: 11px;
  line-height: 1.6;
  padding: 12px;
  margin: 0;
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 分页 */
.pagination {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 16px;
  justify-content: center;
}

.pagination button {
  min-width: 32px;
  height: 32px;
  padding: 0 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}
.pagination button:hover:not(:disabled) { background: #f1f5f9; }
.pagination button:disabled { opacity: 0.4; cursor: default; }
.pagination button.active { background: #2563eb; color: #fff; border-color: #2563eb; }

.page-ellipsis { color: #94a3b8; padding: 0 4px; line-height: 32px; }

.page-size-select {
  margin-left: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  background: #fff;
  color: #475569;
  cursor: pointer;
}

.empty { color: #94a3b8; padding: 40px; text-align: center; }
</style>

<!-- Tooltip 全局样式（不加 scoped，因为 Teleport 到 body） -->
<style>
.tooltip-popup {
  position: fixed;
  z-index: 9999;
  transform: translateY(-50%);
  pointer-events: none;
}

.tooltip-inner {
  background: #111827;
  border: 1px solid #374151;
  border-radius: 10px;
  padding: 10px 14px;
  min-width: 220px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.tooltip-title {
  font-size: 12px;
  font-weight: 600;
  color: #d1d5db;
  margin-bottom: 4px;
}

.tooltip-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.tooltip-label {
  font-size: 12px;
  color: #9ca3af;
  white-space: nowrap;
}

.tooltip-val {
  font-size: 12px;
  font-weight: 500;
  color: #f9fafb;
  font-variant-numeric: tabular-nums;
}

.tooltip-divider {
  height: 1px;
  background: #374151;
  margin: 4px 0;
}

.total-blue   { color: #60a5fa; font-weight: 700; }
.price-green  { color: #34d399; font-weight: 600; }
.price-blue   { color: #60a5fa; font-weight: 600; }
.price-violet { color: #c084fc; font-weight: 500; }
.price-cyan   { color: #22d3ee; font-weight: 600; }

.tooltip-arrow-left {
  position: absolute;
  right: 100%;
  top: 50%;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  border-top: 6px solid transparent;
  border-bottom: 6px solid transparent;
  border-right: 6px solid #374151;
}
</style>
