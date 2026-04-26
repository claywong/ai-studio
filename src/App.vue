<script setup lang="ts">
import { computed } from 'vue'
import { RouterView } from 'vue-router'

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
    <nav v-if="isAdmin" class="admin-nav">
      <a href="/app/ai/images">图片工作台</a>
      <a href="/app/ai/admin/reports">管理报表</a>
    </nav>
    <RouterView />
  </div>
</template>

<style scoped>
.admin-nav {
  display: flex;
  gap: 4px;
  padding: 8px 40px;
  background: #0d0d14;
  border-bottom: 1px solid #1a1a28;
}

.admin-nav a {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 6px;
  color: #64748b;
  text-decoration: none;
  transition: all 0.15s;
}

.admin-nav a:hover,
.admin-nav a.router-link-active {
  background: #1e293b;
  color: #e2e8f0;
}
</style>
