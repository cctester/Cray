import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('../views/Dashboard.vue'),
    },
    {
      path: '/workflows',
      name: 'workflows',
      component: () => import('../views/Workflows.vue'),
    },
    {
      path: '/workflows/:id',
      name: 'workflow-detail',
      component: () => import('../views/WorkflowDetail.vue'),
    },
    {
      path: '/runs',
      name: 'runs',
      component: () => import('../views/Runs.vue'),
    },
    {
      path: '/runs/:id',
      name: 'run-detail',
      component: () => import('../views/RunDetail.vue'),
    },
    {
      path: '/plugins',
      name: 'plugins',
      component: () => import('../views/Plugins.vue'),
    },
    {
      path: '/editor',
      name: 'editor',
      component: () => import('../views/Editor.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/Settings.vue'),
    },
    {
      path: '/metrics',
      name: 'metrics',
      component: () => import('../views/Metrics.vue'),
    },
  ],
})

export default router
