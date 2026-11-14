import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { configureAuthTransport, clearAuthTokens, http, setAuthTokens } from '@/api/http'
import type { ApiSuccess, AuthTokens, CurrentUser } from '@/types/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<CurrentUser | null>(null)
  const accessToken = ref<string | null>(null)
  const refreshToken = ref<string | null>(null)
  const isLoading = ref(false)
  const isAuthenticated = computed(() => Boolean(accessToken.value && user.value))

  function hasPermission(permissionCode: string) {
    return user.value?.permission_codes.includes(permissionCode) ?? false
  }

  function applyTokens(tokens: AuthTokens) {
    accessToken.value = tokens.access_token
    refreshToken.value = tokens.refresh_token
    setAuthTokens(tokens)
  }

  function clearSession() {
    user.value = null
    accessToken.value = null
    refreshToken.value = null
    clearAuthTokens()
  }

  async function login(identifier: string, password: string) {
    isLoading.value = true
    try {
      const response = await http.post<ApiSuccess<AuthTokens>>('/auth/login', {
        identifier,
        password,
      })
      applyTokens(response.data.data)
      await fetchCurrentUser()
    } finally {
      isLoading.value = false
    }
  }

  async function fetchCurrentUser() {
    const response = await http.get<ApiSuccess<CurrentUser>>('/auth/me')
    user.value = response.data.data
    return user.value
  }

  async function refreshSession() {
    if (!refreshToken.value) {
      clearSession()
      return false
    }
    try {
      const response = await http.post<ApiSuccess<AuthTokens>>('/auth/refresh', {
        refresh_token: refreshToken.value,
      })
      applyTokens(response.data.data)
      await fetchCurrentUser()
      return true
    } catch {
      clearSession()
      return false
    }
  }

  async function logout() {
    try {
      if (refreshToken.value) {
        await http.post('/auth/logout', { refresh_token: refreshToken.value })
      }
    } finally {
      clearSession()
    }
  }

  async function changePassword(currentPassword: string, newPassword: string) {
    await http.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
    clearSession()
  }

  return {
    user,
    accessToken,
    refreshToken,
    isLoading,
    isAuthenticated,
    hasPermission,
    login,
    fetchCurrentUser,
    refreshSession,
    logout,
    changePassword,
    clearSession,
  }
})

export function initializeAuthTransport(
  store: ReturnType<typeof useAuthStore>,
  onExpired?: () => void,
) {
  configureAuthTransport(
    () => {
      store.clearSession()
      onExpired?.()
    },
    (tokens) => {
      store.accessToken = tokens.access_token
      store.refreshToken = tokens.refresh_token
    },
  )
}
