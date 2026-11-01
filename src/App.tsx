import * as React from "react"

import {
  ApiError,
} from "@/api/client"
import {
  getCurrentUser,
  type CurrentUser,
  login,
  logout,
  registerAccount,
} from "@/api/auth"
import { AppSidebar } from "@/components/app-sidebar"
const AuditLogsPage = React.lazy(() => import("@/components/audit-logs-page").then(module => ({ default: module.AuditLogsPage })))
import { LoginPage, RegisterPage } from "@/components/auth-pages"
const BackupRestorePage = React.lazy(() => import("@/components/backup-restore-page").then(module => ({ default: module.BackupRestorePage })))
const CompareRunsPage = React.lazy(() => import("@/components/compare-runs-page").then(module => ({ default: module.CompareRunsPage })))
const CalibrationValidationPage = React.lazy(() => import("@/components/calibration-validation-page").then(module => ({ default: module.CalibrationValidationPage })))
const DashboardPage = React.lazy(() => import("@/components/dashboard-page").then(module => ({ default: module.DashboardPage })))
const HelpAboutPage = React.lazy(() => import("@/components/help-about-page").then(module => ({ default: module.HelpAboutPage })))
const RoleAccessControlPage = React.lazy(() => import("@/components/role-access-control-page").then(module => ({ default: module.RoleAccessControlPage })))
const RLTrainingPage = React.lazy(() => import("@/components/rl-training-page").then(module => ({ default: module.RLTrainingPage })))
const RunsReportsPage = React.lazy(() => import("@/components/runs-reports-page").then(module => ({ default: module.RunsReportsPage })))
const ScenariosPage = React.lazy(() => import("@/components/scenarios-page").then(module => ({ default: module.ScenariosPage })))
const SettingsPage = React.lazy(() => import("@/components/settings-page").then(module => ({ default: module.SettingsPage })))
import { SiteHeader } from "@/components/site-header"
const UserManagementPage = React.lazy(() => import("@/components/user-management-page").then(module => ({ default: module.UserManagementPage })))
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"

export default function App() {
  const [activePage, setActivePage] = React.useState("Login")
  const [currentUser, setCurrentUser] = React.useState<CurrentUser | null>(null)
  const [isSessionLoading, setIsSessionLoading] = React.useState(true)
  const pageTitleByPage: Record<string, string> = {
    Dashboard: "Live Simulation View",
    Scenarios: "Scenario Library",
    "Calibration & Validation": "Calibration & Validation",
    Settings: "Settings",
    "RL Training": "RL Training",
    "Runs & Reports": "Runs & Reports",
    "Compare Runs": "Compare Runs",
    "User Management": "User Management",
    "Role & Access Control": "Role & Access Control",
    "Audit Logs": "Audit Logs",
    "Backup & Restore": "Backup & Restore",
    Help: "Help & Documentation",
  }
  const pageTitle = pageTitleByPage[activePage] ?? activePage
  const can = (page: string, action: string) => Boolean(currentUser && (
    currentUser.role.toLowerCase() === "admin" ||
    currentUser.permissions.some((permission) => permission.page === page && permission.action === action)
  ))

  React.useEffect(() => {
    let isMounted = true

    getCurrentUser()
      .then((user) => {
        if (!isMounted) return
        setCurrentUser(user)
        setActivePage("Dashboard")
      })
      .catch((error) => {
        if (!isMounted) return
        if (!(error instanceof ApiError) || error.status !== 401) {
          console.warn("Unable to restore SMARTFLOW session.", error)
        }
        setCurrentUser(null)
        setActivePage("Login")
      })
      .finally(() => {
        if (isMounted) {
          setIsSessionLoading(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [])

  async function handleLogin(username: string, password: string) {
    const response = await login(username, password)
    setCurrentUser(response.user)
    setActivePage(response.landing_path === "/scenarios" ? "Scenarios" : "Dashboard")
  }

  async function handleRegister(payload: {
    full_name: string
    username: string
    email?: string
    password: string
    confirm_password: string
  }) {
    return registerAccount(payload)
  }

  async function handleLogout() {
    try {
      await logout()
    } finally {
      setCurrentUser(null)
      setActivePage("Login")
    }
  }

  function navigate(page: string) {
    setActivePage(page)
  }

  if (isSessionLoading) {
    return (
      <div className="auth-page auth-page-login">
        <div className="auth-session-loading">Loading SmartFlow...</div>
      </div>
    )
  }

  if (!currentUser && activePage === "Login") {
    return <LoginPage onNavigate={setActivePage} onLogin={handleLogin} />
  }

  if (!currentUser && activePage === "Register") {
    return <RegisterPage onNavigate={setActivePage} onRegister={handleRegister} />
  }

  return (
    <TooltipProvider>
      <SidebarProvider
        style={
          {
            "--sidebar-width": "calc(var(--spacing) * 72)",
            "--header-height": "calc(var(--spacing) * 12)",
          } as React.CSSProperties
        }
      >
        <AppSidebar
          activeItem={activePage}
          onSelectItem={navigate}
          currentUser={currentUser}
          onOpenAccount={() => navigate("Settings")}
          onLogout={handleLogout}
          variant="inset"
        />
        <SidebarInset className="min-w-0">
          <SiteHeader
            title={pageTitle}
          />
          <div className="flex min-h-0 flex-1 flex-col">
            <React.Suspense fallback={<p role="status" className="p-6">Loading page…</p>}>
            {activePage === "Scenarios" ? (
              <ScenariosPage onOpenDashboard={() => navigate("Dashboard")}
                permissions={{ create: can("scenarios", "create"), edit: can("scenarios", "edit"),
                  run: can("simulation", "run") }} />
            ) : activePage === "Calibration & Validation" ? (
              <CalibrationValidationPage canEdit={can("scenarios", "edit")}
                canExport={can("runs-reports", "export")} onOpenScenarios={() => navigate("Scenarios")} />
            ) : activePage === "Settings" ? (
              <SettingsPage user={currentUser!}
                onPasswordChanged={() => { getCurrentUser().then(setCurrentUser).catch(() => undefined) }} />
            ) : activePage === "RL Training" ? (
              <RLTrainingPage currentUserId={currentUser!.id} isAdmin={currentUser!.role.toLowerCase() === "admin"}
                canRunTraining={currentUser!.role.toLowerCase() === "admin" || currentUser!.permissions.some((permission) => permission.page === "rl-training" && permission.action === "run")} />
            ) : activePage === "Runs & Reports" ? (
              <RunsReportsPage onOpenDashboard={() => navigate("Dashboard")}
                onOpenResearch={can("scenarios", "view") && can("runs-reports", "view") ? () => navigate("Calibration & Validation") : undefined}
                onOpenCompare={can("compare", "view") ? () => navigate("Compare Runs") : undefined} />
            ) : activePage === "Compare Runs" ? (
              <CompareRunsPage />
            ) : activePage === "User Management" ? (
              <UserManagementPage />
            ) : activePage === "Role & Access Control" ? (
              <RoleAccessControlPage />
            ) : activePage === "Audit Logs" ? (
              <AuditLogsPage />
            ) : activePage === "Backup & Restore" ? (
              <BackupRestorePage />
            ) : activePage === "Help" ? (
              <HelpAboutPage />
            ) : (
              <DashboardPage
                currentUserId={currentUser!.id}
                isAdmin={currentUser!.role.toLowerCase() === "admin"}
                canRunSimulation={currentUser!.role.toLowerCase() === "admin" || currentUser!.permissions.some((permission) => permission.page === "simulation" && permission.action === "run")}
              />
            )}
            </React.Suspense>
          </div>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}
