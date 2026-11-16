import { http } from '@/api/http'
import type { ApiSuccess, ContactRecord, PageData } from '@/types/api'

export interface ContactPayload {
  name: string
  title: string | null
  phone: string | null
  email: string | null
  contact_method: string | null
  is_primary: boolean
  remark: string | null
}

export interface ContactFilters {
  search?: string
  page?: number
  page_size?: number
  sort_order?: 'asc' | 'desc'
}

export async function listContacts(customerId: string, params: ContactFilters = {}) {
  const response = await http.get<ApiSuccess<PageData<ContactRecord>>>(
    `/customers/${customerId}/contacts`,
    { params },
  )
  return response.data
}

export async function getContact(customerId: string, contactId: string) {
  const response = await http.get<ApiSuccess<ContactRecord>>(
    `/customers/${customerId}/contacts/${contactId}`,
  )
  return response.data.data
}

export async function createContact(customerId: string, payload: ContactPayload) {
  const response = await http.post<ApiSuccess<ContactRecord>>(
    `/customers/${customerId}/contacts`,
    payload,
  )
  return response.data.data
}

export async function updateContact(
  customerId: string,
  contactId: string,
  payload: Partial<Omit<ContactPayload, 'is_primary'>>,
) {
  const response = await http.patch<ApiSuccess<ContactRecord>>(
    `/customers/${customerId}/contacts/${contactId}`,
    payload,
  )
  return response.data.data
}

export async function deleteContact(customerId: string, contactId: string) {
  await http.delete(`/customers/${customerId}/contacts/${contactId}`)
}

export async function setPrimaryContact(customerId: string, contactId: string) {
  const response = await http.post<ApiSuccess<ContactRecord>>(
    `/customers/${customerId}/contacts/${contactId}/primary`,
  )
  return response.data.data
}
