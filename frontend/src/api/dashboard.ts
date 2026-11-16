import { http } from '@/api/http'
import type { ApiSuccess, DashboardSummary } from '@/types/api'

export interface DashboardQuery {
  start_date?: string
  end_date?: string
}

export async function getDashboardSummary(params: DashboardQuery = {}) {
  const response = await http.get<ApiSuccess<DashboardSummary>>('/dashboard/summary', { params })
  return response.data.data
}
