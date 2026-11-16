import { afterEach, describe, expect, it, vi } from 'vitest'

const http = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/api/http', () => ({ http }))

import {
  assignCustomer,
  checkCustomerName,
  createCustomer,
  deleteCustomer,
  downloadCustomerImportTemplate,
  exportCustomers,
  getCustomer,
  importCustomers,
  listCustomers,
  transferCustomer,
  updateCustomer,
} from '@/api/customers'

const success = (data: unknown) => ({
  data: { success: true, data, meta: null, request_id: 'request-1' },
})

afterEach(() => vi.resetAllMocks())

describe('customer API client', () => {
  it('passes search, filters, and pagination to the scoped customer list endpoint', async () => {
    const page = { items: [], total: 0 }
    http.get.mockResolvedValue(success(page))
    const filters = {
      search: 'Acme',
      source: 'referral',
      tag_id: 'tag-id',
      page: 2,
      page_size: 20,
    } as const

    await expect(listCustomers(filters)).resolves.toEqual({
      success: true,
      data: page,
      meta: null,
      request_id: 'request-1',
    })
    expect(http.get).toHaveBeenCalledWith('/customers', { params: filters })
  })

  it('maps detail, create, update, and soft-delete operations to resource endpoints', async () => {
    const record = { id: 'customer-id', name: 'Acme' }
    http.get.mockResolvedValue(success(record))
    http.post.mockResolvedValue(success(record))
    http.patch.mockResolvedValue(success(record))
    http.delete.mockResolvedValue(undefined)

    await expect(getCustomer('customer-id')).resolves.toEqual(record)
    await createCustomer({
      customer_no: 'ACME-1',
      name: 'Acme',
      source: null,
      industry: null,
      level: 'C',
      status: 'active',
      phone: null,
      email: null,
      address: null,
      description: null,
    })
    await updateCustomer('customer-id', { name: 'Acme Updated' })
    await deleteCustomer('customer-id')

    expect(http.get).toHaveBeenCalledWith('/customers/customer-id')
    expect(http.post).toHaveBeenCalledWith(
      '/customers',
      expect.objectContaining({
        customer_no: 'ACME-1',
      }),
    )
    expect(http.patch).toHaveBeenCalledWith('/customers/customer-id', { name: 'Acme Updated' })
    expect(http.delete).toHaveBeenCalledWith('/customers/customer-id')
  })

  it('checks duplicates and sends explicit assignment or transfer requests', async () => {
    const result = { has_duplicates: true, matches: [] }
    http.get.mockResolvedValue(success(result))
    http.post.mockResolvedValue(success({ id: 'customer-id' }))

    await expect(checkCustomerName('Acme Ltd', 'customer-id')).resolves.toEqual(result)
    await assignCustomer('customer-id', { owner_id: 'user-a', reason: null })
    await transferCustomer('customer-id', { owner_id: 'user-b', reason: 'Territory change' })

    expect(http.get).toHaveBeenCalledWith('/customers/name-check', {
      params: { name: 'Acme Ltd', exclude_id: 'customer-id' },
    })
    expect(http.post).toHaveBeenNthCalledWith(1, '/customers/customer-id/assign', {
      owner_id: 'user-a',
      reason: null,
    })
    expect(http.post).toHaveBeenNthCalledWith(2, '/customers/customer-id/transfer', {
      owner_id: 'user-b',
      reason: 'Territory change',
    })
  })

  it('maps Excel template, import, and scoped export endpoints', async () => {
    const blob = new Blob(['xlsx'])
    const result = { imported_rows: 1, total_rows: 1 }
    http.get.mockResolvedValueOnce({ data: blob }).mockResolvedValueOnce({ data: blob })
    http.post.mockResolvedValue({ data: { success: true, data: result } })
    const file = new File(['xlsx'], 'customers.xlsx')

    await expect(downloadCustomerImportTemplate()).resolves.toBe(blob)
    await expect(importCustomers(file)).resolves.toEqual(result)
    await expect(exportCustomers({ tag_id: 'tag-id', search: 'Acme' })).resolves.toBe(blob)

    expect(http.get).toHaveBeenNthCalledWith(1, '/customers/import/template', {
      responseType: 'blob',
    })
    expect(http.post).toHaveBeenCalledWith('/customers/import', expect.any(FormData))
    expect(http.get).toHaveBeenNthCalledWith(2, '/customers/export', {
      params: { tag_id: 'tag-id', search: 'Acme' },
      responseType: 'blob',
    })
  })
})
