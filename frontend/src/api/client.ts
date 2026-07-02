import axios, { type AxiosError } from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export const apiClient = axios.create({
  baseURL,
  timeout: 30000,
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail
    const message =
      detail ||
      error.message ||
      (status ? `请求失败（${status}）` : '网络错误，请确认后端服务是否已启动')

    return Promise.reject(new Error(message))
  },
)
