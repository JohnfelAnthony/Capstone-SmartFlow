import * as React from "react"
import {
  CalendarDaysIcon,
  ClipboardListIcon,
  FileClockIcon,
  FilterIcon,
  ListOrderedIcon,
  RotateCcwIcon,
  SearchIcon,
  ShieldAlertIcon,
  SlidersHorizontalIcon,
  TriangleAlertIcon,
  UserRoundIcon,
} from "lucide-react"

import { listAuditLogs, type AuditLogRecord } from "@/api/admin"
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

type AuditActionFilter = "all" | "create" | "update" | "delete" | "login" | "backup"
type AuditTone = "success" | "info" | "danger" | "neutral" | "warning"

type AuditLog = {
  id: number
  timestamp: string
  username: string | null
  action: string
  target: string
  details: string
  ipAddress: string
}

const actionOptions: { label: string; value: AuditActionFilter }[] = [
  { label: "All Actions", value: "all" },
  { label: "Create / Approve", value: "create" },
  { label: "Update / Edit / Config", value: "update" },
  { label: "Delete / Reject", value: "delete" },
  { label: "Login / Logout", value: "login" },
  { label: "Backup / System", value: "backup" },
]

function formatTimestamp(value: string) {
  if (!value) {
    return "Unknown"
  }
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value))
}

function isoDate(value: string) {
  return value.slice(0, 10)
}

function apiAuditLogToView(log: AuditLogRecord): AuditLog {
  return {
    id: log.id,
    timestamp: log.timestamp ?? "",
    username: log.username,
    action: log.action,
    target: log.target,
    details: log.details ?? "",
    ipAddress: log.ip_address ?? "system",
  }
}

function auditErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message
  }
  return fallback
}

function actionTone(action: string): AuditTone {
  const normalized = action.toLowerCase()
  if (/(delete|reject|remove|failed|fail)/.test(normalized)) {
    return "danger"
  }
  if (/(create|approve|promote|register|success)/.test(normalized)) {
    return "success"
  }
  if (/(update|edit|change|modify|config|reset)/.test(normalized)) {
    return "info"
  }
  if (/(backup|restore|system|database)/.test(normalized)) {
    return "warning"
  }
  return "neutral"
}

function actionMatchesFilter(action: string, filter: AuditActionFilter) {
  if (filter === "all") {
    return true
  }

  const normalized = action.toLowerCase()
  if (filter === "create") {
    return /(create|approve|promote|register)/.test(normalized)
  }
  if (filter === "update") {
    return /(update|edit|change|modify|config|reset)/.test(normalized)
  }
  if (filter === "delete") {
    return /(delete|reject|remove)/.test(normalized)
  }
  if (filter === "login") {
    return /(login|logout|auth)/.test(normalized)
  }
  return /(backup|restore|system|database)/.test(normalized)
}

