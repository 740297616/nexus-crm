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

export type CustomerLevel = 'A' | 'B' | 'C' | 'D'
export type CustomerStatus = 'active' | 'inactive'

export interface CustomerRecord {
  id: string
  customer_no: string
  name: string
  owner_id: string
  owner_name: string
  department_id: string
  department_name: string
  source: string | null
  industry: string | null
  level: CustomerLevel
  status: CustomerStatus
  phone: string | null
  email: string | null
  address: string | null
  description: string | null
  created_by: string
  created_by_name: string
  created_at: string
  updated_at: string
}

export interface CustomerOwnershipHistoryRecord {
  id: string
  action: 'assigned' | 'transferred'
  previous_owner_id: string | null
  previous_owner_name: string | null
  previous_department_id: string | null
  new_owner_id: string
  new_owner_name: string
  new_department_id: string
  new_department_name: string
  transferred_by: string
  transferred_by_name: string
  reason: string | null
  created_at: string
}

export interface CustomerDetail extends CustomerRecord {
  ownership_history: CustomerOwnershipHistoryRecord[]
}

export interface ContactRecord {
  id: string
  customer_id: string
  name: string
  title: string | null
  phone: string | null
  email: string | null
  contact_method: string | null
  is_primary: boolean
  remark: string | null
  created_by: string
  created_by_name: string
  created_at: string
  updated_at: string
}

export interface TagRecord {
  id: string
  name: string
  description: string | null
  created_by: string
  created_by_name: string
  created_at: string
  updated_at: string
}

export interface CustomerTagRecord {
  id: string
  customer_id: string
  tag_id: string
  tag_name: string
  tag_description: string | null
  created_by: string
  created_at: string
}

export interface CustomerAssignee {
  id: string
  username: string
  display_name: string
  department_id: string
  department_name: string
}

export interface CustomerNameMatch {
  id: string
  customer_no: string
  name: string
  owner_name: string
}
