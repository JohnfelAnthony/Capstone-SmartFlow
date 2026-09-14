import * as React from "react"
import {
  BadgeCheckIcon,
  BrainIcon,
  ChartLineIcon,
  ClipboardListIcon,
  Code2Icon,
  DatabaseIcon,
  FileOutputIcon,
  GaugeIcon,
  GraduationCapIcon,
  KeyRoundIcon,
  Layers3Icon,
  LockIcon,
  MapPinnedIcon,
  PlayCircleIcon,
  RotateCcwIcon,
  SaveIcon,
  SearchIcon,
  ShieldAlertIcon,
  ShieldCheckIcon,
  ShieldIcon,
  UsersIcon,
  XCircleIcon,
} from "lucide-react"

import {
  listAdminRoles,
  updateRolePermissions,
  type AdminRole,
  type RolePermissionUpdate,
} from "@/api/admin"
import { ApiError } from "@/api/client"
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
import { Checkbox } from "@/components/ui/checkbox"
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"
import "@/styles/admin-user-management.css"

type RoleId = "admin" | "user"

type PermissionAction = {
  page: string
  action: string
  description: string
}

type PermissionGroup = {
  label: string
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>
  items: PermissionAction[]
}

type RoleDefinition = {
  id: RoleId
  label: string
  description: string
  note: string
  locked: boolean
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>
  tone: "purple" | "green"
}

type PermissionMap = Record<RoleId, Set<string>>

const protectedPermissionKeys = new Set([
  "admin-users:view",
  "admin-roles:view",
  "admin-audit:view",
  "admin-backups:view",
])

const permissionGroups: PermissionGroup[] = [
  {
    label: "Dashboard Access",
    icon: GaugeIcon,
    items: [{ page: "dashboard", action: "view", description: "View Dashboard Overview" }],
  },
  {
    label: "Simulation Control",
    icon: PlayCircleIcon,
    items: [
      { page: "simulation", action: "view", description: "View Simulation Control Panel" },
      { page: "simulation", action: "run", description: "Execute Traffic Simulation Runs" },
    ],
  },
  {
    label: "Scenario Management",
    icon: MapPinnedIcon,
    items: [
      { page: "scenarios", action: "view", description: "View Scenarios Configurations" },
      { page: "scenarios", action: "create", description: "Create Custom Scenarios" },
      { page: "scenarios", action: "edit", description: "Edit Scenario Settings" },
      { page: "scenarios", action: "delete", description: "Delete Scenario Presets" },
    ],
  },
  {
    label: "Performance Reports",
    icon: ChartLineIcon,
    items: [{ page: "performance", action: "view", description: "View Performance Analytics Charts" }],
  },
  {
    label: "AI Agent RL Panel",
    icon: BrainIcon,
    items: [{ page: "ai-agent", action: "view", description: "View AI Agent Reinforcement Learning Telemetry" }],
  },
  {
    label: "RL Training",
    icon: GraduationCapIcon,
    items: [{ page: "rl-training", action: "view", description: "View RL Training Jobs and Model Management" }],
  },
  {
    label: "Runs and Reports Export",
    icon: FileOutputIcon,
    items: [
      { page: "runs-reports", action: "view", description: "View Runs History List" },
      { page: "runs-reports", action: "export", description: "Export Simulation Reports (CSV/Excel/PDF)" },
    ],
  },
  {
    label: "Compare Runs",
    icon: Code2Icon,
    items: [{ page: "compare", action: "view", description: "View Side-by-Side Run Comparison" }],
  },
  {
    label: "User Management",
    icon: UsersIcon,
    items: [{ page: "admin-users", action: "view", description: "Admin: Account Approvals & User Management" }],
  },
  {
    label: "Role Access Control",
    icon: ShieldIcon,
    items: [{ page: "admin-roles", action: "view", description: "Admin: Access Control Permissions Matrix" }],
  },
  {
    label: "Audit Logs",
    icon: ClipboardListIcon,
    items: [{ page: "admin-audit", action: "view", description: "Admin: View Audit Ledger" }],
  },
  {
    label: "Backup and Restore",
    icon: DatabaseIcon,
    items: [{ page: "admin-backups", action: "view", description: "Admin: Database Backups & Restore" }],
  },
]

