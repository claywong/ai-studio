<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, RouterLink } from 'vue-router'

const isAdmin = computed(() => {
  try {
    const user = JSON.parse(localStorage.getItem('auth_user') ?? '{}') as { role?: string }
    return user.role === 'admin'
  } catch {
    return false
  }
})
</script>

<template>
  <div>
    <nav class="top-nav">
      <RouterLink to="/images">图片工作台</RouterLink>
      <template v-if="isAdmin">
        <RouterLink to="/admin/reports">管理报表</RouterLink>
        <RouterLink to="/admin/channel-status">渠道状态</RouterLink>
        <RouterLink to="/admin/user-trend">用户趋势</RouterLink>
      </template>
    </nav>
    <RouterView />
  </div>
</template>

<style scoped>
.top-nav {
  display: flex;
  gap: 4px;
  padding: 8px 40px;
  background: #0d0d14;
  border-bottom: 1px solid #1a1a28;
}

.top-nav a {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 6px;
  color: #64748b;
  text-decoration: none;
  transition: all 0.15s;
}

.top-nav a:hover,
.top-nav a.router-link-active {
  background: #1e293b;
  color: #e2e8f0;
}
</style>
