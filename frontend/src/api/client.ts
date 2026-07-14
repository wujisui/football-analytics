import axios, { type AxiosError } from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export const apiClient = axios.create({
  baseURL,
  // List endpoints are local-only and should be fast.
  timeout: 15000,
  // FastAPI list query expects league_ids=1&league_ids=2 (not league_ids[]=).
  paramsSerializer: { indexes: null },
})

export const analysisClient = axios.create({
  baseURL,
  // Detail analysis may enrich from official API within a server-side budget.
  timeout: 45000,
  paramsSerializer: { indexes: null },
})

function toError(error: AxiosError<{ detail?: string | { msg?: string }[] }>): Error {
  const status = error.response?.status
  const rawDetail = error.response?.data?.detail
  const detail =
    typeof rawDetail === 'string'
      ? rawDetail
      : Array.isArray(rawDetail)
        ? rawDetail.map((d) => d.msg || JSON.stringify(d)).join('; ')
        : undefined
  const isTimeout =
    error.code === 'ECONNABORTED' || /timeout/i.test(error.message || '')
  const message =
    detail ||
    (isTimeout
      ? '请求超时：首次分析可能较慢，请稍后重试'
      : status
        ? `请求失败（${status}）`
        : error.message || '网络错误，请确认后端服务是否已启动')

  return new Error(message)
}

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => Promise.reject(toError(error)),
)

analysisClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => Promise.reject(toError(error)),
)
