import axios, { type AxiosError } from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export const apiClient = axios.create({
  baseURL,
  // List endpoints are local-only and should be fast.
  timeout: 15000,
  // FastAPI list query expects league_ids=1&league_ids=2 (not league_ids[]=).
  paramsSerializer: { indexes: null },
  // Session token is an httpOnly cookie; scripts never touch it.
  withCredentials: true,
  headers: {
    'Cache-Control': 'no-cache',
    Pragma: 'no-cache',
  },
})

/** Error carrying the HTTP status so callers can tell 401 from a network drop. */
export interface ApiError extends Error {
  status?: number
}

function toError(error: AxiosError<{ detail?: string | { msg?: string }[] }>): ApiError {
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

  const apiError: ApiError = new Error(message)
  apiError.status = status
  return apiError
}

type AuthExpiredHandler = () => void
let onAuthExpired: AuthExpiredHandler | null = null

export function setOnAuthExpired(handler: AuthExpiredHandler | null) {
  onAuthExpired = handler
}

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    const url = String(error.config?.url || '')
    // /auth/* 401 is a credential answer, not an expired session.
    const isAuthEndpoint = url.includes('/auth/')
    if (error.response?.status === 401 && !isAuthEndpoint) {
      onAuthExpired?.()
    }
    return Promise.reject(toError(error))
  },
)
