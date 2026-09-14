import * as React from "react"
import {
  ArchiveRestoreIcon,
  ClockIcon,
  DatabaseBackupIcon,
  DatabaseIcon,
  DownloadIcon,
  FileArchiveIcon,
  HardDriveIcon,
  HistoryIcon,
  PlusIcon,
  ShieldAlertIcon,
  Trash2Icon,
} from "lucide-react"

import {
  createBackup as createBackupSnapshot,
  deleteBackup,
  downloadBackup,
  downloadDatabase as downloadLiveDatabase,
  listBackups,
  restoreBackup,
  type BackupRecord as ApiBackupRecord,
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

type BackupSnapshot = {
  id: number
  createdAt: string
  creator: string
  filename: string
  sizeBytes: number
  type: "manual" | "system"
  status: "verified" | "restored"
}

function formatDate(value: string) {
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

function formatBytes(bytes: number) {
  if (bytes < 1048576) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  return `${(bytes / 1048576).toFixed(1)} MB`
}

function apiBackupToSnapshot(backup: ApiBackupRecord): BackupSnapshot {
  return {
    id: backup.id,
    createdAt: backup.created_at ?? "",
    creator: backup.username ?? "System",
    filename: backup.filename,
    sizeBytes: backup.size_bytes,
    type: backup.created_by ? "manual" : "system",
    status: "verified",
  }
}

function backupErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message
  }
  return fallback
}

