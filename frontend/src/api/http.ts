import axios, { type AxiosInstance } from 'axios'

import router from '@/router'

// 响应拦截器已解包 resp.data，这里重写实例类型使调用方直接拿到业务数据
interface HttpClient extends Omit<AxiosInstance, 'get' | 'post' | 'put' | 'delete' | 'patch'> {
  get<T = any>(url: string, config?: object): Promise<T>
  post<T = any>(url: string, data?: unknown, config?: object): Promise<T>
  put<T = any>(url: string, data?: unknown, config?: object): Promise<T>
  patch<T = any>(url: string, data?: unknown, config?: object): Promise<T>
  delete<T = any>(url: string, config?: object): Promise<T>
}

export const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
}) as HttpClient

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (resp) => resp.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      router.push({ name: 'login' })
    }
    return Promise.reject(error)
  },
)
