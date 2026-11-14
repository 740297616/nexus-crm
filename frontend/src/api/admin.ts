import { http } from '@/api/http'
import type {
  ApiSuccess,
  DataScope,
  DepartmentRecord,
  PageData,
  PermissionRecord,
  RoleRecord,
  UserRecord,
} from '@/types/api'

export async function listUsers(params: {
  search?: string
  department_id?: string
  page?: number
  page_size?: number
}) {
  const response = await http.get<ApiSuccess<PageData<UserRecord>>>('/users', { params })
  return response.data.data
}

export async function createUser(payload: {
  username: string
  email: string | null
  display_name: string
  password: string
  department_id: string | null
  role_ids: string[]
}) {
  const response = await http.post<ApiSuccess<UserRecord>>('/users', payload)
  return response.data.data
}

export async function updateUser(
  userId: string,
  payload: { email: string | null; display_name: string; department_id: string | null },
) {
  const response = await http.patch<ApiSuccess<UserRecord>>(`/users/${userId}`, payload)
  return response.data.data
}

export async function updateUserStatus(userId: string, status: 'active' | 'disabled') {
  const response = await http.patch<ApiSuccess<UserRecord>>(`/users/${userId}/status`, { status })
  return response.data.data
}

export async function updateUserRoles(userId: string, roleIds: string[]) {
  const response = await http.put<ApiSuccess<UserRecord>>(`/users/${userId}/roles`, {
    role_ids: roleIds,
  })
  return response.data.data
}

export async function listDepartments() {
  const response = await http.get<ApiSuccess<PageData<DepartmentRecord>>>('/departments')
  return response.data.data.items
}

export async function createDepartment(payload: { name: string; parent_id: string | null }) {
  const response = await http.post<ApiSuccess<DepartmentRecord>>('/departments', payload)
  return response.data.data
}

export async function updateDepartment(
  id: string,
  payload: { name?: string; parent_id?: string | null; is_active?: boolean },
) {
  const response = await http.patch<ApiSuccess<DepartmentRecord>>(`/departments/${id}`, payload)
  return response.data.data
}

export async function deleteDepartment(id: string) {
  await http.delete(`/departments/${id}`)
}

export async function listRoles() {
  const response = await http.get<ApiSuccess<PageData<RoleRecord>>>('/roles')
  return response.data.data.items
}

export async function listPermissions() {
  const response = await http.get<ApiSuccess<PageData<PermissionRecord>>>('/permissions')
  return response.data.data.items
}

export async function createRole(payload: {
  name: string
  code: string
  description: string | null
  data_scope: DataScope
}) {
  const response = await http.post<ApiSuccess<RoleRecord>>('/roles', payload)
  return response.data.data
}

export async function updateRole(
  roleId: string,
  payload: { name: string; description: string | null; data_scope: DataScope },
) {
  const response = await http.patch<ApiSuccess<RoleRecord>>(`/roles/${roleId}`, payload)
  return response.data.data
}

export async function updateRolePermissions(roleId: string, permissionCodes: string[]) {
  const response = await http.put<ApiSuccess<RoleRecord>>(`/roles/${roleId}/permissions`, {
    permission_codes: permissionCodes,
  })
  return response.data.data
}

export async function deleteRole(roleId: string) {
  await http.delete(`/roles/${roleId}`)
}
