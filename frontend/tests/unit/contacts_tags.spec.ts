import { afterEach, describe, expect, it, vi } from 'vitest'

const http = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/api/http', () => ({ http }))

import {
  createContact,
  deleteContact,
  listContacts,
  setPrimaryContact,
  updateContact,
} from '@/api/contacts'
import {
  bindCustomerTag,
  createTag,
  deleteTag,
  listCustomerTags,
  listTags,
  unbindCustomerTag,
  updateTag,
} from '@/api/tags'

const success = (data: unknown) => ({
  data: { success: true, data, meta: null, request_id: 'request-2' },
})

afterEach(() => vi.resetAllMocks())

describe('contact and tag API clients', () => {
  it('maps nested contact CRUD and primary-contact endpoints', async () => {
    const contact = { id: 'contact-id', name: 'Alice' }
    http.get.mockResolvedValue(success({ items: [contact], total: 1 }))
    http.post.mockResolvedValue(success(contact))
    http.patch.mockResolvedValue(success(contact))
    http.delete.mockResolvedValue(undefined)

    await expect(listContacts('customer-id', { search: 'Alice' })).resolves.toMatchObject({
      data: { items: [contact], total: 1 },
    })
    await createContact('customer-id', {
      name: 'Alice',
      title: null,
      phone: null,
      email: null,
      contact_method: null,
      is_primary: true,
      remark: null,
    })
    await updateContact('customer-id', 'contact-id', { title: 'Director' })
    await setPrimaryContact('customer-id', 'contact-id')
    await deleteContact('customer-id', 'contact-id')

    expect(http.get).toHaveBeenCalledWith('/customers/customer-id/contacts', {
      params: { search: 'Alice' },
    })
    expect(http.post).toHaveBeenNthCalledWith(
      1,
      '/customers/customer-id/contacts',
      expect.objectContaining({ name: 'Alice', is_primary: true }),
    )
    expect(http.patch).toHaveBeenCalledWith('/customers/customer-id/contacts/contact-id', {
      title: 'Director',
    })
    expect(http.post).toHaveBeenNthCalledWith(
      2,
      '/customers/customer-id/contacts/contact-id/primary',
    )
    expect(http.delete).toHaveBeenCalledWith('/customers/customer-id/contacts/contact-id')
  })

  it('maps tag dictionary and customer binding endpoints', async () => {
    const tag = { id: 'tag-id', name: 'Priority' }
    const relation = { id: 'relation-id', tag_id: 'tag-id' }
    http.get.mockResolvedValueOnce(success([tag])).mockResolvedValueOnce(success([relation]))
    http.post.mockResolvedValueOnce(success(tag)).mockResolvedValueOnce(success(relation))
    http.patch.mockResolvedValue(success(tag))
    http.delete.mockResolvedValue(undefined)

    await expect(listTags()).resolves.toEqual([tag])
    await expect(listCustomerTags('customer-id')).resolves.toEqual([relation])
    await createTag({ name: 'Priority', description: null })
    await updateTag('tag-id', { name: 'High Priority' })
    await bindCustomerTag('customer-id', 'tag-id')
    await unbindCustomerTag('customer-id', 'tag-id')
    await deleteTag('tag-id')

    expect(http.get).toHaveBeenNthCalledWith(1, '/tags')
    expect(http.get).toHaveBeenNthCalledWith(2, '/customers/customer-id/tags')
    expect(http.post).toHaveBeenNthCalledWith(2, '/customers/customer-id/tags', {
      tag_id: 'tag-id',
    })
    expect(http.delete).toHaveBeenNthCalledWith(1, '/customers/customer-id/tags/tag-id')
    expect(http.delete).toHaveBeenNthCalledWith(2, '/tags/tag-id')
  })
})
