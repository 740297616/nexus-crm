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
  role_codes: string[]
  permission_codes: string[]
  data_scope: DataScope
}

export interface UserRecord extends Omit<CurrentUser, 'permission_codes'> {
  department_name: string | null
  created_at: string
  updated_at: string
}

export interface DepartmentRecord {
  id: string
  name: string
  parent_id: string | null
  is_active: boolean
  user_count: number
  created_at: string
  updated_at: string
  children: DepartmentRecord[]
}

export type DataScope = 'self' | 'department' | 'subtree' | 'all'

export interface RoleRecord {
  id: string
  name: string
  code: string
  description: string | null
  data_scope: DataScope
  is_system: boolean
  permission_codes: string[]
  created_at: string
  updated_at: string
}

export interface PermissionRecord {
  id: string
  code: string
  name: string
  resource: string
  action: string
  permission_type: 'menu' | 'page' | 'api'
  description: string | null
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