const roles: RoleDefinition[] = [
  {
    id: "admin",
    label: "Administrator",
    description: "Full platform access with security oversight.",
    note: "Locked read-only role with every SMARTFLOW permission granted.",
    locked: true,
    icon: ShieldCheckIcon,
    tone: "purple",
  },
  {
    id: "user",
    label: "User",
    description: "Standard platform access for experiments and analysis.",
    note: "Editable role for operators, researchers, and lab users.",
    locked: false,
    icon: UsersIcon,
    tone: "green",
  },
]

const allPermissionKeys = permissionGroups.flatMap((group) =>
  group.items.map((permission) => permissionKey(permission.page, permission.action))
)

const fallbackPermissions: PermissionMap = {
  admin: new Set(allPermissionKeys),
  user: new Set([
    "dashboard:view",
    "simulation:view",
    "simulation:run",
    "scenarios:view",
    "scenarios:create",
    "scenarios:edit",
    "performance:view",
    "rl-training:view",
    "runs-reports:view",
    "runs-reports:export",
    "compare:view",
  ]),
}

function permissionKey(page: string, action: string) {
  return `${page}:${action}`
}

function pendingKey(roleId: RoleId, key: string) {
  return `${roleId}:${key}`
}

function permissionLabelFromKey(key: string) {
  const found = permissionGroups.flatMap((group) => group.items).find((permission) => permissionKey(permission.page, permission.action) === key)
  return found?.description ?? key
}

function permissionMapFromRoles(apiRoles: AdminRole[]): { permissions: PermissionMap; roleIds: Record<RoleId, number> } {
  const nextPermissions: PermissionMap = {
    admin: new Set(allPermissionKeys),
    user: new Set(),
  }
  const roleIds: Record<RoleId, number> = { admin: 1, user: 2 }

  apiRoles.forEach((role) => {
    const roleId = role.name.toLowerCase() === "admin" ? "admin" : role.name.toLowerCase() === "user" ? "user" : null
    if (!roleId) {
      return
    }
    roleIds[roleId] = role.id
    if (roleId === "user") {
      nextPermissions.user = new Set(role.permissions.map((permission) => permissionKey(permission.page, permission.action)))
    }
  })

  return { permissions: nextPermissions, roleIds }
}

function roleErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message
  }
  return fallback
}

