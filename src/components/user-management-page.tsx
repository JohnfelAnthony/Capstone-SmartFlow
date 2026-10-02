import * as React from "react"
import {
  ArrowUpCircleIcon,
  BadgeCheckIcon,
  CheckCircle2Icon,
  CirclePauseIcon,
  CirclePlayIcon,
  EyeIcon,
  KeyRoundIcon,
  MailIcon,
  PlusIcon,
  RefreshCcwIcon,
  SaveIcon,
  SearchIcon,
  ShieldCheckIcon,
  Trash2Icon,
  UserCheckIcon,
  UserCogIcon,
  UserPlusIcon,
  UsersIcon,
  XCircleIcon,
} from "lucide-react"

import {
  createAdminUser,
  deleteAdminUser,
  listAdminUsers,
  resetAdminPassword,
  updateAdminUser,
  type AdminUser,
} from "@/api/admin"
import { ApiError } from "@/api/client"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"
import "@/styles/admin-user-management.css"

type UserRole = "admin" | "user"
type UserStatus = "active" | "inactive"
type UserFilter = "all" | UserRole
type StatusFilter = "all" | UserStatus
type AccountCategory = "all" | "admin" | "standard" | "active" | "inactive" | "password"
type SheetMode = "view" | "edit" | "create"

type UserAccount = {
  id: number
  fullName: string
  username: string
  email: string
  role: UserRole
  status: UserStatus
  createdAt: string
  lastLoginAt: string | null
  runCount: number
  auditCount: number
  mustChangePassword: boolean
  isSelf?: boolean
}

type UserDraft = {
  fullName: string
  username: string
  email: string
  role: UserRole
  status: UserStatus
  mustChangePassword: boolean
}

const emptyDraft: UserDraft = {
  fullName: "",
  username: "",
  email: "",
  role: "user",
  status: "active",
  mustChangePassword: true,
}

const avatarColors = ["green", "blue", "purple", "amber", "gray"] as const

function initials(name: string) {
  const parts = name.trim().split(/\s+/)
  if (parts.length > 1) {
    return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
  }
  return (name[0] || "U").toUpperCase()
}

function avatarColor(username: string) {
  const hash = username.split("").reduce((sum, letter) => sum + letter.charCodeAt(0), 0)
  return avatarColors[hash % avatarColors.length]
}

function formatDate(value: string | null) {
  if (!value) {
    return "Never"
  }

  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value))
}

function roleFromApi(role: string): UserRole {
  return role.toLowerCase() === "admin" ? "admin" : "user"
}

function roleIdForRole(role: UserRole) {
  return role === "admin" ? 1 : 2
}

function apiUserToAccount(user: AdminUser): UserAccount {
  return {
    id: user.id,
    fullName: user.full_name,
    username: user.username,
    email: user.email ?? "",
    role: roleFromApi(user.role),
    status: user.status === "active" ? "active" : "inactive",
    createdAt: user.created_at ?? "",
    lastLoginAt: user.last_login_at,
    runCount: user.run_count,
    auditCount: user.audit_count,
    mustChangePassword: user.must_change_password,
    isSelf: user.is_self,
  }
}

function adminErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message
  }
  return fallback
}

