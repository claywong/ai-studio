<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api } from './api/client'
import { generateImage } from './api/images'
import { listTokens, type StudioToken } from './api/tokens'

const aspectRatios = [
  { label: '1:1 正方形', value: '1:1' },
  { label: '16:9 横向宽屏', value: '16:9' },
  { label: '9:16 竖向', value: '9:16' },
  { label: '4:3 横向标准', value: '4:3' },
  { label: '3:4 竖向标准', value: '3:4' },
]

const sizeLabels = ['1K', '2K']
const models = ['gpt-image-2']
const HISTORY_STORAGE_KEY = 'g7e6_ai_studio_image_history'
const MAX_HISTORY_ITEMS = 30
const MAX_REFERENCE_IMAGES = 3

interface HistoryItem {
  id: string
  prompt: string
  image: string
  model: string
  size: string
  aspectRatio: string
  createdAt: string
  revisedPrompt?: string
}

const prompt = ref('')
const aspectRatio = ref('1:1')
const sizeLabel = ref('1K')
const model = ref('gpt-image-2')
const isGenerating = ref(false)
const errorMessage = ref('')
const tokenErrorMessage = ref('')
const isLoadingTokens = ref(false)
const selectedTokenId = ref<number | ''>('')
const studioTokens = ref<StudioToken[]>([])
const isHistoryOpen = ref(false)
const historyItems = ref<HistoryItem[]>([])
const generatedImage = ref('')
const revisedPrompt = ref('')
const generationStartedAt = ref<number | null>(null)
const nowMs = ref(Date.now())
let loadingTimer: number | undefined
const referenceImages = ref<File[]>([])
const referenceImagePreviews = ref<string[]>([])
const devToken = ref(localStorage.getItem('auth_token') ?? '')
const showDevTokenPanel = import.meta.env.DEV
const isAuthReady = ref(import.meta.env.DEV)
const loginUrl = `/login?redirect=${encodeURIComponent('/studio/')}`

function redirectToLogin() {
  window.location.href = loginUrl
}

async function ensureLogin() {
  const token = localStorage.getItem('auth_token')

  if (!token) {
    if (import.meta.env.DEV) {
      isAuthReady.value = true
      void loadTokens()
      return
    }

    redirectToLogin()
    return
  }

  try {
    await api.get('/auth/me')
    isAuthReady.value = true
    void loadTokens()
  } catch {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('auth_user')

    if (import.meta.env.DEV) {
      isAuthReady.value = true
      return
    }

    redirectToLogin()
  }
}

onMounted(() => {
  void ensureLogin()
  loadHistory()
  loadingTimer = window.setInterval(() => {
    nowMs.value = Date.now()
  }, 1000)
})

onUnmounted(() => {
  if (loadingTimer) {
    window.clearInterval(loadingTimer)
  }
  revokeReferencePreviews()
})

const canGenerate = computed(() => prompt.value.trim().length > 0 && !isGenerating.value)
const previewImageUrl = computed(() => generatedImage.value ? `data:image/png;base64,${generatedImage.value}` : '')
const hasHistory = computed(() => historyItems.value.length > 0)
const selectedToken = computed(() => studioTokens.value.find(token => token.id === selectedTokenId.value) ?? null)

const loadingSubtitle = computed(() => {
  if (!generationStartedAt.value) {
    return '正在连接图片模型'
  }

  const seconds = Math.max(1, Math.floor((nowMs.value - generationStartedAt.value) / 1000))
  return `已等待 ${seconds} 秒，高清图片通常需要 30-120 秒`
})

async function loadTokens() {
  isLoadingTokens.value = true
  tokenErrorMessage.value = ''
  try {
    const tokens = await listTokens()
    studioTokens.value = tokens
    if (!selectedTokenId.value && tokens.length > 0) {
      selectedTokenId.value = tokens[0].id
    }
  } catch (error) {
    const maybeError = error as { response?: { data?: { detail?: unknown } }; message?: string }
    const detail = maybeError.response?.data?.detail
    tokenErrorMessage.value = typeof detail === 'string' ? detail : maybeError.message || '令牌加载失败'
  } finally {
    isLoadingTokens.value = false
  }
}

function openKeysPage() {
  window.open('https://g7e6ai.com/keys', '_blank', 'noopener,noreferrer')
}

function loadHistory() {
  try {
    const rawHistory = localStorage.getItem(HISTORY_STORAGE_KEY)
    if (!rawHistory) return

    const parsed = JSON.parse(rawHistory) as HistoryItem[]
    if (Array.isArray(parsed)) {
      historyItems.value = parsed.filter(item => item?.id && item?.image).slice(0, MAX_HISTORY_ITEMS)
    }
  } catch {
    historyItems.value = []
  }
}

function persistHistory() {
  localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(historyItems.value.slice(0, MAX_HISTORY_ITEMS)))
}