function AuditSelect({
  value,
  onChange,
}: {
  value: AuditActionFilter
  onChange: (value: AuditActionFilter) => void
}) {
  return (
    <Select value={value} onValueChange={(nextValue) => nextValue !== null && onChange(nextValue as AuditActionFilter)}>
      <SelectTrigger className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {actionOptions.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
}

export function AuditLogsPage() {
  const [search, setSearch] = React.useState("")
  const [userFilter, setUserFilter] = React.useState("")
  const [actionFilter, setActionFilter] = React.useState<AuditActionFilter>("all")
  const [startDate, setStartDate] = React.useState("")
  const [endDate, setEndDate] = React.useState("")
  const [selectedLogId, setSelectedLogId] = React.useState(0)
  const [logs, setLogs] = React.useState<AuditLog[]>([])
  const [alert, setAlert] = React.useState("Loading audit ledger from SQLite.")
  const [isLoading, setIsLoading] = React.useState(false)

  const loadLogs = React.useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await listAuditLogs({ limit: 500 })
      const nextLogs = response.logs.map(apiAuditLogToView)
      setLogs(nextLogs)
      setSelectedLogId((current) => current || nextLogs[0]?.id || 0)
      setAlert("Audit ledger loaded from SQLite.")
    } catch (error) {
      setAlert(auditErrorMessage(error, "Unable to load audit logs."))
    } finally {
      setIsLoading(false)
    }
  }, [])

  React.useEffect(() => {
    void loadLogs()
  }, [loadLogs])

  const filteredLogs = React.useMemo(() => {
    const query = search.trim().toLowerCase()
    const userQuery = userFilter.trim().toLowerCase()

    return logs.filter((log) => {
      const date = isoDate(log.timestamp)
      const matchesSearch =
        !query ||
        (log.username ?? "System").toLowerCase().includes(query) ||
        log.action.toLowerCase().includes(query) ||
        log.target.toLowerCase().includes(query) ||
        log.details.toLowerCase().includes(query)
      const matchesUser = !userQuery || (log.username ?? "System").toLowerCase().includes(userQuery)
      const matchesAction = actionMatchesFilter(log.action, actionFilter)
      const matchesStart = !startDate || date >= startDate
      const matchesEnd = !endDate || date <= endDate
      return matchesSearch && matchesUser && matchesAction && matchesStart && matchesEnd
    })
  }, [actionFilter, endDate, logs, search, startDate, userFilter])

  const selectedLog = filteredLogs.find((log) => log.id === selectedLogId) ?? filteredLogs[0] ?? null
  const today = new Date().toISOString().slice(0, 10)
  const eventsToday = logs.filter((log) => isoDate(log.timestamp) === today).length
  const failures = logs.filter((log) => /fail|reject/.test(log.action.toLowerCase())).length
  const configChanges = logs.filter((log) => /config|setting|permission|migration/.test(log.action.toLowerCase())).length
  const recentCritical = logs.filter((log) => actionTone(log.action) === "danger").slice(0, 3)

  const metrics = [
    { label: "Events Today", value: eventsToday, hint: today, icon: CalendarDaysIcon, tone: "info" },
    { label: "Total Logged", value: logs.length, hint: "SQLite ledger entries", icon: ListOrderedIcon, tone: "success" },
    { label: "Failures", value: failures, hint: "Failed or rejected", icon: TriangleAlertIcon, tone: "danger" },
    { label: "Config Changes", value: configChanges, hint: "Settings and access", icon: SlidersHorizontalIcon, tone: "warning" },
  ]

  function resetFilters() {
    setSearch("")
    setUserFilter("")
    setActionFilter("all")
    setStartDate("")
    setEndDate("")
    setSelectedLogId(logs[0]?.id ?? 0)
    void loadLogs()
  }

  return (
    <main className="smartflow-page audit-page">
      <section className="audit-hero">
        <div>
          <h1>System Audit Logs</h1>
          <p>Immutable history of user changes, deletions, exports, and configuration updates.</p>
        </div>
        <Button variant="outline" onClick={resetFilters} disabled={isLoading}>
          <RotateCcwIcon data-icon="inline-start" />
          {isLoading ? "Refreshing" : "Reset Filters"}
        </Button>
      </section>

      <section className="audit-metric-strip" aria-label="Audit log metrics">
        {metrics.map((metric) => {
          const Icon = metric.icon
          return (
            <div key={metric.label} className={cn("audit-strip-metric", metric.tone)}>
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
        <ClipboardListIcon />
        <span>{alert}</span>
      </div>

      <section className="audit-console-grid">
        <Card className="audit-filter-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FilterIcon />
              Audit Filters
            </CardTitle>
            <CardDescription>{filteredLogs.length} entries match the current filters.</CardDescription>
          </CardHeader>
          <CardContent className="audit-filter-content">
            <label className="audit-search-field">
              <SearchIcon />
              <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search user, action, target, or details" />
            </label>
            <AuditSelect value={actionFilter} onChange={setActionFilter} />
            <label className="audit-inline-field">
              <UserRoundIcon />
              <Input value={userFilter} onChange={(event) => setUserFilter(event.target.value)} placeholder="Filter by user" />
            </label>
            <div className="audit-date-grid">
              <label>
                <span>Start Date</span>
                <Input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
              </label>
              <label>
                <span>End Date</span>
                <Input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
              </label>
            </div>
          </CardContent>
        </Card>

        <Card className="audit-inspector-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileClockIcon />
              Event Inspector
            </CardTitle>
            <CardDescription>Selected ledger entry details.</CardDescription>
            <CardAction>
              <Badge variant="outline">Read Only</Badge>
            </CardAction>
          </CardHeader>
          <CardContent>
            {selectedLog ? (
              <div className="audit-inspector">
                <Badge variant={actionTone(selectedLog.action) === "danger" ? "destructive" : "secondary"} className={cn("audit-action-badge", actionTone(selectedLog.action))}>
                  {selectedLog.action}
                </Badge>
                <strong>{selectedLog.target}</strong>
                <span>{formatTimestamp(selectedLog.timestamp)}</span>
                <p>{selectedLog.details}</p>
                <div>
                  <small>User</small>
                  <span>{selectedLog.username ?? "System"}</span>
                </div>
                <div>
                  <small>Source</small>
                  <span>{selectedLog.ipAddress}</span>
                </div>
              </div>
            ) : (
              <div className="audit-empty-mini">No event selected.</div>
            )}
          </CardContent>
        </Card>

        <Card className="audit-ledger-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ClipboardListIcon />
              Audit Events Ledger
            </CardTitle>
            <CardDescription>Immutable, read-only history of every system action.</CardDescription>
            <CardAction>
              <Badge variant="secondary">{filteredLogs.length} entries</Badge>
            </CardAction>
          </CardHeader>
          <CardContent className="audit-ledger-content">
            {filteredLogs.length ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>User</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Target</TableHead>
                    <TableHead>Details</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredLogs.map((log) => {
                    const tone = actionTone(log.action)
                    return (
                      <TableRow
                        key={log.id}
                        className={cn("audit-log-row", selectedLog?.id === log.id && "selected")}
                        onClick={() => setSelectedLogId(log.id)}
                      >
                        <TableCell>{formatTimestamp(log.timestamp)}</TableCell>
                        <TableCell>{log.username ?? "System"}</TableCell>
                        <TableCell>
                          <Badge variant={tone === "danger" ? "destructive" : "secondary"} className={cn("audit-action-badge", tone)}>
                            {log.action}
                          </Badge>
                        </TableCell>
                        <TableCell>{log.target}</TableCell>
                        <TableCell className="audit-detail-cell">{log.details}</TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            ) : (
              <div className="audit-empty-state">
                <ClipboardListIcon />
                <strong>No audit events found</strong>
                <span>No entries match the current search or filter criteria.</span>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="audit-critical-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldAlertIcon />
              Watchlist
            </CardTitle>
            <CardDescription>Recent failed, rejected, or destructive actions.</CardDescription>
          </CardHeader>
          <CardContent className="audit-watchlist">
            {recentCritical.map((log) => (
              <button key={log.id} type="button" onClick={() => setSelectedLogId(log.id)}>
                <Badge variant="destructive">{log.action}</Badge>
                <span>{log.details}</span>
                <small>{formatTimestamp(log.timestamp)}</small>
              </button>
            ))}
          </CardContent>
        </Card>
      </section>
    </main>
  )
}
