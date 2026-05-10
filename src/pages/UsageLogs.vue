<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed, watch } from 'vue'
import {
  fetchUsageLogs, searchUsers, fetchAccounts, fetchGroups, fetchModels,
  type UsageLogItem, type UsageLogsParams,
  type UserOption, type AccountOption, type GroupOption,
} from '../api/usageLogs'

// ── 筛选状态 ──────────────────────────────────────────────
const filterStartDate = ref('')
const filterEndDate = ref('')
const filterSessionId = ref('')

// 用户搜索下拉
const userKeyword = ref('')
const userOptions = ref<UserOption[]>([])
const userSelected = ref<UserOption | null>(null)
const userDropOpen = ref(false)
const userSearching = ref(false)
let userSearchTimer: ReturnType<typeof setTimeout> | null = null

// 账号下拉（全量，本地过滤）
const accountKeyword = ref('')
const accountOptions = ref<AccountOption[]>([])
const accountSelected = ref<AccountOption | null>(null)
const accountDropOpen = ref(false)

// 分组下拉
const groupOptions = ref<GroupOption[]>([])
const groupSelected = ref<GroupOption | null>(null)
const groupDropOpen = ref(false)
const groupKeyword = ref('')

// 模型下拉
const modelOptions = ref<string[]>([])
const modelSelected = ref('')
const modelDropOpen = ref(false)
const modelKeyword = ref('')

// ── 列表状态 ──────────────────────────────────────────────
const items = ref<UsageLogItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const error = ref('')
const expandedId = ref<number | null>(null)

// ── Tooltip ───────────────────────────────────────────────
const tokenTooltipVisible = ref(false)
const tokenTooltipPos = ref({ x: 0, y: 0 })
const tokenTooltipData = ref<UsageLogItem | null>(null)
const costTooltipVisible = ref(false)
const costTooltipPos = ref({ x: 0, y: 0 })
const costTooltipData = ref<UsageLogItem | null>(null)

// ── 计算 ──────────────────────────────────────────────────
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const filteredAccounts = computed(() => {
  const kw = accountKeyword.value.trim().toLowerCase()
  if (!kw) return accountOptions.value
  return accountOptions.value.filter(a => a.name.toLowerCase().includes(kw))
})

const filteredGroups = computed(() => {
  const kw = groupKeyword.value.trim().toLowerCase()
  if (!kw) return groupOptions.value
  return groupOptions.value.filter(g => g.name.toLowerCase().includes(kw))
})

const filteredModels = computed(() => {
  const kw = modelKeyword.value.trim().toLowerCase()
  if (!kw) return modelOptions.value
  return modelOptions.value.filter(m => m.toLowerCase().includes(kw))
})

