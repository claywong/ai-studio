import { createRouter, createWebHistory } from 'vue-router'
import ImageStudio from '../pages/ImageStudio.vue'
import AdminReports from '../pages/AdminReports.vue'
import ChannelStatus from '../pages/ChannelStatus.vue'

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
  ],
})

router.beforeEach((to) => {
  if (!to.meta.requiresAdmin) return true

  const rawUser = localStorage.getItem('auth_user')
  if (!rawUser) {
    window.location.href = '/login?redirect=/app/ai/admin/reports'
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
