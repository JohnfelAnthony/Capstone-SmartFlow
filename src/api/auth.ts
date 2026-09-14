import { apiRequest } from "@/api/client"

export type Permission = {
  page: string
  action: string
}

export type CurrentUser = {
  id: number
  username: string
  full_name: string
  email: string | null
  role: string
  role_id: number
  status: string
  must_change_password: boolean
  permissions: Permission[]
}

export type LoginResponse = {
  user: CurrentUser
  landing_path: string | null
}

export type RegisterResponse = {
  message: string
  account_status: string
}

export function login(username: string, password: string) {
  return apiRequest<LoginResponse>("/api/auth/login", {
    method: "POST",
    body: { username, password },
  })
}

export function registerAccount(payload: {
  full_name: string
  username: string
  email?: string
  password: string
  confirm_password: string
}) {
  return apiRequest<RegisterResponse>("/api/auth/register", {
    method: "POST",
    body: payload,
  })
}

export function getCurrentUser() {
  return apiRequest<CurrentUser>("/api/auth/me")
}

export function changePassword(payload: {
  current_password: string
  new_password: string
  confirm_password: string
}) {
  return apiRequest<{ message: string }>("/api/auth/change-password", {
    method: "POST",
    body: payload,
  })
}

export function logout() {
  return apiRequest<{ ok: boolean }>("/api/auth/logout", {
    method: "POST",
  })
}
