import { API_BASE_URL, ApiError, apiRequest } from "@/api/client"

export type AdminUser = {
  id: number
  full_name: string
  username: string
  email: string | null
  role: string
  role_id: number
  status: string
  created_at: string | null
  updated_at: string | null
  last_login_at: string | null
  must_change_password: boolean
  run_count: number
  audit_count: number
  is_self: boolean
}

export type AdminUserCreatePayload = {
  full_name: string
  username: string
  email: string | null
  role_id: number
  status: "active" | "inactive"
  must_change_password: boolean
}

export type AdminUserUpdatePayload = Partial<AdminUserCreatePayload>

export type AdminUserCreateResponse = {
  user: AdminUser
  temporary_password: string
  message: string
}

export type AdminPasswordResetResponse = {
  user: AdminUser
  temporary_password: string
  message: string
}

export type Permission = {
  page: string
  action: string
}

export type AdminRole = {
  id: number
  name: string
  description: string | null
  permissions: Permission[]
  locked: boolean
}

export type RolePermissionUpdate = {
  page: string
  action: string
  enabled: boolean
}

export type AuditLogRecord = {
  id: number
  user_id: number | null
  username: string | null
  action: string
  target: string
  details: string | null
  timestamp: string | null
  ip_address: string | null
  user_agent: string | null
}

export type BackupRecord = {
  id: number
  filename: string
  created_by: number | null
  username: string | null
  created_at: string | null
  size_bytes: number
}

export type BackupActionResponse = {
  message: string
  backup: BackupRecord | null
}

export function listAdminUsers(params: { roleId?: number; status?: string } = {}) {
  const query = new URLSearchParams()
  if (params.roleId) {
    query.set("role_id", String(params.roleId))
  }
  if (params.status) {
    query.set("status", params.status)
  }
  const suffix = query.size ? `?${query.toString()}` : ""
  return apiRequest<{ users: AdminUser[] }>(`/api/admin/users${suffix}`)
}

export function createAdminUser(payload: AdminUserCreatePayload) {
  return apiRequest<AdminUserCreateResponse>("/api/admin/users", {
    method: "POST",
    body: payload,
  })
}

export function updateAdminUser(userId: number, payload: AdminUserUpdatePayload) {
  return apiRequest<AdminUser>(`/api/admin/users/${userId}`, {
    method: "PUT",
    body: payload,
  })
}

export function deleteAdminUser(userId: number) {
  return apiRequest<{ message: string }>(`/api/admin/users/${userId}`, {
    method: "DELETE",
  })
}

export function resetAdminPassword(userId: number) {
  return apiRequest<AdminPasswordResetResponse>(`/api/admin/users/${userId}/reset-password`, {
    method: "POST",
  })
}

export function listAdminRoles() {
  return apiRequest<{ roles: AdminRole[] }>("/api/admin/roles")
}

export function updateRolePermissions(roleId: number, updates: RolePermissionUpdate[]) {
  return apiRequest<AdminRole>(`/api/admin/roles/${roleId}/permissions`, {
    method: "PUT",
    body: { updates },
  })
}

export function listAuditLogs(params: { userId?: number; action?: string; limit?: number } = {}) {
  const query = new URLSearchParams()
  if (params.userId) {
    query.set("user_id", String(params.userId))
  }
  if (params.action) {
    query.set("action", params.action)
  }
  if (params.limit) {
    query.set("limit", String(params.limit))
  }
  const suffix = query.size ? `?${query.toString()}` : ""
  return apiRequest<{ logs: AuditLogRecord[] }>(`/api/admin/audit-logs${suffix}`)
}

export function listBackups() {
  return apiRequest<{ backups: BackupRecord[] }>("/api/admin/backups")
}

export function createBackup() {
  return apiRequest<BackupActionResponse>("/api/admin/backups", {
    method: "POST",
  })
}

export function restoreBackup(backupId: number) {
  return apiRequest<BackupActionResponse>(`/api/admin/backups/${backupId}/restore`, {
    method: "POST",
  })
}

export function deleteBackup(backupId: number) {
  return apiRequest<{ message: string }>(`/api/admin/backups/${backupId}`, {
    method: "DELETE",
  })
}

async function downloadFile(path: string, fallbackFilename: string) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
  })
  if (!response.ok) {
    let message = `Download failed with status ${response.status}.`
    try {
      const payload = await response.json()
      if (typeof payload.detail === "string") {
        message = payload.detail
      }
    } catch {
      // Keep the generic message when the server did not send JSON.
    }
    throw new ApiError(response.status, message)
  }

  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = objectUrl
  link.download = fallbackFilename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}

export function downloadBackup(backupId: number, filename: string) {
  return downloadFile(`/api/admin/backups/${backupId}/download`, filename)
}

export function downloadDatabase() {
  return downloadFile("/api/admin/database/download", "smartflow.db")
}
