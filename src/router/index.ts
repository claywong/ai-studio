import { createRouter, createWebHistory } from 'vue-router'
import ImageStudio from '../pages/ImageStudio.vue'
import AdminReports from '../pages/AdminReports.vue'
import AdminReportsFull from '../pages/AdminReportsFull.vue'
import ChannelStatus from '../pages/ChannelStatus.vue'
import UserTrend from '../pages/UserTrend.vue'
import AccountLatency from '../pages/AccountLatency.vue'
import AccountMonitorChart from '../pages/AccountMonitorChart.vue'
import AccountUsageTimeline from '../pages/AccountUsageTimeline.vue'
import AccountHealthStatus from '../pages/AccountHealthStatus.vue'
import UsageLogs from '../pages/UsageLogs.vue'

// AI工作组推广小组 成员邮箱白名单（可访问 /images 和 /admin/reports）
const REPORTER_EMAILS = new Set([
  'xiqiang@g7.com.cn',
  'liuyunyang@g7.com.cn',
  'wangzhong@g7.com.cn',
  'wanghao_cd@g7.com.cn',
  'denglei@g7.com.cn',
  'guijiabin@g7.com.cn',
])

export function isAdmin(): boolean {
  try {
    const user = JSON.parse(localStorage.getItem('auth_user') ?? '{}') as { role?: string }
    return user.role === 'admin'
  } catch {
    return false
  }
}

export function isReporter(): boolean {
  try {
    const user = JSON.parse(localStorage.getItem('auth_user') ?? '{}') as { role?: string; email?: string }
    if (user.role === 'admin') return true
    return !!user.email && REPORTER_EMAILS.has(user.email)
  } catch {
    return false
  }
}

const router = createRouter({
  history: createWebHistory('/app/ai/'),
  routes: [
    { path: '/', redirect: '/images' },
    { path: '/images', component: ImageStudio },
    {
      path: '/admin/reports',
      component: AdminReports,
      meta: { requiresReporter: true },
    },
    {
      path: '/admin/reports-full',
      component: AdminReportsFull,
      meta: { requiresAdmin: true },
    },
    {
      path: '/admin/channel-status',
      component: ChannelStatus,
      meta: { requiresAdmin: true },
    },
    {
      path: '/admin/user-trend',
      component: UserTrend,
      meta: { requiresAdmin: true },
    },
    {
      path: '/admin/account-latency',
      component: AccountLatency,
      meta: { requiresAdmin: true },
    },
    {
      path: '/admin/account-monitor-chart',
      component: AccountMonitorChart,
      meta: { requiresAdmin: true },
    },
    {
      path: '/admin/account-usage-timeline',
      component: AccountUsageTimeline,
      meta: { requiresAdmin: true },
    },
    {
      path: '/admin/account-health',
      component: AccountHealthStatus,
      meta: { requiresAdmin: true },
    },
    {
      path: '/admin/usage-logs',
      component: UsageLogs,
      meta: { requiresAdmin: true },
    },
  ],
})

router.beforeEach((to) => {
  const rawUser = localStorage.getItem('auth_user')

  if (to.meta.requiresAdmin) {
    if (!rawUser) {
      window.location.href = `/login?redirect=/app/ai${to.path}`
      return false
    }
    if (!isAdmin()) return { path: '/images' }
    return true
  }

  if (to.meta.requiresReporter) {
    if (!rawUser) {
      window.location.href = `/login?redirect=/app/ai${to.path}`
      return false
    }
    if (!isReporter()) return { path: '/images' }
    return true
  }

  return true
})

export default router