function addHistoryItem(image: string, size: string, revised?: string) {
  const item: HistoryItem = {
    id: crypto.randomUUID(),
    prompt: prompt.value.trim(),
    image,
    model: model.value,
    size,
    aspectRatio: aspectRatio.value,
    createdAt: new Date().toISOString(),
    revisedPrompt: revised,
  }
  historyItems.value = [item, ...historyItems.value].slice(0, MAX_HISTORY_ITEMS)
  persistHistory()
}

function selectHistoryItem(item: HistoryItem) {
  generatedImage.value = item.image
  revisedPrompt.value = item.revisedPrompt ?? ''
  prompt.value = item.prompt
  model.value = item.model
  aspectRatio.value = item.aspectRatio
  isHistoryOpen.value = false
}

function clearHistory() {
  historyItems.value = []
  localStorage.removeItem(HISTORY_STORAGE_KEY)
}

function formatHistoryTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function saveDevToken() {
  const normalizedToken = devToken.value.trim()
  if (normalizedToken) {
    localStorage.setItem('auth_token', normalizedToken)
  } else {
    localStorage.removeItem('auth_token')
  }
}

function clearDevToken() {
  devToken.value = ''
  localStorage.removeItem('auth_token')
}

function revokeReferencePreviews() {
  for (const previewUrl of referenceImagePreviews.value) {
    URL.revokeObjectURL(previewUrl)
  }
}

function setReferenceImages(files: File[]) {
  revokeReferencePreviews()
  referenceImages.value = files.slice(0, 3)
  referenceImagePreviews.value = referenceImages.value.map(file => URL.createObjectURL(file))
}

function handleReferenceChange(event: Event) {
  const input = event.target as HTMLInputElement
  const incomingFiles = Array.from(input.files ?? [])
    .filter(file => file.type.startsWith('image/'))
    .filter(file => file.size <= 5 * 1024 * 1024)

  const mergedFiles = [...referenceImages.value]
  for (const file of incomingFiles) {
    const alreadyExists = mergedFiles.some(existingFile =>
      existingFile.name === file.name
      && existingFile.size === file.size
      && existingFile.lastModified === file.lastModified,
    )
    if (!alreadyExists && mergedFiles.length < MAX_REFERENCE_IMAGES) {
      mergedFiles.push(file)
    }
  }

  setReferenceImages(mergedFiles)
  input.value = ''
}

function removeReferenceImage(index: number) {
  const nextFiles = referenceImages.value.filter((_, fileIndex) => fileIndex !== index)
  setReferenceImages(nextFiles)
}

function downloadImage() {
  if (!previewImageUrl.value) return
  const link = document.createElement('a')
  link.href = previewImageUrl.value
  link.download = `g7e6-ai-studio-${new Date().toISOString().replace(/[:.]/g, '-')}.png`
  link.click()
}

async function submit() {
  if (!canGenerate.value) return
  if (!selectedToken.value) {
    tokenErrorMessage.value = '请先选择或生成一个 OpenAI 令牌'
    return
  }
  isGenerating.value = true
  generationStartedAt.value = Date.now()
  errorMessage.value = ''
  revisedPrompt.value = ''

  try {
    const result = await generateImage({
      prompt: prompt.value.trim(),
      aspect_ratio: aspectRatio.value,
      size_label: sizeLabel.value,
      model: model.value,
      reference_images: referenceImages.value,
      token_id: selectedToken.value.id,
    })
    const firstImage = result.images[0]
    if (!firstImage) {
      throw new Error('图片服务没有返回图片')
    }
    generatedImage.value = firstImage.b64_json
    revisedPrompt.value = firstImage.revised_prompt ?? ''
    addHistoryItem(firstImage.b64_json, result.size, firstImage.revised_prompt)
  } catch (error) {
    const maybeError = error as { response?: { data?: { detail?: unknown } }; message?: string }
    const detail = maybeError.response?.data?.detail
    errorMessage.value = typeof detail === 'string' ? detail : maybeError.message || '生成失败，请稍后重试'
  } finally {
    isGenerating.value = false
    generationStartedAt.value = null
  }
}
</script>