// ── 工具函数 ──────────────────────────────────────────────
function defaultDateRange() {
  const end = new Date()
  const start = new Date(end.getTime() - 24 * 60 * 60 * 1000)
  const fmt = (d: Date) => d.toISOString().slice(0, 10)
  return { start: fmt(start), end: fmt(end) }
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
  try { return JSON.stringify(JSON.parse(raw), null, 2) } catch { return raw }
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

// ── 加载数据 ──────────────────────────────────────────────
async function load() {
  loading.value = true
  error.value = ''
  try {
    const params: UsageLogsParams = {
      page: page.value,
      page_size: pageSize.value,
      start_date: filterStartDate.value || undefined,
      end_date: filterEndDate.value || undefined,
      user_id: userSelected.value?.id,
      model: modelSelected.value || undefined,
      session_id: filterSessionId.value || undefined,
      account_id: accountSelected.value?.id,
      group_id: groupSelected.value?.id,
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

async function loadOptions() {
  const [accs, grps, mods] = await Promise.all([
    fetchAccounts().catch(() => []),
    fetchGroups().catch(() => []),
    fetchModels().catch(() => ({ models: [] })),
  ])
  accountOptions.value = accs
  groupOptions.value = grps
  modelOptions.value = (mods as any)?.models?.map((m: any) => m.model).filter(Boolean) ?? []
}

function search() {
  page.value = 1
  void load()
}

function reset() {
  const range = defaultDateRange()
  filterStartDate.value = range.start
  filterEndDate.value = range.end
  filterSessionId.value = ''
  userKeyword.value = ''
  userSelected.value = null
  userOptions.value = []
  accountKeyword.value = ''
  accountSelected.value = null
  groupSelected.value = null
  groupKeyword.value = ''
  modelSelected.value = ''
  modelKeyword.value = ''
  page.value = 1
  void load()
}

// ── 用户搜索 ──────────────────────────────────────────────
function onUserInput() {
  userSelected.value = null
  if (userSearchTimer) clearTimeout(userSearchTimer)
  userSearchTimer = setTimeout(async () => {
    const kw = userKeyword.value.trim()
    if (!kw) { userOptions.value = []; return }
    userSearching.value = true
    userOptions.value = await searchUsers(kw).catch(() => [])
    userSearching.value = false
    userDropOpen.value = true
  }, 300)
}

function selectUser(u: UserOption) {
  userSelected.value = u
  userKeyword.value = u.email
  userDropOpen.value = false
}

function clearUser() {
  userSelected.value = null
  userKeyword.value = ''
  userOptions.value = []
}

// ── 账号选择 ──────────────────────────────────────────────
function selectAccount(a: AccountOption) {
  accountSelected.value = a
  accountKeyword.value = a.name
  accountDropOpen.value = false
}

function clearAccount() {
  accountSelected.value = null
  accountKeyword.value = ''
}

// ── 分组选择 ──────────────────────────────────────────────
function selectGroup(g: GroupOption | null) {
  groupSelected.value = g
  groupDropOpen.value = false
  groupKeyword.value = ''
}

// ── 模型选择 ──────────────────────────────────────────────
function selectModel(m: string) {
  modelSelected.value = m
  modelDropOpen.value = false
  modelKeyword.value = ''
}

function clearModel() {
  modelSelected.value = ''
  modelKeyword.value = ''
}

// ── 展开详情 ──────────────────────────────────────────────
function toggleExpand(item: UsageLogItem) {
  expandedId.value = expandedId.value === item.id ? null : item.id
}

// ── Token tooltip ─────────────────────────────────────────
function showTokenTooltip(event: MouseEvent, item: UsageLogItem) {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  tokenTooltipPos.value = { x: rect.right + 8, y: rect.top + rect.height / 2 }
  tokenTooltipData.value = item
  tokenTooltipVisible.value = true
}
function hideTokenTooltip() { tokenTooltipVisible.value = false; tokenTooltipData.value = null }

// ── 费用 tooltip ──────────────────────────────────────────
function showCostTooltip(event: MouseEvent, item: UsageLogItem) {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  costTooltipPos.value = { x: rect.right + 8, y: rect.top + rect.height / 2 }
  costTooltipData.value = item
  costTooltipVisible.value = true
}
function hideCostTooltip() { costTooltipVisible.value = false; costTooltipData.value = null }

// ── 分页 ──────────────────────────────────────────────────
function prevPage() { if (page.value > 1) { page.value--; void load() } }
function nextPage() { if (page.value < totalPages.value) { page.value++; void load() } }
function goPage(p: number) { page.value = p; void load() }
function onPageSizeChange() { page.value = 1; void load() }

// ── 关闭下拉（点击外部）──────────────────────────────────
function onDocClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.dropdown-wrap')) {
    userDropOpen.value = false
    accountDropOpen.value = false
    groupDropOpen.value = false
    modelDropOpen.value = false
  }
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
  void loadOptions()
  document.addEventListener('click', onDocClick)
  document.addEventListener('scroll', hideAllTooltips, true)
})

onUnmounted(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('scroll', hideAllTooltips, true)
})
</script>

