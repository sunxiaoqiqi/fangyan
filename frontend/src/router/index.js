import { createRouter, createWebHistory } from 'vue-router'
import CollectPage from '../views/CollectPage.vue'
import TranscribePage from '../views/TranscribePage.vue'
import FineTunePage from '../views/FineTunePage.vue'
import FineTuneHistoryPage from '../views/FineTuneHistoryPage.vue'
import TestPage from '../views/TestPage.vue'
import LoginPage from '../views/LoginPage.vue'
import UserManagementPage from '../views/UserManagementPage.vue'
import EvaluatePage from '../views/EvaluatePage.vue'

// 路由守卫
const requireAuth = (to, from, next) => {
  const token = localStorage.getItem('token')
  if (token) {
    next()
  } else {
    next('/login')
  }
}

// 管理员路由守卫
const requireAdmin = (to, from, next) => {
  const user = JSON.parse(localStorage.getItem('user'))
  if (user && user.is_admin) {
    next()
  } else {
    next('/')
  }
}

const routes = [
  {
    path: '/login',
    name: 'login',
    component: LoginPage
  },
  {
    path: '/',
    name: 'collect',
    component: CollectPage,
    beforeEnter: requireAuth
  },
  {
    path: '/transcribe',
    name: 'transcribe',
    component: TranscribePage,
    beforeEnter: requireAuth
  },
  {
    path: '/fine-tune',
    name: 'fine-tune',
    component: FineTunePage,
    beforeEnter: requireAuth
  },
  {
    path: '/fine-tune-history',
    name: 'fine-tune-history',
    component: FineTuneHistoryPage,
    beforeEnter: requireAuth
  },
  {
    path: '/test',
    name: 'test',
    component: TestPage,
    beforeEnter: requireAuth
  },
  {
    path: '/evaluate',
    name: 'evaluate',
    component: EvaluatePage,
    beforeEnter: requireAuth
  },
  {
    path: '/user-management',
    name: 'user-management',
    component: UserManagementPage,
    beforeEnter: requireAdmin
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router

