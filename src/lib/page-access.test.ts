import { describe, expect, it } from "vitest"
import { canViewPage, permissionPageFor } from "./page-access"

describe("Route Planner navigation and render permission", () => {
  it("maps the Route Planner identity to scenarios:view without changing other pages", () => {
    expect(permissionPageFor("route-planner")).toBe("scenarios")
    expect(permissionPageFor("compare")).toBe("compare")
    expect(canViewPage({ role: "user", permissions: [{ page: "scenarios", action: "view" }] }, "route-planner")).toBe(true)
  })

  it("denies guests and users without scenario view", () => {
    expect(canViewPage(null, "route-planner")).toBe(false)
    expect(canViewPage({ role: "user", permissions: [{ page: "scenarios", action: "edit" }] }, "route-planner")).toBe(false)
    expect(canViewPage({ role: "user", permissions: [{ page: "route-planner", action: "view" }] }, "route-planner")).toBe(false)
  })

  it("keeps administrator access and the existing admin-only page rule", () => {
    expect(canViewPage({ role: "Admin", permissions: [] }, "route-planner")).toBe(true)
    expect(canViewPage({ role: "user", permissions: [{ page: "admin-users", action: "view" }] }, "admin-users")).toBe(false)
  })
})