<template>
  <div class="page">
    <!-- 筛选区：两行 -->
    <div class="filter-box">
      <!-- 第一行 -->
      <div class="filter-row">
        <div class="filter-item">
          <span class="filter-label">开始日期</span>
          <input type="date" v-model="filterStartDate" />
        </div>
        <div class="filter-item">
          <span class="filter-label">结束日期</span>
          <input type="date" v-model="filterEndDate" />
        </div>

        <!-- 用户搜索 -->
        <div class="filter-item dropdown-wrap">
          <span class="filter-label">用户</span>
          <div class="search-select" :class="{ active: userDropOpen }">
            <input
              v-model="userKeyword"
              placeholder="搜索邮箱…"
              @input="onUserInput"
              @focus="userDropOpen = userOptions.length > 0"
              class="search-input"
            />
            <span v-if="userSelected" class="clear-btn" @click.stop="clearUser">×</span>
            <div v-if="userDropOpen && (userOptions.length > 0 || userSearching)" class="drop-menu">
              <div v-if="userSearching" class="drop-loading">搜索中…</div>
              <div
                v-for="u in userOptions" :key="u.id"
                class="drop-item"
                :class="{ selected: userSelected?.id === u.id }"
                @click.stop="selectUser(u)"
              >{{ u.email }}</div>
            </div>
          </div>
        </div>

        <!-- 账号下拉 -->
        <div class="filter-item dropdown-wrap">
          <span class="filter-label">账号</span>
          <div class="search-select" :class="{ active: accountDropOpen }">
            <input
              v-model="accountKeyword"
              placeholder="搜索账号…"
              @focus="accountDropOpen = true"
              @input="accountSelected = null"
              class="search-input"
            />
            <span v-if="accountSelected" class="clear-btn" @click.stop="clearAccount">×</span>
            <div v-if="accountDropOpen" class="drop-menu">
              <div
                v-for="a in filteredAccounts" :key="a.id"
                class="drop-item"
                :class="{ selected: accountSelected?.id === a.id }"
                @click.stop="selectAccount(a)"
              >{{ a.name }}</div>
              <div v-if="filteredAccounts.length === 0" class="drop-empty">无匹配</div>
            </div>
          </div>
        </div>

        <div class="filter-item">
          <span class="filter-label">Session ID</span>
          <input type="text" v-model="filterSessionId" placeholder="可选" class="input-lg" />
        </div>
      </div>

      <!-- 第二行 -->
      <div class="filter-row">
        <!-- 分组下拉 -->
        <div class="filter-item dropdown-wrap">
          <span class="filter-label">分组</span>
          <div class="search-select" :class="{ active: groupDropOpen }">
            <div class="select-display" @click.stop="groupDropOpen = !groupDropOpen">
              <span :class="groupSelected ? 'selected-text' : 'placeholder-text'">
                {{ groupSelected ? groupSelected.name : '全部分组' }}
              </span>
              <span class="drop-arrow">{{ groupDropOpen ? '∧' : '∨' }}</span>
            </div>
            <div v-if="groupDropOpen" class="drop-menu">
              <div class="drop-search">
                <input v-model="groupKeyword" placeholder="搜索…" class="drop-search-input" @click.stop />
              </div>
              <div class="drop-item" :class="{ selected: !groupSelected }" @click.stop="selectGroup(null)">
                全部分组
              </div>
              <div
                v-for="g in filteredGroups" :key="g.id"
                class="drop-item"
                :class="{ selected: groupSelected?.id === g.id }"
                @click.stop="selectGroup(g)"
              >{{ g.name }}</div>
              <div v-if="filteredGroups.length === 0" class="drop-empty">无匹配</div>
            </div>
          </div>
        </div>

        <!-- 模型下拉 -->
        <div class="filter-item dropdown-wrap">
          <span class="filter-label">模型</span>
          <div class="search-select" :class="{ active: modelDropOpen }">
            <div class="select-display" @click.stop="modelDropOpen = !modelDropOpen">
              <span :class="modelSelected ? 'selected-text' : 'placeholder-text'">
                {{ modelSelected || '全部模型' }}
              </span>
              <span v-if="modelSelected" class="clear-btn-inline" @click.stop="clearModel">×</span>
              <span v-else class="drop-arrow">{{ modelDropOpen ? '∧' : '∨' }}</span>
            </div>
            <div v-if="modelDropOpen" class="drop-menu drop-menu-lg">
              <div class="drop-search">
                <input v-model="modelKeyword" placeholder="搜索模型…" class="drop-search-input" @click.stop />
              </div>
              <div
                v-for="m in filteredModels" :key="m"
                class="drop-item"
                :class="{ selected: modelSelected === m }"
                @click.stop="selectModel(m)"
              >{{ m }}</div>
              <div v-if="filteredModels.length === 0" class="drop-empty">无匹配</div>
            </div>
          </div>
        </div>

        <div class="filter-actions">
          <button class="btn-primary" :disabled="loading" @click="search">
            {{ loading ? '加载中…' : '查询' }}
          </button>
          <button class="btn-secondary" @click="reset">重置</button>
        </div>
      </div>
    </div>

    <div v-if="error" class="error-msg">{{ error }}</div>

    <div class="total-info" v-if="!loading">
      共 {{ total }} 条记录
    </div>

    <table v-if="items.length > 0" class="log-table">
      <thead>
        <tr>
          <th>时间</th>
          <th>用户</th>
          <th>账号</th>
          <th>分组</th>
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
            <td class="col-group">{{ item.group?.name ?? '-' }}</td>
            <td class="col-model">
              <div class="model-cell">
                <span class="model-name">{{ item.model }}</span>
                <span v-if="item.upstream_model && item.upstream_model !== item.model" class="model-upstream">
                  └ {{ item.upstream_model }}
                </span>
              </div>
            </td>
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
                  <div v-if="item.cache_read_tokens > 0 || item.cache_creation_tokens > 0" class="token-cache-row">
                    <template v-if="item.cache_read_tokens > 0">
                      <span class="cache-icon">🗃</span>
                      <span class="cache-val">{{ fmtCacheTokens(item.cache_read_tokens) }}</span>
                    </template>
                    <template v-if="item.cache_creation_tokens > 0">
                      <span class="cache-create-icon">✎</span>
                      <span class="cache-create-val">{{ fmtCacheTokens(item.cache_creation_tokens) }}</span>
                    </template>
                  </div>
                </div>
                <button class="info-btn" @mouseenter="showTokenTooltip($event, item)" @mouseleave="hideTokenTooltip">ⓘ</button>
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
                <button class="info-btn" @mouseenter="showCostTooltip($event, item)" @mouseleave="hideCostTooltip">ⓘ</button>
              </div>
            </td>

            <td class="col-num">{{ fmtMs(item.first_token_ms) }}</td>
            <td class="col-num">{{ fmtMs(item.duration_ms) }}</td>
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
    <div v-if="total > 0" class="pagination-bar">
      <div class="pagination">
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
      </div>
      <select class="page-size-select" v-model.number="pageSize" @change="onPageSizeChange">
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
        <template v-if="tokenTooltipData.cache_creation_tokens > 0">
          <template v-if="tokenTooltipData.cache_creation_5m_tokens > 0 || tokenTooltipData.cache_creation_1h_tokens > 0">
            <div v-if="tokenTooltipData.cache_creation_5m_tokens > 0" class="tooltip-row">
              <span class="tooltip-label">缓存创建 <span class="badge-5m">5m</span></span>
              <span class="tooltip-val">{{ tokenTooltipData.cache_creation_5m_tokens.toLocaleString() }}</span>
            </div>
            <div v-if="tokenTooltipData.cache_creation_1h_tokens > 0" class="tooltip-row">
              <span class="tooltip-label">缓存创建 <span class="badge-1h">1h</span></span>
              <span class="tooltip-val">{{ tokenTooltipData.cache_creation_1h_tokens.toLocaleString() }}</span>
            </div>
          </template>
          <div v-else class="tooltip-row">
            <span class="tooltip-label">缓存创建 Token</span>
            <span class="tooltip-val">{{ tokenTooltipData.cache_creation_tokens.toLocaleString() }}</span>
          </div>
        </template>
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
        <template v-if="costTooltipData.account_rate_multiplier != null">
          <div class="tooltip-divider" />
          <div class="tooltip-row">
            <span class="tooltip-label">账号倍率</span>
            <span class="tooltip-val price-blue">{{ fmtMultiplier(costTooltipData.account_rate_multiplier) }}x</span>
          </div>
          <div class="tooltip-row">
            <span class="tooltip-label">账号计费</span>
            <span class="tooltip-val price-green">${{ accountBilled(costTooltipData).toFixed(6) }}</span>
          </div>
        </template>
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