export function BackupRestorePage() {
  const [backups, setBackups] = React.useState<BackupSnapshot[]>([])
  const [selectedBackupId, setSelectedBackupId] = React.useState(0)
  const [pendingAction, setPendingAction] = React.useState<"restore" | "delete" | null>(null)
  const [alert, setAlert] = React.useState("Loading backup snapshot catalog from SQLite.")
  const [isLoading, setIsLoading] = React.useState(false)

  const loadBackups = React.useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await listBackups()
      const snapshots = response.backups.map(apiBackupToSnapshot)
      setBackups(snapshots)
      setSelectedBackupId((current) => current || snapshots[0]?.id || 0)
      setAlert("Backup snapshot catalog loaded from SQLite.")
    } catch (error) {
      setAlert(backupErrorMessage(error, "Unable to load backups."))
    } finally {
      setIsLoading(false)
    }
  }, [])

  React.useEffect(() => {
    void loadBackups()
  }, [loadBackups])

  const selectedBackup = backups.find((backup) => backup.id === selectedBackupId) ?? backups[0] ?? null
  const totalBytes = backups.reduce((sum, backup) => sum + backup.sizeBytes, 0)
  const latestBackup = backups[0]?.createdAt ?? null

  const metrics = [
    { label: "Total Backups", value: backups.length, hint: "Saved snapshots", icon: HistoryIcon, tone: "info" },
    { label: "Storage Used", value: formatBytes(totalBytes), hint: "Local backup folder", icon: HardDriveIcon, tone: "warning" },
    { label: "Latest Backup", value: latestBackup ? "Ready" : "None", hint: latestBackup ? formatDate(latestBackup) : "No snapshots", icon: ClockIcon, tone: "success" },
  ]

  async function createBackup() {
    try {
      const response = await createBackupSnapshot()
      if (response.backup) {
        const created = apiBackupToSnapshot(response.backup)
        setBackups((current) => [created, ...current.filter((backup) => backup.id !== created.id)])
        setSelectedBackupId(created.id)
      } else {
        await loadBackups()
      }
      setAlert(response.message)
    } catch (error) {
      setAlert(backupErrorMessage(error, "Unable to create backup."))
    }
  }

  function requestRestore(backup: BackupSnapshot) {
    setSelectedBackupId(backup.id)
    setPendingAction("restore")
    setAlert(`Restore requested for '${backup.filename}'. Confirm to apply the database snapshot and invalidate sessions.`)
  }

  function requestDelete(backup: BackupSnapshot) {
    setSelectedBackupId(backup.id)
    setPendingAction("delete")
    setAlert(`Delete requested for '${backup.filename}'. Confirm to remove this snapshot.`)
  }

  async function confirmPendingAction() {
    if (!selectedBackup || !pendingAction) {
      return
    }

    try {
      if (pendingAction === "restore") {
        const response = await restoreBackup(selectedBackup.id)
        setBackups((current) =>
          current.map((backup) => ({
            ...backup,
            status: backup.id === selectedBackup.id ? "restored" : backup.status,
          }))
        )
        setAlert(`${response.message} You may need to sign in again.`)
      } else {
        const response = await deleteBackup(selectedBackup.id)
        const nextBackups = backups.filter((backup) => backup.id !== selectedBackup.id)
        setBackups(nextBackups)
        setSelectedBackupId(nextBackups[0]?.id ?? 0)
        setAlert(response.message)
      }
    } catch (error) {
      setAlert(backupErrorMessage(error, `Unable to ${pendingAction} backup.`))
    }

    setPendingAction(null)
  }

  async function downloadSelectedBackup(backup: BackupSnapshot) {
    try {
      await downloadBackup(backup.id, backup.filename)
      setAlert(`Backup '${backup.filename}' download started.`)
    } catch (error) {
      setAlert(backupErrorMessage(error, `Unable to download '${backup.filename}'.`))
    }
  }

  async function downloadDatabase() {
    try {
      await downloadLiveDatabase()
      setAlert("Active SQLite database download started.")
    } catch (error) {
      setAlert(backupErrorMessage(error, "Unable to download active SQLite database."))
    }
  }

  return (
    <main className="smartflow-page backup-page">
      <section className="backup-hero">
        <div>
          <h1>Backup & Restore</h1>
          <p>Create database snapshots, restore from backups, or download the active SQLite file.</p>
        </div>
        <Button onClick={createBackup} disabled={isLoading}>
          <PlusIcon data-icon="inline-start" />
          {isLoading ? "Working" : "Backup Database"}
        </Button>
      </section>

      <section className="backup-metric-strip" aria-label="Backup metrics">
        {metrics.map((metric) => {
          const Icon = metric.icon
          return (
            <div key={metric.label} className={cn("backup-strip-metric", metric.tone)}>
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

      <div className={cn("backup-notice", pendingAction && "warning")}>
        {pendingAction ? <ShieldAlertIcon /> : <DatabaseBackupIcon />}
        <span>{alert}</span>
      </div>

      <section className="backup-console-grid">
        <Card className="backup-snapshots-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileArchiveIcon />
              Backup Snapshots
            </CardTitle>
            <CardDescription>View, restore, or delete saved database copies.</CardDescription>
            <CardAction>
              <Badge variant="secondary">{backups.length} snapshots</Badge>
            </CardAction>
          </CardHeader>
          <CardContent className="backup-table-shell">
            {backups.length ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Created At</TableHead>
                    <TableHead>Creator</TableHead>
                    <TableHead>Filename</TableHead>
                    <TableHead>File Size</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {backups.map((backup) => (
                    <TableRow
                      key={backup.id}
                      className={cn("backup-row", selectedBackup?.id === backup.id && "selected")}
                      onClick={() => setSelectedBackupId(backup.id)}
                    >
                      <TableCell>{formatDate(backup.createdAt)}</TableCell>
                      <TableCell>{backup.creator}</TableCell>
                      <TableCell>
                        <code className="backup-filename">{backup.filename}</code>
                      </TableCell>
                      <TableCell>{formatBytes(backup.sizeBytes)}</TableCell>
                      <TableCell>
                        <div className="backup-actions-inline">
                          <Button variant="ghost" size="sm" onClick={() => downloadSelectedBackup(backup)}>
                            <DownloadIcon data-icon="inline-start" />
                            Download
                          </Button>
                          <Button variant="outline" size="sm" onClick={() => requestRestore(backup)}>
                            <ArchiveRestoreIcon data-icon="inline-start" />
                            Restore
                          </Button>
                          <Button variant="destructive" size="sm" onClick={() => requestDelete(backup)}>
                            <Trash2Icon data-icon="inline-start" />
                            Delete
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="backup-empty-state">
                <HistoryIcon />
                <strong>No backup snapshots yet</strong>
                <span>Create your first backup using the Database Actions panel.</span>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="backup-actions-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DatabaseIcon />
              Database Actions
            </CardTitle>
            <CardDescription>Create new backups or export the live database.</CardDescription>
          </CardHeader>
          <CardContent className="backup-action-stack">
            <div className="backup-action-tile">
              <DatabaseBackupIcon />
              <div>
                <strong>Create Local Snapshot</strong>
                <span>Save a point-in-time copy of the entire database.</span>
              </div>
              <Button onClick={createBackup} disabled={isLoading}>
                <DatabaseBackupIcon data-icon="inline-start" />
                Backup Database
              </Button>
            </div>
            <div className="backup-action-tile">
              <DownloadIcon />
              <div>
                <strong>Export Active SQLite</strong>
                <span>Download the current database file to your local machine.</span>
              </div>
              <Button variant="outline" onClick={downloadDatabase} disabled={isLoading}>
                <DownloadIcon data-icon="inline-start" />
                Download SQLite DB
              </Button>
            </div>
            {pendingAction && selectedBackup ? (
              <div className="backup-confirm-panel">
                <ShieldAlertIcon />
                <span>
                  Confirm {pendingAction} for <strong>{selectedBackup.filename}</strong>
                </span>
                <Button variant="outline" onClick={() => setPendingAction(null)}>
                  Cancel
                </Button>
                <Button variant={pendingAction === "delete" ? "destructive" : "default"} onClick={confirmPendingAction}>
                  Confirm
                </Button>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </section>
    </main>
  )
}
