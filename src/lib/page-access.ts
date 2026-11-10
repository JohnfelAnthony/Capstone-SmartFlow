import type { CurrentUser } from "@/api/auth"

export function permissionPageFor(page: string) {
  return page === "route-planner" ? "scenarios" : page
}

export function canViewPage(user: Pick<CurrentUser, "role" | "permissions"> | null, page: string) {
  if (!user) return false
  if (user.role.toLowerCase() === "admin") return true
  if (page.startsWith("admin-")) return false
  const permissionPage = permissionPageFor(page)
  return user.permissions.some(permission => permission.page === permissionPage && permission.action === "view")
}
