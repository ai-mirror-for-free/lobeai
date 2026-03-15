import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue'
import Models from '@/views/Models.vue'
import Pricing from '@/views/Pricing.vue'
import Login from '@/views/Login.vue'
import Register from '@/views/Register.vue'
import UserProfile from '@/views/UserProfile.vue'

const routes = [
  { path: '/', name: 'Home', component: Home },
  { path: '/models', name: 'Models', component: Models },
  { path: '/pricing', name: 'Pricing', component: Pricing },
  { path: '/login', name: 'Login', component: Login },
  { path: '/register', name: 'Register', component: Register },
  { path: '/profile', name: 'UserProfile', component: UserProfile },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.hash) return { el: to.hash, behavior: 'smooth' }
    return { top: 0, behavior: 'smooth' }
  }
})

export default router