function RoleSelect({
  value,
  onChange,
}: {
  value: RoleId
  onChange: (value: RoleId) => void
}) {
  return (
    <Select value={value} onValueChange={(nextValue) => nextValue !== null && onChange(nextValue as RoleId)}>
      <SelectTrigger className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {roles.map((role) => (
            <SelectItem key={role.id} value={role.id}>
              {role.label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
}

function computeEffectivePermissions(roleId: RoleId, pending: Record<string, boolean>, basePermissions: PermissionMap) {
  const effective = new Set(basePermissions[roleId])

  Object.entries(pending).forEach(([key, enabled]) => {
    const [pendingRoleId, page, action] = key.split(":")
    if (pendingRoleId !== roleId) {
      return
    }

    const realKey = permissionKey(page, action)
    if (enabled) {
      effective.add(realKey)
    } else {
      effective.delete(realKey)
    }
  })

  return effective
}

export function RoleAccessControlPage() {
  const [selectedRoleId, setSelectedRoleId] = React.useState<RoleId>("user")
  const [query, setQuery] = React.useState("")
  const [pending, setPending] = React.useState<Record<string, boolean>>({})
  const [basePermissions, setBasePermissions] = React.useState<PermissionMap>(fallbackPermissions)
  const [serverRoleIds, setServerRoleIds] = React.useState<Record<RoleId, number>>({ admin: 1, user: 2 })
  const [showProtectedConfirm, setShowProtectedConfirm] = React.useState(false)
  const [alert, setAlert] = React.useState("Loading permission matrix from SQLite.")
  const [isLoading, setIsLoading] = React.useState(false)

  const loadRoles = React.useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await listAdminRoles()
      const mapped = permissionMapFromRoles(response.roles)
      setBasePermissions(mapped.permissions)
      setServerRoleIds(mapped.roleIds)
      setAlert("Permission matrix loaded from SQLite. Toggle editable permissions, then save.")
    } catch (error) {
      setAlert(roleErrorMessage(error, "Unable to load role permissions."))
    } finally {
      setIsLoading(false)
    }
  }, [])

  React.useEffect(() => {
    void loadRoles()
  }, [loadRoles])

  const selectedRole = roles.find((role) => role.id === selectedRoleId) ?? roles[1]
  const SelectedRoleIcon = selectedRole.icon
  const pendingCount = Object.keys(pending).length
  const selectedEffective = computeEffectivePermissions(selectedRoleId, pending, basePermissions)
  const adminEffective = computeEffectivePermissions("admin", pending, basePermissions)
  const userEffective = computeEffectivePermissions("user", pending, basePermissions)
  const restrictedFromUser = allPermissionKeys.length - userEffective.size
  const protectedGranted = [...protectedPermissionKeys].filter((key) => adminEffective.has(key)).length
  const protectedPending = Object.keys(pending).some((key) => protectedPermissionKeys.has(key.split(":").slice(1).join(":")))

  const visibleGroups = React.useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) {
      return permissionGroups
    }

    return permissionGroups
      .map((group) => ({
        ...group,
        items: group.items.filter((permission) => {
          const key = permissionKey(permission.page, permission.action)
          return (
            group.label.toLowerCase().includes(normalized) ||
            permission.description.toLowerCase().includes(normalized) ||
            key.toLowerCase().includes(normalized)
          )
        }),
      }))
      .filter((group) => group.items.length > 0)
  }, [query])

  const metrics = [
    {
      label: "Total Roles",
      value: roles.length,
      icon: UsersIcon,
      hint: "Configured role types",
      tone: "info",
    },
    {
      label: "Permissions",
      value: allPermissionKeys.length,
      icon: Layers3Icon,
      hint: "Matrix controls",
      tone: "success",
    },
    {
      label: "Admin Security",
      value: protectedGranted,
      icon: ShieldCheckIcon,
      hint: "Protected permissions",
      tone: "purple",
    },
    {
      label: "User Restrictions",
      value: restrictedFromUser,
      icon: LockIcon,
      hint: "Blocked from users",
      tone: "warning",
    },
  ]

  function isEnabled(roleId: RoleId, key: string) {
    return computeEffectivePermissions(roleId, pending, basePermissions).has(key)
  }

  function togglePermission(roleId: RoleId, key: string, enabled: boolean) {
    const role = roles.find((item) => item.id === roleId)
    if (!role || role.locked) {
      return
    }

    const keyForPending = pendingKey(roleId, key)
    const originalEnabled = basePermissions[roleId].has(key)
    setPending((current) => {
      const next = { ...current }
      if (enabled === originalEnabled) {
        delete next[keyForPending]
      } else {
        next[keyForPending] = enabled
      }
      return next
    })
    setAlert("Permission change staged. Save to apply or reset to discard.")
  }

  function resetChanges() {
    if (!pendingCount) {
      setAlert("Nothing to reset.")
      return
    }

    setPending({})
    setShowProtectedConfirm(false)
    setAlert("All pending permission changes discarded.")
  }

  function requestSave() {
    if (!pendingCount) {
      setAlert("No changes to save.")
      return
    }

    if (protectedPending) {
      setShowProtectedConfirm(true)
      setAlert("Protected admin permissions selected. Confirmation required.")
      return
    }

    applyPendingChanges()
  }

  async function applyPendingChanges() {
    const updatesByRole: Record<RoleId, RolePermissionUpdate[]> = { admin: [], user: [] }
    Object.entries(pending).forEach(([key, enabled]) => {
      const [roleId, page, action] = key.split(":") as [RoleId, string, string]
      updatesByRole[roleId].push({ page, action, enabled })
    })

    try {
      await Promise.all(
        (Object.keys(updatesByRole) as RoleId[])
          .filter((roleId) => updatesByRole[roleId].length > 0)
          .map((roleId) => updateRolePermissions(serverRoleIds[roleId], updatesByRole[roleId]))
      )
      setPending({})
      setShowProtectedConfirm(false)
      setAlert("Permissions saved successfully to SQLite.")
      await loadRoles()
    } catch (error) {
      setAlert(roleErrorMessage(error, "Unable to save permission changes."))
    }
  }

  return (
    <main className="smartflow-page role-access-page">
      <section className="role-access-hero">
        <div>
          <h1>Role & Access Control</h1>
        </div>
        <div className="role-access-actions">
          <Button variant="outline" onClick={resetChanges}>
            <RotateCcwIcon data-icon="inline-start" />
            Reset
          </Button>
          <Button disabled={!pendingCount || isLoading} onClick={requestSave}>
            <SaveIcon data-icon="inline-start" />
            Save Changes
          </Button>
        </div>
      </section>

      <section className="role-metric-deck" aria-label="Role access metrics">
        {metrics.map((metric) => {
          const Icon = metric.icon
          return (
            <div key={metric.label} className={cn("role-strip-metric", metric.tone)}>
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

      <section className="role-command-strip">
        {roles.map((role) => {
          const Icon = role.icon
          const effective = computeEffectivePermissions(role.id, pending, basePermissions)
          const isSelected = selectedRoleId === role.id
          return (
            <button
              key={role.id}
              className={cn("role-focus-card", role.tone, isSelected && "selected")}
              type="button"
              onClick={() => setSelectedRoleId(role.id)}
            >
              <span className="role-focus-icon">
                <Icon />
              </span>
              <span className="role-focus-copy">
                <strong>{role.label}</strong>
                <small>{role.description}</small>
              </span>
              <span className="role-focus-count">
                {effective.size}/{allPermissionKeys.length}
              </span>
              <Badge variant={role.locked ? "outline" : "secondary"}>{role.locked ? "Locked" : "Editable"}</Badge>
            </button>
          )
        })}
      </section>

      <div className="role-notice-row">
        <div className={cn("role-notice", pendingCount ? "warning" : "ready")}>
          {pendingCount ? <ShieldAlertIcon /> : <BadgeCheckIcon />}
          <span>{pendingCount ? `${pendingCount} pending change${pendingCount === 1 ? "" : "s"}. ${alert}` : alert}</span>
        </div>
        {showProtectedConfirm ? (
          <Card className="role-protected-confirm" size="sm">
            <CardContent>
              <ShieldAlertIcon />
              <span>Protected admin permissions are included. This action would be audited.</span>
              <Button size="sm" variant="outline" onClick={() => setShowProtectedConfirm(false)}>
                <XCircleIcon data-icon="inline-start" />
                Cancel
              </Button>
              <Button size="sm" onClick={applyPendingChanges}>
                <ShieldCheckIcon data-icon="inline-start" />
                Confirm & Save
              </Button>
            </CardContent>
          </Card>
        ) : null}
      </div>

      <section className="role-access-grid">
        <Card className="role-matrix-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <KeyRoundIcon />
              Permission Matrix
            </CardTitle>
            <CardDescription>Compare permissions across roles and stage edits safely.</CardDescription>
            <CardAction>
              <Badge variant="secondary">{visibleGroups.reduce((total, group) => total + group.items.length, 0)} visible</Badge>
            </CardAction>
          </CardHeader>
          <CardContent className="role-matrix-content">
            <div className="role-toolbar">
              <label className="role-search-field">
                <SearchIcon />
                <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Permission name or key..." />
              </label>
              <RoleSelect value={selectedRoleId} onChange={setSelectedRoleId} />
              <div className="role-legend">
                <span>
                  <i className="enabled" />
                  Enabled
                </span>
                <span>
                  <i className="disabled" />
                  Disabled
                </span>
                <span>
                  <i className="locked" />
                  Locked
                </span>
              </div>
            </div>

            <div className="role-matrix-scroll">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Permission</TableHead>
                    <TableHead>Key</TableHead>
                    {roles.map((role) => (
                      <TableHead key={role.id} className={cn("role-column-heading", selectedRoleId === role.id && "selected")}>
                        {role.label}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleGroups.map((group) => {
                    const Icon = group.icon
                    return (
                      <React.Fragment key={group.label}>
                        <TableRow className="role-group-row">
                          <TableCell colSpan={2 + roles.length}>
                            <Icon />
                            {group.label}
                          </TableCell>
                        </TableRow>
                        {group.items.map((permission) => {
                          const key = permissionKey(permission.page, permission.action)
                          return (
                            <TableRow key={key}>
                              <TableCell className="role-permission-name">
                                <span>{permission.description}</span>
                                {protectedPermissionKeys.has(key) ? <Badge variant="outline">Protected</Badge> : null}
                              </TableCell>
                              <TableCell>
                                <code className="role-permission-key">{key}</code>
                              </TableCell>
                              {roles.map((role) => {
                                const enabled = isEnabled(role.id, key)
                                return (
                                  <TableCell
                                    key={role.id}
                                    className={cn("role-toggle-cell", selectedRoleId === role.id && "selected")}
                                  >
                                    {role.locked ? (
                                      <span className={cn("role-lock-toggle", enabled && "enabled")}>
                                        <LockIcon />
                                      </span>
                                    ) : (
                                      <Checkbox
                                        checked={enabled}
                                        onCheckedChange={(checked) => togglePermission(role.id, key, Boolean(checked))}
                                      />
                                    )}
                                  </TableCell>
                                )
                              })}
                            </TableRow>
                          )
                        })}
                      </React.Fragment>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        <Card className={cn("role-inspector-card", selectedRole.tone)}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <SelectedRoleIcon />
              {selectedRole.label}
            </CardTitle>
            <CardDescription>{selectedRole.note}</CardDescription>
            <CardAction>
              <Badge variant={selectedRole.locked ? "outline" : "secondary"}>{selectedRole.locked ? "Read Only" : "Editable"}</Badge>
            </CardAction>
          </CardHeader>
          <CardContent className="role-inspector-content">
            <div className="role-inspector-stats">
              <div>
                <strong>{selectedEffective.size}</strong>
                <span>Granted</span>
              </div>
              <div>
                <strong>{allPermissionKeys.length - selectedEffective.size}</strong>
                <span>Restricted</span>
              </div>
            </div>
            <div className="role-inspector-section">
              <span>Protected Access</span>
              <div className="role-protected-list">
                {[...protectedPermissionKeys].map((key) => (
                  <div key={key}>
                    <Badge variant={selectedEffective.has(key) ? "secondary" : "outline"}>
                      {selectedEffective.has(key) ? "Granted" : "Blocked"}
                    </Badge>
                    <small>{permissionLabelFromKey(key)}</small>
                  </div>
                ))}
              </div>
            </div>
            <div className="role-inspector-section">
              <span>Policy</span>
              <p>
                {selectedRole.locked
                  ? "Administrator permissions are locked in this UI to preserve access to the admin platform."
                  : "User permissions can be changed, staged, reviewed, then saved into SQLite."}
              </p>
            </div>
          </CardContent>
        </Card>
      </section>
    </main>
  )
}
