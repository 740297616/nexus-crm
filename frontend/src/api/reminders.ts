import { http } from '@/api/http'
import type { ApiSuccess, PageData, ReminderRecord } from '@/types/api'

export interface ReminderPayload {
  title: string
  content: string | null
  remind_at: string
  customer_id: string | null
  follow_up_record_id: string | null
}

export interface ReminderFilters {
  status?: 'pending' | 'completed' | 'cancelled'
  customer_id?: string
  page?: number
  page_size?: number
  sort_order?: 'asc' | 'desc'
}

export async function listReminders(params: ReminderFilters = {}) {
  const response = await http.get<ApiSuccess<PageData<ReminderRecord>>>('/reminders', { params })
  return response.data
}

export async function listMyReminders(params: Omit<ReminderFilters, 'customer_id'> = {}) {
  const response = await http.get<ApiSuccess<PageData<ReminderRecord>>>('/reminders/mine', {
    params,
  })
  return response.data
}

export async function listDueReminders(params: Pick<ReminderFilters, 'page' | 'page_size'> = {}) {
  const response = await http.get<ApiSuccess<PageData<ReminderRecord>>>('/reminders/due', {
    params,
  })
  return response.data
}

export async function listOverdueReminders(
  params: Pick<ReminderFilters, 'page' | 'page_size'> = {},
) {
  const response = await http.get<ApiSuccess<PageData<ReminderRecord>>>('/reminders/overdue', {
    params,
  })
  return response.data
}

export async function createReminder(payload: ReminderPayload) {
  const response = await http.post<ApiSuccess<ReminderRecord>>('/reminders', payload)
  return response.data.data
}

export async function updateReminder(reminderId: string, payload: Partial<ReminderPayload>) {
  const response = await http.patch<ApiSuccess<ReminderRecord>>(`/reminders/${reminderId}`, payload)
  return response.data.data
}

export async function completeReminder(reminderId: string) {
  const response = await http.post<ApiSuccess<ReminderRecord>>(`/reminders/${reminderId}/complete`)
  return response.data.data
}

export async function cancelReminder(reminderId: string) {
  const response = await http.post<ApiSuccess<ReminderRecord>>(`/reminders/${reminderId}/cancel`)
  return response.data.data
}
