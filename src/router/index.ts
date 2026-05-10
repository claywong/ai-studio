import { createRouter, createWebHistory } from 'vue-router'
import ImageStudio from '../pages/ImageStudio.vue'
import AdminReports from '../pages/AdminReports.vue'
import ChannelStatus from '../pages/ChannelStatus.vue'
import UserTrend from '../pages/UserTrend.vue'
import AccountLatency from '../pages/AccountLatency.vue'
import AccountMonitorChart from '../pages/AccountMonitorChart.vue'
import AccountUsageTimeline from '../pages/AccountUsageTimeline.vue'
import AccountHealthStatus from '../pages/AccountHealthStatus.vue'
import UsageLogs from '../pages/UsageLogs.vue'

const router = createRouter({
  history: createWebHistory('/app/ai/'),
  routes: [
    { path: '/', redirect: '/images' },
    { path: '/images', component: ImageStudio },
    {
      path: '/admin/reports',
      component: AdminReports,
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
  if (!to.meta.requiresAdmin) return true

  const rawUser = localStorage.getItem('auth_user')
  if (!rawUser) {
    window.location.href = `/login?redirect=/app/ai${to.path}`
    return false
  }

  try {
    const user = JSON.parse(rawUser) as { role?: string }
    if (user.role !== 'admin') {
      return { path: '/images' }
    }
  } catch {
    return { path: '/images' }
  }

  return true
})

export default router