/* 筛选区 */
.filter-box {
  background: #fff;
  border: 1px solid #e5e9f2;
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 6px;
  position: relative;
}

.filter-label {
  color: #64748b;
  font-size: 12px;
  white-space: nowrap;
}

.filter-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

input[type="date"],
input[type="text"] {
  background: #fff;
  border: 1px solid #e2e8f0;
  color: #334155;
  border-radius: 6px;
  padding: 5px 8px;
  font-size: 12px;
}

.input-lg { width: 200px; }

/* 搜索下拉组件 */
.search-select {
  position: relative;
  width: 180px;
}

.search-input {
  width: 100%;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 5px 28px 5px 8px;
  font-size: 12px;
  color: #334155;
  box-sizing: border-box;
}

.search-select.active .search-input,
.search-select.active .select-display {
  border-color: #2563eb;
  outline: none;
}

.select-display {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 5px 8px;
  font-size: 12px;
  cursor: pointer;
  user-select: none;
  min-height: 30px;
}

.placeholder-text { color: #94a3b8; }
.selected-text { color: #334155; font-weight: 500; }
.drop-arrow { color: #94a3b8; font-size: 10px; margin-left: 4px; }

.clear-btn {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  color: #94a3b8;
  font-size: 14px;
  cursor: pointer;
  line-height: 1;
}
.clear-btn:hover { color: #475569; }

.clear-btn-inline {
  color: #94a3b8;
  font-size: 14px;
  cursor: pointer;
  padding: 0 2px;
}
.clear-btn-inline:hover { color: #475569; }

.drop-menu {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 100;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 8px 20px rgba(0,0,0,0.1);
  min-width: 100%;
  max-height: 220px;
  overflow-y: auto;
  padding: 4px 0;
}

.drop-menu-lg { width: 280px; }

.drop-search {
  padding: 6px 8px 4px;
  border-bottom: 1px solid #f1f5f9;
}

.drop-search-input {
  width: 100%;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 5px;
  padding: 4px 8px;
  font-size: 12px;
  color: #334155;
  box-sizing: border-box;
}

.drop-item {
  padding: 7px 12px;
  font-size: 12px;
  color: #334155;
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.drop-item:hover { background: #f1f5f9; }
.drop-item.selected { background: #eff6ff; color: #2563eb; font-weight: 500; }

.drop-loading, .drop-empty {
  padding: 10px 12px;
  font-size: 12px;
  color: #94a3b8;
  text-align: center;
}

.btn-primary {
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 6px 18px;
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
  padding: 6px 16px;
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

/* 表格 */
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
.col-group { max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #64748b; }
.col-model { }
.model-cell { display: flex; flex-direction: column; gap: 1px; }
.model-name { font-weight: 500; color: #0f172a; }
.model-upstream { font-size: 11px; color: #64748b; padding-left: 2px; }
.col-session { max-width: 120px; }
.col-num { text-align: right; font-variant-numeric: tabular-nums; }
.col-expand { text-align: center; width: 36px; }

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
.cache-create-icon { font-size: 11px; color: #d97706; margin-left: 4px; }
.cache-create-val { font-weight: 500; color: #d97706; font-size: 12px; }

.col-cost { white-space: nowrap; }
.cost-cell { display: flex; align-items: center; gap: 6px; }
.cost-main { display: flex; flex-direction: column; gap: 2px; }
.cost-user { font-weight: 600; color: #16a34a; font-variant-numeric: tabular-nums; }
.cost-account { font-size: 11px; color: #f97316; font-variant-numeric: tabular-nums; }

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

.detail-row td { padding: 0; background: #f8fafc; border-bottom: 1px solid #e5e9f2; }
.detail-box { padding: 16px 20px; }
.detail-meta { display: flex; gap: 24px; margin-bottom: 12px; font-size: 12px; color: #475569; flex-wrap: wrap; }

.body-panels { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.body-panel { background: #1e293b; border-radius: 8px; overflow: hidden; }
.panel-title {
  background: #334155; color: #94a3b8; font-size: 11px; font-weight: 600;
  padding: 6px 12px; text-transform: uppercase; letter-spacing: 0.05em;
}
.body-pre {
  color: #e2e8f0;
  font-family: 'JetBrains Mono', 'Fira Code', 'Menlo', monospace;
  font-size: 11px; line-height: 1.6; padding: 12px; margin: 0;
  max-height: 400px; overflow-y: auto; white-space: pre-wrap; word-break: break-all;
}

/* 分页 */
.pagination-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  justify-content: center;
}

.pagination {
  display: flex;
  align-items: center;
  gap: 4px;
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
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 5px 8px;
  font-size: 12px;
  background: #fff;
  color: #475569;
  cursor: pointer;
  height: 32px;
}

.empty { color: #94a3b8; padding: 40px; text-align: center; }
</style>

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
  box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.tooltip-title { font-size: 12px; font-weight: 600; color: #d1d5db; margin-bottom: 4px; }

.tooltip-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; }

.tooltip-label { font-size: 12px; color: #9ca3af; white-space: nowrap; }

.tooltip-val { font-size: 12px; font-weight: 500; color: #f9fafb; font-variant-numeric: tabular-nums; }

.tooltip-divider { height: 1px; background: #374151; margin: 4px 0; }

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
  width: 0; height: 0;
  border-top: 6px solid transparent;
  border-bottom: 6px solid transparent;
  border-right: 6px solid #374151;
}

.badge-5m, .badge-1h {
  display: inline-block;
  padding: 0 5px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  line-height: 1.5;
  vertical-align: middle;
}
.badge-5m { background: rgba(251,146,60,0.2); color: #fb923c; }
.badge-1h  { background: rgba(167,139,250,0.2); color: #a78bfa; }
</style>