function UserSelect({
  value,
  options,
  onChange,
}: {
  value: string
  options: { label: string; value: string }[]
  onChange: (value: string) => void
}) {
  return (
    <Select value={value} onValueChange={(nextValue) => nextValue !== null && onChange(nextValue)}>
      <SelectTrigger className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{children}</span>
}

function RoleBadge({ role }: { role: UserRole }) {
  return (
    <Badge variant={role === "admin" ? "default" : "secondary"} className="user-role-badge">
      {role === "admin" ? <ShieldCheckIcon data-icon="inline-start" /> : <UserCheckIcon data-icon="inline-start" />}
      {role === "admin" ? "Admin" : "User"}
    </Badge>
  )
}

function StatusBadge({ status }: { status: UserStatus }) {
  return (
    <Badge variant={status === "active" ? "secondary" : "outline"} className={cn("user-status-badge", status)}>
      {status === "active" ? <CheckCircle2Icon data-icon="inline-start" /> : <CirclePauseIcon data-icon="inline-start" />}
      {status === "active" ? "Active" : "Inactive"}
    </Badge>
  )
}

function UserIdentity({ user }: { user: UserAccount }) {
  return (
    <div className="user-identity">
      <Avatar className={cn("user-avatar", avatarColor(user.username))}>
        <AvatarFallback>{initials(user.fullName)}</AvatarFallback>
      </Avatar>
      <div>
        <div className="user-name-line">
          <span>{user.fullName}</span>
          {user.isSelf ? <Badge variant="outline">You</Badge> : null}
        </div>
        <div className="user-sub-line">@{user.username}</div>
      </div>
    </div>
  )
}

function draftFromUser(user: UserAccount): UserDraft {
  return {
    fullName: user.fullName,
    username: user.username,
    email: user.email,
    role: user.role,
    status: user.status,
    mustChangePassword: user.mustChangePassword,
  }
}

export function UserManagementPage() {
  const [users, setUsers] = React.useState<UserAccount[]>([])
  const [query, setQuery] = React.useState("")
  const [accountCategory, setAccountCategory] = React.useState<AccountCategory>("all")
  const [roleFilter, setRoleFilter] = React.useState<UserFilter>("all")
  const [statusFilter, setStatusFilter] = React.useState<StatusFilter>("all")
  const [selectedUserId, setSelectedUserId] = React.useState<number | null>(null)
  const [sheetMode, setSheetMode] = React.useState<SheetMode>("view")
  const [isSheetOpen, setIsSheetOpen] = React.useState(false)
  const [draft, setDraft] = React.useState<UserDraft>(emptyDraft)
  const [alert, setAlert] = React.useState("Loading user directory from SQLite.")
  const [isLoading, setIsLoading] = React.useState(false)

  const loadUsers = React.useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await listAdminUsers()
      const accounts = response.users.map(apiUserToAccount)
      setUsers(accounts)
      setAlert("User directory loaded from SQLite.")
    } catch (error) {
      setAlert(adminErrorMessage(error, "Unable to load users."))
    } finally {
      setIsLoading(false)
    }
  }, [])

  React.useEffect(() => {
    const timer = window.setTimeout(() => { void loadUsers() }, 0)
    return () => window.clearTimeout(timer)
  }, [loadUsers])

  const selectedUser = users.find((user) => user.id === selectedUserId) ?? null
  const activeAdminCount = users.filter((user) => user.role === "admin" && user.status === "active").length
  const inactiveUsers = users.filter((user) => user.status === "inactive")
  const accountCategories = [
    { label: "All Accounts", value: "all" as const, count: users.length },
    { label: "Admins", value: "admin" as const, count: users.filter((user) => user.role === "admin").length },
    { label: "Standard Users", value: "standard" as const, count: users.filter((user) => user.role === "user").length },
    { label: "Active", value: "active" as const, count: users.filter((user) => user.status === "active").length },
    { label: "Inactive", value: "inactive" as const, count: inactiveUsers.length },
    { label: "Password Reset", value: "password" as const, count: users.filter((user) => user.mustChangePassword).length },
  ]

  const filteredUsers = React.useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return users
      .filter((user) => {
        const matchesCategory =
          accountCategory === "all" ||
          (accountCategory === "admin" && user.role === "admin") ||
          (accountCategory === "standard" && user.role === "user") ||
          (accountCategory === "active" && user.status === "active") ||
          (accountCategory === "inactive" && user.status === "inactive") ||
          (accountCategory === "password" && user.mustChangePassword)
        const matchesQuery =
          !normalizedQuery ||
          user.fullName.toLowerCase().includes(normalizedQuery) ||
          user.username.toLowerCase().includes(normalizedQuery) ||
          user.email.toLowerCase().includes(normalizedQuery)
        const matchesRole = roleFilter === "all" || user.role === roleFilter
        const matchesStatus = statusFilter === "all" || user.status === statusFilter
        return matchesCategory && matchesQuery && matchesRole && matchesStatus
      })
      .sort((first, second) => Number(second.status === "active") - Number(first.status === "active"))
  }, [accountCategory, query, roleFilter, statusFilter, users])

  const metrics = [
    {
      label: "Total Users",
      value: users.length,
      hint: "Platform accounts",
      icon: UsersIcon,
      tone: "info",
    },
    {
      label: "Active Users",
      value: users.filter((user) => user.status === "active").length,
      hint: "Ready to sign in",
      icon: UserCheckIcon,
      tone: "success",
    },
    {
      label: "Inactive Accounts",
      value: inactiveUsers.length,
      hint: "Awaiting review",
      icon: UserPlusIcon,
      tone: "warning",
    },
    {
      label: "Admin Users",
      value: users.filter((user) => user.role === "admin" && user.status === "active").length,
      hint: "Active administrators",
      icon: ShieldCheckIcon,
      tone: "purple",
    },
  ]

  function openView(user: UserAccount) {
    setSelectedUserId(user.id)
    setDraft(draftFromUser(user))
    setSheetMode("view")
    setIsSheetOpen(true)
  }

  function openEdit(user: UserAccount) {
    setSelectedUserId(user.id)
    setDraft(draftFromUser(user))
    setSheetMode("edit")
    setIsSheetOpen(true)
  }

  function openCreate() {
    setSelectedUserId(null)
    setDraft(emptyDraft)
    setSheetMode("create")
    setIsSheetOpen(true)
  }

  function refreshUserData() {
    setQuery("")
    setAccountCategory("all")
    setRoleFilter("all")
    setStatusFilter("all")
    void loadUsers()
  }

  function mergeUser(user: AdminUser, message: string) {
    const account = apiUserToAccount(user)
    setUsers((current) => current.map((item) => (item.id === account.id ? account : item)))
    setAlert(message)
  }

  async function approveUser(user: UserAccount) {
    try {
      const updated = await updateAdminUser(user.id, { role_id: roleIdForRole("user"), status: "active", must_change_password: true })
      mergeUser(updated, `User '${user.username}' approved successfully.`)
    } catch (error) {
      setAlert(adminErrorMessage(error, `Unable to approve '${user.username}'.`))
    }
  }

  async function rejectUser(user: UserAccount) {
    try {
      await deleteAdminUser(user.id)
      setUsers((current) => current.filter((target) => target.id !== user.id))
      setAlert(`Inactive user '${user.username}' was rejected.`)
    } catch (error) {
      setAlert(adminErrorMessage(error, `Unable to reject '${user.username}'.`))
    }
  }

  async function activateUser(user: UserAccount) {
    try {
      const updated = await updateAdminUser(user.id, { status: "active" })
      mergeUser(updated, `User '${user.username}' activated successfully.`)
    } catch (error) {
      setAlert(adminErrorMessage(error, `Unable to activate '${user.username}'.`))
    }
  }

  async function deactivateUser(user: UserAccount) {
    if (user.role === "admin" && activeAdminCount <= 1) {
      setAlert("Safeguard: Cannot deactivate the last active administrator.")
      return
    }

    try {
      const updated = await updateAdminUser(user.id, { status: "inactive" })
      mergeUser(updated, `User '${user.username}' deactivated successfully.`)
    } catch (error) {
      setAlert(adminErrorMessage(error, `Unable to deactivate '${user.username}'.`))
    }
  }

  async function promoteUser(user: UserAccount) {
    try {
      const updated = await updateAdminUser(user.id, { role_id: roleIdForRole("admin") })
      mergeUser(updated, `User '${user.username}' promoted to Admin.`)
    } catch (error) {
      setAlert(adminErrorMessage(error, `Unable to promote '${user.username}'.`))
    }
  }

  async function resetPassword(user: UserAccount) {
    if (user.isSelf) {
      setAlert("Safeguard: Use change password to update your own password.")
      return
    }

    try {
      const response = await resetAdminPassword(user.id)
      mergeUser(
        response.user,
        `Temporary password for '${user.username}': ${response.temporary_password}. Copy it now; it is shown once.`
      )
    } catch (error) {
      setAlert(adminErrorMessage(error, `Unable to reset password for '${user.username}'.`))
    }
  }

  async function deleteUser(user: UserAccount) {
    if (user.isSelf) {
      setAlert("Safeguard: You cannot delete your own account while logged in.")
      return
    }

    if (user.role === "admin" && activeAdminCount <= 1) {
      setAlert("Safeguard: Cannot delete the last active administrator.")
      return
    }

    try {
      await deleteAdminUser(user.id)
      setUsers((current) => current.filter((target) => target.id !== user.id))
      setAlert(`User '${user.username}' permanently deleted.`)
      if (selectedUserId === user.id) {
        setIsSheetOpen(false)
        setSelectedUserId(null)
      }
    } catch (error) {
      setAlert(adminErrorMessage(error, `Unable to delete '${user.username}'.`))
    }
  }

  async function saveDraft() {
    const fullName = draft.fullName.trim()
    const username = draft.username.trim()
    const email = draft.email.trim() || null
    if (!fullName || !username) {
      setAlert("Full name and username are required.")
      return
    }

    if (sheetMode === "create") {
      try {
        const response = await createAdminUser({
          full_name: fullName,
          username,
          email,
          role_id: roleIdForRole(draft.role),
          status: draft.status,
          must_change_password: draft.mustChangePassword,
        })
        const createdUser = apiUserToAccount(response.user)
        setUsers((current) => [createdUser, ...current])
        setSelectedUserId(createdUser.id)
        setSheetMode("view")
        setAlert(`User '${createdUser.username}' created. Temporary password: ${response.temporary_password}. Copy it now; it is shown once.`)
      } catch (error) {
        setAlert(adminErrorMessage(error, "Unable to create user."))
      }
      return
    }

    if (selectedUser) {
      try {
        const updated = await updateAdminUser(selectedUser.id, {
          full_name: fullName,
          username,
          email,
          role_id: roleIdForRole(draft.role),
          status: draft.status,
          must_change_password: draft.mustChangePassword,
        })
        mergeUser(updated, `User '${username}' updated successfully.`)
        setSheetMode("view")
      } catch (error) {
        setAlert(adminErrorMessage(error, `Unable to update '${selectedUser.username}'.`))
      }
    }
  }

  return (
    <main className="smartflow-page user-management-page">
      <section className="user-management-hero">
        <div>
          <h1>User Management</h1>
        </div>
        <div className="user-management-hero-actions">
          <Button variant="outline" onClick={refreshUserData} disabled={isLoading}>
            <RefreshCcwIcon data-icon="inline-start" />
            {isLoading ? "Refreshing" : "Refresh"}
          </Button>
          <Button onClick={openCreate}>
            <PlusIcon data-icon="inline-start" />
            Add User
          </Button>
        </div>
      </section>

      <section className="user-metric-strip" aria-label="User account metrics">
        {metrics.map((metric) => {
          const Icon = metric.icon
          return (
            <div key={metric.label} className={cn("user-strip-metric", metric.tone)}>
              <Icon />
              <div>
                <div>
                  <strong>{metric.value}</strong>
                  <span>{metric.label}</span>
                </div>
                <small>{metric.hint}</small>
              </div>
            </div>
          )
        })}
      </section>

      <div className="user-notice">
        <BadgeCheckIcon />
        <span>{alert}</span>
      </div>

      <section className="user-workspace">
        <aside className="user-filter-rail">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UsersIcon />
                Account Groups
              </CardTitle>
              <CardDescription>{users.length} SQLite account{users.length === 1 ? "" : "s"}</CardDescription>
            </CardHeader>
            <CardContent className="user-category-list">
              {accountCategories.map((category) => (
                <button
                  key={category.value}
                  className={cn("user-category-button", accountCategory === category.value && "active")}
                  type="button"
                  onClick={() => setAccountCategory(category.value)}
                >
                  <span>{category.label}</span>
                  <Badge variant="secondary">{category.count}</Badge>
                </button>
              ))}
            </CardContent>
          </Card>

          <Card className="inactive-accounts-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UserPlusIcon />
                Review Queue
              </CardTitle>
              <CardDescription>{inactiveUsers.length} inactive account{inactiveUsers.length === 1 ? "" : "s"}</CardDescription>
            </CardHeader>
            <CardContent className="inactive-account-list">
              {inactiveUsers.length ? (
                inactiveUsers.map((user) => (
                  <div key={user.id} className="inactive-account-card">
                    <UserIdentity user={user} />
                    <div className="inactive-account-meta">
                      <span>
                        <MailIcon />
                        {user.email}
                      </span>
                      <span>Created {formatDate(user.createdAt)}</span>
                    </div>
                    <div className="inactive-account-actions">
                      <Button size="sm" onClick={() => approveUser(user)}>
                        <CheckCircle2Icon data-icon="inline-start" />
                        Approve
                      </Button>
                      <Button variant="destructive" size="sm" onClick={() => rejectUser(user)}>
                        <XCircleIcon data-icon="inline-start" />
                        Reject
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => openView(user)}>
                        <EyeIcon data-icon="inline-start" />
                        View
                      </Button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="user-empty-state compact">
                  <CheckCircle2Icon />
                  <strong>All Clear</strong>
                  <span>No inactive accounts.</span>
                </div>
              )}
            </CardContent>
          </Card>
        </aside>

        <div className="user-library-panel">
          <Card className="user-toolbar-card">
            <CardContent className="user-filter-toolbar">
              <label className="user-search-field">
                <SearchIcon />
                <Input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search by name, username, or email"
                />
              </label>
              <UserSelect
                value={roleFilter}
                onChange={(value) => setRoleFilter(value as UserFilter)}
                options={[
                  { label: "All Roles", value: "all" },
                  { label: "Admin", value: "admin" },
                  { label: "User", value: "user" },
                ]}
              />
              <UserSelect
                value={statusFilter}
                onChange={(value) => setStatusFilter(value as StatusFilter)}
                options={[
                  { label: "All Statuses", value: "all" },
                  { label: "Active", value: "active" },
                  { label: "Inactive", value: "inactive" },
                ]}
              />
              <Badge variant="secondary">{filteredUsers.length} shown</Badge>
            </CardContent>
          </Card>

          <Card className="user-directory-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UsersIcon />
                Account Directory
              </CardTitle>
              <CardDescription>Search, filter, and manage all platform accounts.</CardDescription>
              <CardAction>
                <Badge variant="secondary">{accountCategories.find((category) => category.value === accountCategory)?.label}</Badge>
              </CardAction>
            </CardHeader>
            <CardContent className="user-table-shell">
              {filteredUsers.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>User</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Last Login</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredUsers.map((user) => (
                      <TableRow key={user.id}>
                        <TableCell>
                          <UserIdentity user={user} />
                        </TableCell>
                        <TableCell>
                          <span className="user-email-cell">{user.email}</span>
                        </TableCell>
                        <TableCell>
                          <RoleBadge role={user.role} />
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={user.status} />
                        </TableCell>
                        <TableCell>{formatDate(user.lastLoginAt)}</TableCell>
                        <TableCell>
                          <div className="user-actions-inline">
                            <Button variant="ghost" size="icon-sm" title="View Details" onClick={() => openView(user)}>
                              <EyeIcon />
                            </Button>
                            <Button variant="ghost" size="icon-sm" title="Edit User" onClick={() => openEdit(user)}>
                              <UserCogIcon />
                            </Button>
                            {user.status === "active" ? (
                              <Button
                                variant="ghost"
                                size="icon-sm"
                                title="Deactivate"
                                onClick={() => deactivateUser(user)}
                              >
                                <CirclePauseIcon />
                              </Button>
                            ) : (
                              <Button variant="ghost" size="icon-sm" title="Activate" onClick={() => activateUser(user)}>
                                <CirclePlayIcon />
                              </Button>
                            )}
                            {user.role !== "admin" ? (
                              <Button variant="ghost" size="icon-sm" title="Promote to Admin" onClick={() => promoteUser(user)}>
                                <ArrowUpCircleIcon />
                              </Button>
                            ) : null}
                            {!user.isSelf ? (
                              <Button variant="ghost" size="icon-sm" title="Reset Password" onClick={() => resetPassword(user)}>
                                <KeyRoundIcon />
                              </Button>
                            ) : null}
                            {!user.isSelf ? (
                              <Button variant="destructive" size="icon-sm" title="Delete User" onClick={() => deleteUser(user)}>
                                <Trash2Icon />
                              </Button>
                            ) : null}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="user-empty-state">
                  <UsersIcon />
                  <strong>No users found</strong>
                  <span>Try adjusting your search or filters.</span>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </section>

      <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
        <SheetContent className="user-management-sheet" side="right">
          <SheetHeader>
            <SheetTitle>
              {sheetMode === "create" ? "Add User" : sheetMode === "edit" ? "Edit User" : selectedUser?.fullName ?? "User Details"}
            </SheetTitle>
            <SheetDescription>
              {sheetMode === "view"
                ? "Review account details, activity totals, and available admin actions."
                : "Edit the account fields stored in the SMARTFLOW SQLite database."}
            </SheetDescription>
          </SheetHeader>

          <div className="user-sheet-body">
            {sheetMode === "view" && selectedUser ? (
              <>
                <div className="user-sheet-profile">
                  <UserIdentity user={selectedUser} />
                  <div className="user-sheet-badges">
                    <RoleBadge role={selectedUser.role} />
                    <StatusBadge status={selectedUser.status} />
                    {selectedUser.mustChangePassword ? <Badge variant="outline">Password Change Required</Badge> : null}
                  </div>
                </div>

                <Card size="sm">
                  <CardHeader>
                    <CardTitle>Account Information</CardTitle>
                  </CardHeader>
                  <CardContent className="user-info-grid">
                    <div>
                      <span>Email</span>
                      <strong>{selectedUser.email}</strong>
                    </div>
                    <div>
                      <span>Username</span>
                      <strong>@{selectedUser.username}</strong>
                    </div>
                    <div>
                      <span>Member Since</span>
                      <strong>{formatDate(selectedUser.createdAt)}</strong>
                    </div>
                    <div>
                      <span>Last Login</span>
                      <strong>{formatDate(selectedUser.lastLoginAt)}</strong>
                    </div>
                  </CardContent>
                </Card>

                <div className="user-activity-grid">
                  <Card size="sm">
                    <CardHeader>
                      <CardTitle>Simulation Runs</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <strong>{selectedUser.runCount}</strong>
                    </CardContent>
                  </Card>
                  <Card size="sm">
                    <CardHeader>
                      <CardTitle>Audit Events</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <strong>{selectedUser.auditCount}</strong>
                    </CardContent>
                  </Card>
                </div>

                <Card size="sm">
                  <CardHeader>
                    <CardTitle>Admin Actions</CardTitle>
                    <CardDescription>These mirror the Dash account action callbacks against SQLite.</CardDescription>
                  </CardHeader>
                  <CardContent className="user-sheet-action-grid">
                    <Button variant="outline" onClick={() => openEdit(selectedUser)}>
                      <UserCogIcon data-icon="inline-start" />
                      Edit
                    </Button>
                    {selectedUser.status === "active" ? (
                      <Button variant="outline" onClick={() => deactivateUser(selectedUser)}>
                        <CirclePauseIcon data-icon="inline-start" />
                        Deactivate
                      </Button>
                    ) : (
                      <Button variant="outline" onClick={() => activateUser(selectedUser)}>
                        <CirclePlayIcon data-icon="inline-start" />
                        Activate
                      </Button>
                    )}
                    {selectedUser.role !== "admin" ? (
                      <Button variant="outline" onClick={() => promoteUser(selectedUser)}>
                        <ArrowUpCircleIcon data-icon="inline-start" />
                        Promote
                      </Button>
                    ) : null}
                    {!selectedUser.isSelf ? (
                      <Button variant="outline" onClick={() => resetPassword(selectedUser)}>
                        <KeyRoundIcon data-icon="inline-start" />
                        Reset Password
                      </Button>
                    ) : null}
                    {!selectedUser.isSelf ? (
                      <Button variant="destructive" onClick={() => deleteUser(selectedUser)}>
                        <Trash2Icon data-icon="inline-start" />
                        Delete
                      </Button>
                    ) : null}
                  </CardContent>
                </Card>
              </>
            ) : (
              <div className="user-form">
                <Card size="sm">
                  <CardHeader>
                    <CardTitle>Profile</CardTitle>
                    <CardDescription>Name the account and set its sign-in identity.</CardDescription>
                  </CardHeader>
                  <CardContent className="user-form-grid">
                    <label className="flex flex-col gap-1.5">
                      <FieldLabel>Full Name</FieldLabel>
                      <Input value={draft.fullName} onChange={(event) => setDraft({ ...draft, fullName: event.target.value })} />
                    </label>
                    <label className="flex flex-col gap-1.5">
                      <FieldLabel>Username</FieldLabel>
                      <Input value={draft.username} onChange={(event) => setDraft({ ...draft, username: event.target.value })} />
                    </label>
                    <label className="flex flex-col gap-1.5 user-form-full">
                      <FieldLabel>Email</FieldLabel>
                      <Input value={draft.email} onChange={(event) => setDraft({ ...draft, email: event.target.value })} />
                    </label>
                  </CardContent>
                </Card>

                <Card size="sm">
                  <CardHeader>
                    <CardTitle>Access</CardTitle>
                    <CardDescription>Assign role, account state, and password reset behavior.</CardDescription>
                  </CardHeader>
                  <CardContent className="user-form-grid">
                    <label className="flex flex-col gap-1.5">
                      <FieldLabel>Role</FieldLabel>
                      <UserSelect
                        value={draft.role}
                        onChange={(value) => setDraft({ ...draft, role: value as UserRole })}
                        options={[
                          { label: "Admin", value: "admin" },
                          { label: "User", value: "user" },
                        ]}
                      />
                    </label>
                    <label className="flex flex-col gap-1.5">
                      <FieldLabel>Status</FieldLabel>
                      <UserSelect
                        value={draft.status}
                        onChange={(value) => setDraft({ ...draft, status: value as UserStatus })}
                        options={[
                          { label: "Active", value: "active" },
                          { label: "Inactive", value: "inactive" },
                        ]}
                      />
                    </label>
                    <div className="user-password-toggle user-form-full">
                      <div>
                        <strong>Require password change</strong>
                        <span>Matches the Dash `must_change_password` behavior after resets.</span>
                      </div>
                      <Button
                        type="button"
                        variant={draft.mustChangePassword ? "default" : "outline"}
                        onClick={() => setDraft({ ...draft, mustChangePassword: !draft.mustChangePassword })}
                      >
                        {draft.mustChangePassword ? "Required" : "Not Required"}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </div>

          {sheetMode !== "view" ? (
            <SheetFooter className="user-sheet-footer">
              <Button variant="outline" onClick={() => setIsSheetOpen(false)}>
                <XCircleIcon data-icon="inline-start" />
                Cancel
              </Button>
              <Button onClick={saveDraft}>
                <SaveIcon data-icon="inline-start" />
                Save User
              </Button>
            </SheetFooter>
          ) : null}
        </SheetContent>
      </Sheet>
    </main>
  )
}
