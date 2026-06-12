<script setup lang="ts">
import { onMounted, ref, computed, watch } from 'vue'
import { api } from '../api/client'

// 加权选号常量（与 sub2api 线上默认值一致）
const EPS = 0.10 // 相近带宽度
const BETA = 1.0 // 成本权重陡峭度
const FLOOR = 0.05 // 带外探索保底
const MIN_RATE = 0.05 // 倍率下限
const NEUTRAL_SCORE = 0.5 // 无质量样本中性分

interface GroupItem {
  id: number
  name: string
}

interface AccountItem {
  id: number
  name: string
  priority: number
  status: string
  platform: string
  rate_multiplier: number | null
  concurrency: number
  current_concurrency: number
  model_mapping_keys: string[] | null
  schedulable: boolean
  groups: { id: number; name: string }[]
}

interface QualityItem {
  account_id: number
  model: string
  score: number
}

// 计算后的候选账号视图
interface Candidate {
  id: number
  name: string
  priority: number
  rate: number // clamp 后的倍率
  rawRate: number | null // 原始倍率
  score: number
  hasSample: boolean // 是否有质量样本
  inBand: boolean
  weight: number
  prob: number // 命中概率 0~1
  loadRate: number // 负载率 %
  schedulable: boolean
  eligible: boolean // 是否进入本轮竞争
  reason: string // 不参与原因
}

interface PriorityTier {
  priority: number
  candidates: Candidate[]
}

const groups = ref<GroupItem[]>([])
const accounts = ref<AccountItem[]>([])
const qualities = ref<QualityItem[]>([])
const loading = ref(false)
const error = ref('')
const lastUpdated = ref('')

const selectedGroup = ref<number | ''>('')
const selectedModel = ref('')

// PLACEHOLDER_SCRIPT

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [gRes, aRes] = await Promise.all([
      api.get('/admin/reports/groups'),
      api.get('/admin/reports/accounts-list'),
    ])
    groups.value = (gRes.data ?? []) as GroupItem[]
    accounts.value = (aRes.data ?? []) as AccountItem[]
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

