import { defineStore } from 'pinia'
import { ref } from 'vue'

import { http } from '@/api/http'

export interface UserInfo {
  id: number
  username: string
  display_name: string
  role: string
  status: string
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem('token') ?? '')
  const user = ref<UserInfo | null>(JSON.parse(localStorage.getItem('user') ?? 'null'))

  function setAuth(newToken: string, newUser: UserInfo) {
    token.value = newToken
    user.value = newUser
    localStorage.setItem('token', newToken)
    localStorage.setItem('user', JSON.stringify(newUser))
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  async function login(username: string, password: string) {
    const data = await http.post('/auth/login', { username, password })
    setAuth(data.access_token, data.user)
  }

  /**
   * 用后端最新信息刷新本地登录态。
   * 角色被管理员调整后，页面加载时以服务端为准，避免菜单/按钮继续使用旧角色缓存。
   */
  async function refreshMe() {
    if (!token.value) return
    try {
      const me = await http.get<UserInfo>('/auth/me')
      user.value = me
      localStorage.setItem('user', JSON.stringify(me))
    } catch {
      // 401 由 http 拦截器统一清理登录态；网络异常不阻塞页面
    }
  }

  return { token, user, login, logout, refreshMe }
})
