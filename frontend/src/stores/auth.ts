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

  return { token, user, login, logout }
})