// 切换分组时拉取该组所有账号的质量数据（用于选模型 + 取 score）
async function loadQuality() {
  qualities.value = []
  selectedModel.value = ''
  if (selectedGroup.value === '') return
  try {
    // quality 不支持按 group 过滤，全量拉取后按候选账号匹配
    const res = await api.get('/admin/reports/scheduler-quality')
    qualities.value = (res.data ?? []) as QualityItem[]
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

watch(selectedGroup, () => void loadQuality())

// 当前分组的候选账号（schedulable 的活跃账号）
const groupAccounts = computed(() => {
  if (selectedGroup.value === '') return []
  const gid = Number(selectedGroup.value)
  return accounts.value.filter((a) => a.groups.some((g) => g.id === gid))
})

// 可选模型列表：该组账号支持的具体模型
// = quality 样本出现过的 model ∪ 各账号 model_mapping 的非通配符键
const availableModels = computed(() => {
  const ids = new Set(groupAccounts.value.map((a) => a.id))
  const models = new Set<string>()
  for (const q of qualities.value) {
    if (ids.has(q.account_id)) models.add(q.model)
  }
  for (const a of groupAccounts.value) {
    for (const k of a.model_mapping_keys ?? []) {
      if (!k.endsWith('*')) models.add(k)
    }
  }
  return [...models].sort()
})

function clampRate(rate: number | null): number {
  const r = rate == null ? 1.0 : rate
  return r < MIN_RATE ? MIN_RATE : r
}

// 复刻 sub2api Account.IsModelSupported：
// model_mapping 为空 → 支持所有模型；否则模型须精确命中键，或命中末尾 * 前缀通配
function isModelSupported(keys: string[] | null, model: string): boolean {
  if (!keys || keys.length === 0) return true
  if (keys.includes(model)) return true
  for (const k of keys) {
    if (k.endsWith('*') && model.startsWith(k.slice(0, -1))) return true
  }
  return false
}

function loadRateOf(a: AccountItem): number {
  if (!a.concurrency || a.concurrency <= 0) return 0
  return Math.round((a.current_concurrency / a.concurrency) * 100)
}

// 核心：按优先级分层 + 算命中概率
const tiers = computed<PriorityTier[]>(() => {
  if (selectedGroup.value === '' || !selectedModel.value) return []
  const model = selectedModel.value

  // score 查表
  const scoreMap = new Map<number, number>()
  for (const q of qualities.value) {
    if (q.model === model) scoreMap.set(q.account_id, q.score)
  }

  // 1. 构造候选：先剔除不支持该模型的账号（真实调度不进候选集）
  const supported = groupAccounts.value.filter((a) => isModelSupported(a.model_mapping_keys, model))
  const cands: Candidate[] = supported.map((a) => {
    const loadRate = loadRateOf(a)
    const hasSample = scoreMap.has(a.id)
    const score = hasSample ? (scoreMap.get(a.id) as number) : NEUTRAL_SCORE
    let eligible = true
    let reason = ''
    if (!a.schedulable) {
      eligible = false
      reason = '不可调度'
    } else if (a.status !== 'active') {
      eligible = false
      reason = a.status || '非活跃'
    } else if (loadRate >= 100) {
      eligible = false
      reason = '负载满'
    }
    return {
      id: a.id,
      name: a.name,
      priority: a.priority,
      rate: clampRate(a.rate_multiplier),
      rawRate: a.rate_multiplier,
      score,
      hasSample,
      inBand: false,
      weight: 0,
      prob: 0,
      loadRate,
      schedulable: a.schedulable,
      eligible,
      reason,
    }
  })

  // 2. 仅 eligible 参与分层竞争
  const eligible = cands.filter((c) => c.eligible)
  const byPriority = new Map<number, Candidate[]>()
  for (const c of eligible) {
    const arr = byPriority.get(c.priority)
    if (arr) arr.push(c)
    else byPriority.set(c.priority, [c])
  }

  // 3. filterByMinPriority：调度只在最小 priority 层竞争，但页面展示所有层
  const priorities = [...byPriority.keys()].sort((a, b) => a - b)

  const result: PriorityTier[] = []
  for (const p of priorities) {
    const layer = byPriority.get(p) as Candidate[]
    computeProbabilities(layer)
    layer.sort((a, b) => b.prob - a.prob)
    result.push({ priority: p, candidates: layer })
  }

  // 把不参与的账号挂到各自 priority 层尾部（灰显）
  const ineligible = cands.filter((c) => !c.eligible)
  for (const c of ineligible) {
    let tier = result.find((t) => t.priority === c.priority)
    if (!tier) {
      tier = { priority: c.priority, candidates: [] }
      result.push(tier)
    }
    tier.candidates.push(c)
  }
  result.sort((a, b) => a.priority - b.priority)
  return result
})

// 复刻 selectByWeightedQuality 的带/权重/概率计算
function computeProbabilities(layer: Candidate[]) {
  if (layer.length === 0) return
  if (layer.length === 1) {
    layer[0].inBand = true
    layer[0].weight = 1
    layer[0].prob = 1
    return
  }
  const bestScore = Math.max(...layer.map((c) => c.score))
  let maxInBand = 0
  for (const c of layer) {
    if (c.score >= bestScore - EPS) {
      c.inBand = true
      c.weight = Math.pow(1 / c.rate, BETA)
      if (c.weight > maxInBand) maxInBand = c.weight
    } else {
      c.inBand = false
    }
  }
  const floorWeight = FLOOR * maxInBand
  let total = 0
  for (const c of layer) {
    if (!c.inBand) c.weight = floorWeight
    total += c.weight
  }
  for (const c of layer) {
    c.prob = total > 0 ? c.weight / total : 0
  }
}

const minPriority = computed(() => {
  const ts = tiers.value.filter((t) => t.candidates.some((c) => c.eligible))
  return ts.length ? ts[0].priority : null
})

function isActiveTier(t: PriorityTier): boolean {
  return t.priority === minPriority.value
}

function eligibleCount(t: PriorityTier): number {
  return t.candidates.filter((c) => c.eligible).length
}

function fmtPct(v: number): string {
  return (v * 100).toFixed(1) + '%'
}

function fmtRate(rate: number | null): string {
  if (rate == null) return '1.00'
  return rate.toFixed(2)
}

function scoreClass(score: number, hasSample: boolean): string {
  if (!hasSample) return ''
  if (score >= 0.8) return 'ttft-good'
  if (score >= 0.65) return 'ttft-ok'
  if (score >= 0.5) return 'ttft-warn'
  return 'ttft-bad'
}

function loadClass(rate: number): string {
  if (rate >= 100) return 'ttft-bad'
  if (rate >= 80) return 'ttft-warn'
  if (rate >= 50) return 'ttft-ok'
  return 'ttft-good'
}

onMounted(() => {
  void load()
})

</script>

<template>
  <div class="page">
    <div class="toolbar">
      <span class="title">调度选号透视</span>

      <div class="filter-item">
        <span class="filter-label">分组</span>
        <select v-model="selectedGroup">
          <option value="">请选择</option>
          <option v-for="g in groups" :key="g.id" :value="g.id">{{ g.name }}</option>
        </select>
      </div>

      <div class="filter-item">
        <span class="filter-label">模型</span>
        <select v-model="selectedModel" :disabled="availableModels.length === 0">
          <option value="">请选择</option>
          <option v-for="m in availableModels" :key="m" :value="m">{{ m }}</option>
        </select>
      </div>

      <button class="btn-refresh" :disabled="loading" @click="load">
        {{ loading ? '加载中…' : '刷新' }}
      </button>
      <span v-if="lastUpdated" class="updated">更新于 {{ lastUpdated }}</span>
    </div>

    <div v-if="error" class="error-msg">{{ error }}</div>

    <!-- 算法说明 -->
    <div class="note">
      加权随机选号（线上已启用）。同一分组下，调度只在<b>优先级数值最小</b>的一层竞争；
      层内按质量分划「相近带」(score ≥ 最高分 − {{ EPS }})，带内按倍率倒数加权
      (weight = (1/倍率)^{{ BETA }})，带外给 {{ FLOOR * 100 }}% 探索保底，命中概率 = 权重占比。
      <br />
      <span class="note-dim">
        注：score 取调度质量窗口综合分（无样本按 {{ NEUTRAL_SCORE }} 中性分）；负载为近似值；
        未纳入配额/RPM/健康等次级过滤，故为「理论候选」。这是<b>倾向概率</b>，非每次必选最高分。
      </span>
    </div>

    <div v-if="selectedGroup === ''" class="empty">请选择分组与模型</div>
    <div v-else-if="!selectedModel" class="empty">请选择模型</div>
    <div v-else-if="tiers.length === 0" class="empty">该分组下没有候选账号</div>

    <template v-else>
      <div
        v-for="tier in tiers"
        :key="tier.priority"
        class="tier"
        :class="{ 'tier-active': isActiveTier(tier) }"
      >
        <div class="tier-head">
          <span class="tier-name">优先级 {{ tier.priority }}</span>
          <span class="tier-count">{{ eligibleCount(tier) }} 个候选</span>
          <span v-if="isActiveTier(tier)" class="tier-badge">← 调度发生在此层</span>
          <span v-else class="tier-dim">优先级更低，仅当上层全部不可用时才参与</span>
        </div>

        <table class="data-table">
          <thead>
            <tr>
              <th>账号名</th>
              <th>倍率</th>
              <th>质量分</th>
              <th>相近带</th>
              <th>权重</th>
              <th>命中概率</th>
              <th>负载</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="c in tier.candidates"
              :key="c.id"
              :class="{ 'row-out': !c.eligible, 'row-top': c.eligible && isActiveTier(tier) && c.prob > 0 && c.prob === Math.max(...tier.candidates.map((x) => x.prob)) }"
            >
              <td class="col-name">{{ c.name }}</td>
              <td class="col-num">{{ fmtRate(c.rawRate) }}</td>
              <td class="col-num" :class="scoreClass(c.score, c.hasSample)">
                {{ c.score.toFixed(2) }}<span v-if="!c.hasSample" class="q-sample">中性</span>
              </td>
              <td class="col-center">
                <span v-if="!c.eligible" class="q-empty">-</span>
                <span v-else-if="c.inBand" class="badge band-in">带内</span>
                <span v-else class="badge band-out">探索</span>
              </td>
              <td class="col-num">{{ c.eligible ? c.weight.toFixed(3) : '-' }}</td>
              <td class="col-prob">
                <template v-if="c.eligible">
                  <div class="prob-bar-wrap">
                    <div class="prob-bar" :style="{ width: (c.prob * 100).toFixed(1) + '%' }"></div>
                    <span class="prob-val">{{ fmtPct(c.prob) }}</span>
                  </div>
                </template>
                <span v-else class="q-empty">-</span>
              </td>
              <td class="col-num" :class="loadClass(c.loadRate)">{{ c.loadRate }}%</td>
              <td class="col-center">
                <span v-if="c.eligible" class="badge status-active">参与</span>
                <span v-else class="badge status-out">{{ c.reason }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
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
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  margin-right: 8px;
}

.filter-item { display: flex; align-items: center; gap: 6px; }
.filter-label { color: #64748b; font-size: 12px; }

select {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  color: #334155;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
}
select:disabled { opacity: 0.5; cursor: default; }

.btn-refresh {
  background: #2563eb;
  color: #ffffff;
  border: none;
  border-radius: 6px;
  padding: 5px 14px;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-refresh:hover:not(:disabled) { background: #1d4ed8; }
.btn-refresh:disabled { opacity: 0.5; cursor: default; }

.updated { color: #94a3b8; font-size: 11px; }

.note {
  background: #ffffff;
  border: 1px solid #e5e9f2;
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 16px;
  color: #475569;
  font-size: 12px;
  line-height: 1.7;
}
.note b { color: #0f172a; }
.note-dim { color: #94a3b8; font-size: 11px; }

/* STYLE_PLACEHOLDER */

/* 优先级层 */
.tier {
  background: #ffffff;
  border: 1px solid #e5e9f2;
  border-radius: 10px;
  margin-bottom: 14px;
  overflow: hidden;
}
.tier-active { border-color: #2563eb; box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.15); }

.tier-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  background: #f8fafc;
  border-bottom: 1px solid #e5e9f2;
}
.tier-name { font-weight: 700; color: #0f172a; font-size: 13px; }
.tier-count { color: #94a3b8; font-size: 11px; }
.tier-badge { color: #2563eb; font-size: 11px; font-weight: 600; }
.tier-dim { color: #cbd5e1; font-size: 11px; }

.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th {
  background: #ffffff;
  color: #64748b;
  font-weight: 600;
  padding: 7px 12px;
  text-align: left;
  border-bottom: 1px solid #f1f5f9;
  white-space: nowrap;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.data-table td {
  padding: 7px 12px;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: middle;
  color: #475569;
}
.data-table tbody tr:last-child td { border-bottom: none; }
.data-table tr:hover td { background: #f8fafc; }

.row-out td { opacity: 0.5; }
.row-top td { background: rgba(37, 99, 235, 0.05); }

.col-name { font-weight: 500; color: #0f172a; }
.col-num { text-align: right; font-variant-numeric: tabular-nums; }
.col-center { text-align: center; }
.col-prob { width: 200px; }

.badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}
.band-in { background: #dbeafe; color: #2563eb; }
.band-out { background: #f1f5f9; color: #94a3b8; }
.status-active { background: #dcfce7; color: #16a34a; }
.status-out { background: #f1f5f9; color: #94a3b8; }

.q-empty { color: #cbd5e1; }
.q-sample { color: #cbd5e1; font-size: 10px; margin-left: 3px; }

/* 命中概率条 */
.prob-bar-wrap {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
}
.prob-bar {
  height: 14px;
  background: linear-gradient(90deg, #60a5fa, #2563eb);
  border-radius: 3px;
  min-width: 2px;
  flex-shrink: 0;
  transition: width 0.2s;
}
.prob-val { font-variant-numeric: tabular-nums; color: #334155; font-weight: 600; }

/* 四档数值着色 */
.ttft-good { color: #16a34a; font-weight: 600; }
.ttft-ok   { color: #65a30d; font-weight: 600; }
.ttft-warn { color: #d97706; font-weight: 600; }
.ttft-bad  { color: #dc2626; font-weight: 600; }

.error-msg { color: #dc2626; margin-bottom: 12px; }
.empty { color: #94a3b8; padding: 40px; text-align: center; }

</style>

