import { http } from '@/api/http'
import type { ApiSuccess, FollowUpMethod, FollowUpRecord, PageData } from '@/types/api'

export interface FollowUpPayload {
  contact_id: string | null
  method: FollowUpMethod
  content: string
  followed_at: string
  result: string | null
  next_follow_up_at: string | null
}

export interface FollowUpFilters {
  search?: string
  method?: FollowUpMethod
  from_at?: string
  to_at?: string
  page?: number
  page_size?: number
  sort_order?: 'asc' | 'desc'
}

export async function listFollowUps(customerId: string, params: FollowUpFilters = {}) {
  const response = await http.get<ApiSuccess<PageData<FollowUpRecord>>>(
    `/customers/${customerId}/follow-ups`,
    { params },
  )
  return response.data
}

export async function getFollowUp(customerId: string, recordId: string) {
  const response = await http.get<ApiSuccess<FollowUpRecord>>(
    `/customers/${customerId}/follow-ups/${recordId}`,
  )
  return response.data.data
}

export async function createFollowUp(customerId: string, payload: FollowUpPayload) {
  const response = await http.post<ApiSuccess<FollowUpRecord>>(
    `/customers/${customerId}/follow-ups`,
    payload,
  )
  return response.data.data
}

export async function updateFollowUp(
  customerId: string,
  recordId: string,
  payload: Partial<FollowUpPayload>,
) {
  const response = await http.patch<ApiSuccess<FollowUpRecord>>(
    `/customers/${customerId}/follow-ups/${recordId}`,
    payload,
  )
  return response.data.data
}
