import { describe, expect, it } from 'vitest'

import { createAppStore, useAppStore } from '@/stores/app'

describe('frontend foundation', () => {
  it('creates the default application store', () => {
    const store = useAppStore(createAppStore())

    expect(store.sidebarCollapsed).toBe(false)
    store.toggleSidebar()
    expect(store.sidebarCollapsed).toBe(true)
  })
})