<template>
  <main class="page-shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">G7E6 AI Studio</p>
        <h1>图片生成工作台</h1>
      </div>
      <a class="back-link" href="/">返回主站</a>
    </header>

    <section v-if="showDevTokenPanel" class="dev-token-panel">
      <div>
        <strong>开发登录</strong>
        <span>从 G7e6ai.com 复制 localStorage.auth_token，粘贴后即可本地复用登录态。</span>
      </div>
      <input v-model="devToken" type="password" placeholder="粘贴 auth_token" @keyup.enter="saveDevToken">
      <button type="button" @click="saveDevToken">保存</button>
      <button class="ghost-button" type="button" @click="clearDevToken">清空</button>
    </section>

    <section v-if="isAuthReady" class="workspace">
      <form class="panel control-panel" @submit.prevent="submit">
        <div class="field prompt-field">
          <label for="prompt">提示词</label>
          <textarea
            id="prompt"
            v-model="prompt"
            maxlength="5000"
            placeholder="描述你想创建的图片..."
          />
          <div class="counter">{{ prompt.length }} / 5000</div>
        </div>

        <div class="field">
          <label>参考图片（可选，1-3张）</label>
          <div class="reference-upload-box" :class="{ 'has-files': referenceImages.length > 0 }">
            <div
              v-for="(file, index) in referenceImages"
              :key="`${file.name}-${index}`"
              class="reference-upload-card"
              :title="file.name"
            >
              <img :src="referenceImagePreviews[index]" :alt="file.name">
              <button type="button" aria-label="移除参考图" @click="removeReferenceImage(index)">×</button>
            </div>

            <label v-if="referenceImages.length < MAX_REFERENCE_IMAGES" class="reference-add-card">
              <input type="file" accept="image/jpeg,image/png,image/webp" multiple @change="handleReferenceChange">
              <span class="upload-icon">▧</span>
              <strong>{{ referenceImages.length === 0 ? '点击或拖拽图片到这里' : '继续添加参考图' }}</strong>
              <small>JPEG, PNG, WebP · 每张最大5MB · 最多3张</small>
            </label>
          </div>
          <div class="counter">{{ referenceImages.length }} / 3 张图片</div>
        </div>

        <div class="field token-row">
          <label>令牌</label>
          <div class="token-controls">
            <select v-model="selectedTokenId" :disabled="isLoadingTokens || studioTokens.length === 0">
              <option value="" disabled>{{ isLoadingTokens ? '加载令牌中...' : '选择令牌' }}</option>
              <option v-for="token in studioTokens" :key="token.id" :value="token.id">
                {{ token.name }} · {{ token.group_name || 'OpenAI' }}
              </option>
            </select>
            <button class="secondary-button" type="button" @click="openKeysPage">
              生成令牌
            </button>
          </div>
          <p v-if="tokenErrorMessage" class="error-message">{{ tokenErrorMessage }}</p>
        </div>

        <div class="option-grid">
          <label class="field">
            <span>宽高比</span>
            <select v-model="aspectRatio">
              <option v-for="item in aspectRatios" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
          </label>
          <label class="field">
            <span>图片尺寸</span>
            <select v-model="sizeLabel">
              <option v-for="item in sizeLabels" :key="item" :value="item">{{ item }}</option>
            </select>
          </label>
          <label class="field">
            <span>模型</span>
            <select v-model="model">
              <option v-for="item in models" :key="item" :value="item">{{ item }}</option>
            </select>
          </label>
        </div>

        <button class="generate-button" type="submit" :disabled="!canGenerate">
          {{ isGenerating ? '生成中...' : '生成图片' }}
        </button>
        <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
      </form>

      <section class="panel preview-panel">
        <div v-if="isGenerating" class="loading-state">
          <div class="spinner-ring"></div>
          <h2>正在生成图片</h2>
          <p>{{ loadingSubtitle }}</p>
          <div class="progress-track">
            <div class="progress-bar"></div>
          </div>
          <span>请保持页面打开，完成后会自动展示结果</span>
        </div>
        <div v-else-if="previewImageUrl" class="result-wrap">
          <img :src="previewImageUrl" alt="生成结果">
          <button class="download-button" type="button" @click="downloadImage">下载图片</button>
          <p v-if="revisedPrompt" class="revised-prompt">修订提示词：{{ revisedPrompt }}</p>
        </div>
        <div v-else class="empty-state">
          <div class="orb"></div>
          <p>你的图片将在这里展示</p>
        </div>
      </section>
    </section>

    <button class="history-button" type="button" title="历史记录" @click="isHistoryOpen = true">◷</button>

    <div v-if="isHistoryOpen" class="history-backdrop" @click="isHistoryOpen = false"></div>
    <aside class="history-drawer" :class="{ 'is-open': isHistoryOpen }" aria-label="生图历史">
      <header class="history-header">
        <h2>生图历史</h2>
        <button type="button" aria-label="关闭" @click="isHistoryOpen = false">×</button>
      </header>

      <div v-if="!hasHistory" class="history-empty">
        <div class="history-empty-icon">▧</div>
        <strong>还没有生图记录</strong>
        <span>生成第一张图片后将在这里显示</span>
      </div>

      <div v-else class="history-content">
        <button class="clear-history-button" type="button" @click="clearHistory">清空历史</button>
        <button
          v-for="item in historyItems"
          :key="item.id"
          class="history-card"
          type="button"
          @click="selectHistoryItem(item)"
        >
          <img :src="`data:image/png;base64,${item.image}`" alt="历史图片">
          <div>
            <strong>{{ item.prompt }}</strong>
            <span>{{ item.model }} · {{ item.size }} · {{ formatHistoryTime(item.createdAt) }}</span>
          </div>
        </button>
      </div>
    </aside>
  </main>
</template>
