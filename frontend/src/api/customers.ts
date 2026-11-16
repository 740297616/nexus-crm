import { http } from '@/api/http'
import type {
  ApiSuccess,
  CustomerAssignee,
  CustomerDetail,
  CustomerLevel,
  CustomerNameMatch,
  CustomerRecord,
  CustomerStatus,
  PageData,
} from '@/types/api'

export interface CustomerFilters {
  search?: string
  source?: string
  industry?: string
  level?: CustomerLevel
  status?: CustomerStatus
  tag_id?: string
  page?: number
  page_size?: number
  sort_by?: 'created_at' | 'updated_at' | 'customer_no' | 'name' | 'level' | 'status'
  sort_order?: 'asc' | 'desc'
}

export interface CustomerPayload {
  customer_no: string
  name: string
  owner_id?: string
  source: string | null
  industry: string | null
  level: CustomerLevel
  status: CustomerStatus
  phone: string | null
  email: string | null
  address: string | null
  description: string | null
}

export type CustomerUpdatePayload = Partial<Omit<CustomerPayload, 'customer_no' | 'owner_id'>>

export async function listCustomers(params: CustomerFilters) {
  const response = await http.get<ApiSuccess<PageData<CustomerRecord>>>('/customers', { params })
  return response.data
}

export async function getCustomer(customerId: string) {
  const response = await http.get<ApiSuccess<CustomerDetail>>(`/customers/${customerId}`)
  return response.data.data
}

export async function createCustomer(payload: CustomerPayload) {
  const response = await http.post<ApiSuccess<CustomerRecord>>('/customers', payload)
  return response.data.data
}

export async function updateCustomer(customerId: string, payload: CustomerUpdatePayload) {
  const response = await http.patch<ApiSuccess<CustomerRecord>>(`/customers/${customerId}`, payload)
  return response.data.data
}

export async function deleteCustomer(customerId: string) {
  await http.delete(`/customers/${customerId}`)
}

export async function checkCustomerName(name: string, excludeId?: string) {
  const response = await http.get<
    ApiSuccess<{ has_duplicates: boolean; matches: CustomerNameMatch[] }>
  >('/customers/name-check', { params: { name, exclude_id: excludeId } })
  return response.data.data
}

export async function listCustomerAssignees() {
  const response = await http.get<ApiSuccess<CustomerAssignee[]>>('/customers/assignees')
  return response.data.data
}

export async function assignCustomer(
  customerId: string,
  payload: { owner_id: string; reason: string | null },
) {
  const response = await http.post<ApiSuccess<CustomerDetail>>(
    `/customers/${customerId}/assign`,
    payload,
  )
  return response.data.data
}

export async function transferCustomer(
  customerId: string,
  payload: { owner_id: string; reason: string },
) {
  const response = await http.post<ApiSuccess<CustomerDetail>>(
    `/customers/${customerId}/transfer`,
    payload,
  )
  return response.data.data
}
