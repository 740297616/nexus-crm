import { afterEach, describe, expect, it } from 'vitest'

import { clearAuthTokens, getAccessToken, getRefreshToken, setAuthTokens } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { createAppStore } from '@/stores/app'

describe('authentication transport', () => {
  afterEach(() => {
    clearAuthTokens()
  })

  it('keeps tokens in memory and clears them on logout', () => {
    setAuthTokens({
      access_token: 'access-token',
      refresh_token: 'refresh-token',
      token_type: 'bearer',
      expires_in: 900,
    })

    expect(getAccessToken()).toBe('access-token')
    expect(getRefreshToken()).toBe('refresh-token')

    clearAuthTokens()
    expect(getAccessToken()).toBeNull()
    expect(getRefreshToken()).toBeNull()
  })

  it('exposes current permissions for route, menu and action guards', () => {
    const auth = useAuthStore(createAppStore())
    auth.user = {
      id: 'user-id',
      username: 'employee',
      email: null,
      display_name: 'Employee',
      department_id: null,
      status: 'active',
      last_login_at: null,
      role_codes: ['employee'],
      permission_codes: ['dashboard:menu', 'dashboard:page'],
      data_scope: 'self',
    }

    expect(auth.hasPermission('dashboard:menu')).toBe(true)
    expect(auth.hasPermission('users:menu')).toBe(false)
  })
})
