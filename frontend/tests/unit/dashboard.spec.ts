import { afterEach, describe, expect, it, vi } from 'vitest'

const http = vi.hoisted(() => ({
  get: vi.fn(),
}))

vi.mock('@/api/http', () => ({ http }))

import { getDashboardSummary } from '@/api/dashboard'

const success = (data: unknown) => ({
  data: { success: true, data, meta: null, request_id: 'request-dashboard' },
})

afterEach(() => vi.resetAllMocks())

describe('dashboard API client', () => {
  it('passes an optional UTC date range and unwraps the scoped summary', async () => {
    const summary = {
      personal: { my_customer_total: 2 },
      management: { customer_total: 3 },
      range: { start_date: '2026-11-01', end_date: '2026-11-16' },
    }
    http.get.mockResolvedValue(success(summary))

    await expect(
      getDashboardSummary({ start_date: '2026-11-01', end_date: '2026-11-16' }),
    ).resolves.toEqual(summary)

    expect(http.get).toHaveBeenCalledWith('/dashboard/summary', {
      params: { start_date: '2026-11-01', end_date: '2026-11-16' },
    })
  })
})
