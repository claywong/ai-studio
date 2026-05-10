<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
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

// 格式化时间（默认 last 24h）
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

function prevPage() {
  if (page.value > 1) {
    page.value--
    void load()
  }
}

function nextPage() {
  if (page.value < totalPages.value) {
    page.value++
    void load()
  }
}

function goPage(p: number) {
  page.value = p
  void load()
}

onMounted(() => {
  const range = defaultDateRange()
  filterStartDate.value = range.start
  filterEndDate.value = range.end
  void load()
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
          <th>输入 Token</th>
          <th>输出 Token</th>
          <th>TTFT</th>
          <th>耗时</th>
          <th>费用</th>
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
            <td class="col-num">{{ item.input_tokens.toLocaleString() }}</td>
            <td class="col-num">{{ item.output_tokens.toLocaleString() }}</td>
            <td class="col-num">{{ fmtMs(item.first_token_ms) }}</td>
            <td class="col-num">{{ fmtMs(item.duration_ms) }}</td>
            <td class="col-num">${{ (item.actual_cost ?? item.total_cost ?? 0).toFixed(6) }}</td>
            <td class="col-expand">
              <span class="expand-icon" :class="{ open: expandedId === item.id }">▶</span>
            </td>
          </tr>
          <tr v-if="expandedId === item.id" class="detail-row">
            <td colspan="11">
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
  transition: background 0.15s;
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

.detail-box {
  padding: 16px 20px;
}

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
  transition: all 0.15s;
}
.pagination button:hover:not(:disabled) { background: #f1f5f9; }
.pagination button:disabled { opacity: 0.4; cursor: default; }
.pagination button.active { background: #2563eb; color: #fff; border-color: #2563eb; }

.page-ellipsis {
  color: #94a3b8;
  padding: 0 4px;
  line-height: 32px;
}

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

.empty {
  color: #94a3b8;
  padding: 40px;
  text-align: center;
}
</style>
