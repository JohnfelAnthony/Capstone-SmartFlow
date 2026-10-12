import * as React from "react"

import {
  ApiError,
} from "@/api/client"
import {
  getCurrentUser,
  changePassword,
  type CurrentUser,
  login,
  logout,
  registerAccount,
} from "@/api/auth"
import { AppSidebar } from "@/components/app-sidebar"
import { AuditLogsPage } from "@/components/audit-logs-page"
import { ChangePasswordPage, LoginPage, RegisterPage } from "@/components/auth-pages"
import { BackupRestorePage } from "@/components/backup-restore-page"
import { CompareRunsPage } from "@/components/compare-runs-page"
import { CalibrationValidationPage } from "@/components/calibration-validation-page"
import { DashboardPage } from "@/components/dashboard-page"
import { HelpAboutPage } from "@/components/help-about-page"
import { RoleAccessControlPage } from "@/components/role-access-control-page"
import { RLTrainingPage } from "@/components/rl-training-page"
import { RunsReportsPage } from "@/components/runs-reports-page"
import { ScenariosPage } from "@/components/scenarios-page"
import { SearchPage } from "@/components/search-page"
import { SettingsPage } from "@/components/settings-page"
import { SiteHeader } from "@/components/site-header"
import { UserManagementPage } from "@/components/user-management-page"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"
import type { VisualizationMode } from "@/simulation/visualization-mode"
import type { SearchResult } from "@/api/research"
import { defaultVisualization } from "@/lib/preferences"

export default function App() {
  const [activePage, setActivePage] = React.useState("Login")
  const [currentUser, setCurrentUser] = React.useState<CurrentUser | null>(null)
  const [isSessionLoading, setIsSessionLoading] = React.useState(true)
  const [visualizationMode, setVisualizationMode] = React.useState<VisualizationMode>("3d")
  const [selection, setSelection] = React.useState<SearchResult | null>(null)
  const [passwordReturnPage, setPasswordReturnPage] = React.useState("Dashboard")
  const pageTitleByPage: Record<string, string> = {
    Dashboard: "Live Simulation View",
    Scenarios: "Scenario Library",
    "Calibration & Validation": "Calibration & Validation",
    Search: "Workspace Search",
    Settings: "Settings",
    "RL Training": "RL Training",
    "Runs & Reports": "Runs & Reports",
    "Compare Runs": "Compare Runs",
    "User Management": "User Management",
    "Role & Access Control": "Role & Access Control",
    "Audit Logs": "Audit Logs",
    "Backup & Restore": "Backup & Restore",
    "Change Password": "Change Password",
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
        setVisualizationMode(defaultVisualization(user.id))
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
    setSelection(null)
    setVisualizationMode(defaultVisualization(response.user.id))
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

  async function handleChangePassword(payload: {
    current_password: string
    new_password: string
    confirm_password: string
  }) {
    return changePassword(payload)
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
    setSelection(null)
    setActivePage(page)
  }

  function openPassword() {
    setPasswordReturnPage(activePage)
    setActivePage("Change Password")
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
          onChangePassword={openPassword}
          onLogout={handleLogout}
          variant="inset"
        />
        <SidebarInset className="min-w-0">
          <SiteHeader
            title={pageTitle}
            showVizToggle={activePage === "Dashboard"}
            visualizationMode={visualizationMode}
            onVisualizationModeChange={setVisualizationMode}
          />
          <div className="flex min-h-0 flex-1 flex-col">
            {activePage === "Scenarios" ? (
              <ScenariosPage initialScenarioId={selection?.id} onOpenDashboard={() => navigate("Dashboard")}
                permissions={{ create: can("scenarios", "create"), edit: can("scenarios", "edit"),
                  run: can("simulation", "run") }} />
            ) : activePage === "Calibration & Validation" ? (
              <CalibrationValidationPage initialRecordId={selection?.id} canEdit={can("scenarios", "edit")}
                canExport={can("runs-reports", "export")} onOpenScenarios={() => navigate("Scenarios")} />
            ) : activePage === "Settings" ? (
              <SettingsPage user={currentUser!} onChangePassword={openPassword} onVisualizationChange={setVisualizationMode} />
            ) : activePage === "Search" ? (
              <SearchPage onOpen={(result) => { setSelection(result); setActivePage(result.page) }} />
            ) : activePage === "RL Training" ? (
              <RLTrainingPage initialModelId={selection?.id} currentUserId={currentUser!.id} isAdmin={currentUser!.role.toLowerCase() === "admin"}
                canRunTraining={currentUser!.role.toLowerCase() === "admin" || currentUser!.permissions.some((permission) => permission.page === "rl-training" && permission.action === "run")} />
            ) : activePage === "Runs & Reports" ? (
              <RunsReportsPage initialRunId={selection?.id} onOpenDashboard={() => navigate("Dashboard")} />
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
            ) : activePage === "Change Password" ? (
              <ChangePasswordPage
                onCancel={() => setActivePage(passwordReturnPage)}
                onChangePassword={handleChangePassword}
              />
            ) : activePage === "Help" ? (
              <HelpAboutPage />
            ) : (
              <DashboardPage
                currentUserId={currentUser!.id}
                isAdmin={currentUser!.role.toLowerCase() === "admin"}
                canRunSimulation={currentUser!.role.toLowerCase() === "admin" || currentUser!.permissions.some((permission) => permission.page === "simulation" && permission.action === "run")}
                visualizationMode={visualizationMode}
                onVisualizationModeChange={setVisualizationMode}
              />
            )}
          </div>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}
