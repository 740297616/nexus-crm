import { http } from '@/api/http'
import type { ApiSuccess, CustomerTagRecord, TagRecord } from '@/types/api'

export interface TagPayload {
  name: string
  description: string | null
}

export async function listTags() {
  const response = await http.get<ApiSuccess<TagRecord[]>>('/tags')
  return response.data.data
}

export async function createTag(payload: TagPayload) {
  const response = await http.post<ApiSuccess<TagRecord>>('/tags', payload)
  return response.data.data
}

export async function updateTag(tagId: string, payload: Partial<TagPayload>) {
  const response = await http.patch<ApiSuccess<TagRecord>>(`/tags/${tagId}`, payload)
  return response.data.data
}

export async function deleteTag(tagId: string) {
  await http.delete(`/tags/${tagId}`)
}

export async function listCustomerTags(customerId: string) {
  const response = await http.get<ApiSuccess<CustomerTagRecord[]>>(`/customers/${customerId}/tags`)
  return response.data.data
}

export async function bindCustomerTag(customerId: string, tagId: string) {
  const response = await http.post<ApiSuccess<CustomerTagRecord>>(`/customers/${customerId}/tags`, {
    tag_id: tagId,
  })
  return response.data.data
}

export async function unbindCustomerTag(customerId: string, tagId: string) {
  await http.delete(`/customers/${customerId}/tags/${tagId}`)
}
