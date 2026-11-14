import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

import type { ApiSuccess, AuthTokens } from '@/types/api'

const baseURL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

let accessToken: string | null = null
let refreshToken: string | null = null
let refreshPromise: Promise<string | null> | null = null
let onSessionExpired: () => void = () => undefined
let onTokensRotated: ((tokens: AuthTokens) => void) | undefined

export const http = axios.create({
  baseURL,
  timeout: 10_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

const refreshClient = axios.create({
  baseURL,
  timeout: 10_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

export function configureAuthTransport(
  sessionExpired: () => void,
  tokensRotated?: (tokens: AuthTokens) => void,
) {
  onSessionExpired = sessionExpired
  onTokensRotated = tokensRotated
}

export function setAuthTokens(tokens: AuthTokens) {
  accessToken = tokens.access_token
  refreshToken = tokens.refresh_token
}

export function clearAuthTokens() {
  accessToken = null
  refreshToken = null
}

export function getAccessToken() {
  return accessToken
}

export function getRefreshToken() {
  return refreshToken
}

function isAuthEndpoint(url?: string) {
  return Boolean(url?.includes('/auth/login') || url?.includes('/auth/refresh'))
}

async function rotateTokens() {
  if (!refreshToken) {
    return null
  }
  if (!refreshPromise) {
    refreshPromise = refreshClient
      .post<ApiSuccess<AuthTokens>>('/auth/refresh', { refresh_token: refreshToken })
      .then((response) => {
        setAuthTokens(response.data.data)
        onTokensRotated?.(response.data.data)
        return response.data.data.access_token
      })
      .catch(() => {
        clearAuthTokens()
        onSessionExpired()
        return null
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

http.interceptors.request.use((config) => {
  const requestId = crypto.randomUUID()
  config.headers.set('X-Request-ID', requestId)
  if (accessToken && !isAuthEndpoint(config.url)) {
    config.headers.set('Authorization', `Bearer ${accessToken}`)
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as
      (InternalAxiosRequestConfig & { _authRetry?: boolean }) | undefined
    if (
      error.response?.status !== 401 ||
      !config ||
      config._authRetry ||
      isAuthEndpoint(config.url)
    ) {
      return Promise.reject(error)
    }

    const nextAccessToken = await rotateTokens()
    if (!nextAccessToken) {
      return Promise.reject(error)
    }

    config._authRetry = true
    config.headers.set('Authorization', `Bearer ${nextAccessToken}`)
    return http(config)
  },
)
