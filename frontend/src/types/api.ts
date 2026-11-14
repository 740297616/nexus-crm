export interface ApiSuccess<T> {
  success: true
  data: T
  meta: Record<string, unknown> | null
  request_id: string
}

export interface ApiErrorBody {
  success: false
  error: {
    code: string
    message: string
    details: unknown
  }
  request_id: string
}

export interface PageMeta {
  page: number
  page_size: number
  total_pages: number
}

export interface PageData<T> {
  items: T[]
  total: number
}
