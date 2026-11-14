export interface ApiSuccess<T> {
  success: true
  data: T
  meta: Record<string, unknown> | null
  request_id: string
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  expires_in: number
}

export interface CurrentUser {
  id: string
  username: string
  email: string | null
  display_name: string
  department_id: string | null
  status: 'active' | 'disabled'
  last_login_at: string | null
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
