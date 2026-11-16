import { afterEach, describe, expect, it, vi } from 'vitest'

const http = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}))

vi.mock('@/api/http', () => ({ http }))

import { createFollowUp, listFollowUps, updateFollowUp } from '@/api/followups'
import {
  cancelReminder,
  completeReminder,
  createReminder,
  listDueReminders,
  listMyReminders,
  listOverdueReminders,
  updateReminder,
} from '@/api/reminders'

const success = (data: unknown) => ({
  data: { success: true, data, meta: null, request_id: 'request-followups' },
})

afterEach(() => vi.resetAllMocks())

describe('follow-up and reminder API clients', () => {
  it('maps nested follow-up timeline CRUD endpoints', async () => {
    const record = { id: 'follow-up-id', content: '已沟通' }
    http.get.mockResolvedValue(success({ items: [record], total: 1 }))
    http.post.mockResolvedValue(success(record))
    http.patch.mockResolvedValue(success(record))
    const payload = {
      contact_id: null,
      method: 'phone' as const,
      content: '已沟通',
      followed_at: '2026-11-16T02:00:00.000Z',
      result: null,
      next_follow_up_at: null,
    }

    await expect(listFollowUps('customer-id', { page: 1, page_size: 20 })).resolves.toMatchObject({
      data: { items: [record], total: 1 },
    })
    await expect(createFollowUp('customer-id', payload)).resolves.toEqual(record)
    await expect(
      updateFollowUp('customer-id', 'follow-up-id', { result: '待回访' }),
    ).resolves.toEqual(record)

    expect(http.get).toHaveBeenCalledWith('/customers/customer-id/follow-ups', {
      params: { page: 1, page_size: 20 },
    })
    expect(http.post).toHaveBeenCalledWith('/customers/customer-id/follow-ups', payload)
    expect(http.patch).toHaveBeenCalledWith('/customers/customer-id/follow-ups/follow-up-id', {
      result: '待回访',
    })
  })

  it('maps reminder personal, due, overdue, and state-transition endpoints', async () => {
    const reminder = { id: 'reminder-id', status: 'pending' }
    http.get.mockResolvedValue(success({ items: [reminder], total: 1 }))
    http.post.mockResolvedValue(success(reminder))
    http.patch.mockResolvedValue(success(reminder))
    const payload = {
      title: '回访客户',
      content: null,
      remind_at: '2026-11-16T02:00:00.000Z',
      customer_id: null,
      follow_up_record_id: null,
    }

    await listMyReminders({ page: 1, page_size: 20 })
    await listDueReminders({ page: 1, page_size: 20 })
    await listOverdueReminders({ page: 1, page_size: 20 })
    await createReminder(payload)
    await updateReminder('reminder-id', { title: '再次回访' })
    await completeReminder('reminder-id')
    await cancelReminder('reminder-id')

    expect(http.get).toHaveBeenNthCalledWith(1, '/reminders/mine', {
      params: { page: 1, page_size: 20 },
    })
    expect(http.get).toHaveBeenNthCalledWith(2, '/reminders/due', {
      params: { page: 1, page_size: 20 },
    })
    expect(http.get).toHaveBeenNthCalledWith(3, '/reminders/overdue', {
      params: { page: 1, page_size: 20 },
    })
    expect(http.post).toHaveBeenCalledWith('/reminders', payload)
    expect(http.patch).toHaveBeenCalledWith('/reminders/reminder-id', { title: '再次回访' })
    expect(http.post).toHaveBeenCalledWith('/reminders/reminder-id/complete')
    expect(http.post).toHaveBeenCalledWith('/reminders/reminder-id/cancel')
  })
})
