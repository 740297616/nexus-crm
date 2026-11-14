import { afterEach, describe, expect, it } from 'vitest'

import { clearAuthTokens, getAccessToken, getRefreshToken, setAuthTokens } from '@/api/http'

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
})
