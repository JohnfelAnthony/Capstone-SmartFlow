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
import { DashboardPage } from "@/components/dashboard-page"
import { HelpAboutPage } from "@/components/help-about-page"
import { RoleAccessControlPage } from "@/components/role-access-control-page"
import { RLTrainingPage } from "@/components/rl-training-page"
import { RunsReportsPage } from "@/components/runs-reports-page"
import { ScenariosPage } from "@/components/scenarios-page"
import { SiteHeader } from "@/components/site-header"
import { UserManagementPage } from "@/components/user-management-page"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"
import type { VisualizationMode } from "@/simulation/visualization-mode"

export default function App() {
  const [activePage, setActivePage] = React.useState("Login")
  const [currentUser, setCurrentUser] = React.useState<CurrentUser | null>(null)
  const [isSessionLoading, setIsSessionLoading] = React.useState(true)
  const [visualizationMode, setVisualizationMode] = React.useState<VisualizationMode>("2d")
  const pageTitleByPage: Record<string, string> = {
    Dashboard: "Live Simulation View",
    Scenarios: "Scenario Library",
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
          onSelectItem={setActivePage}
          currentUser={currentUser}
          onChangePassword={() => setActivePage("Change Password")}
          onLogout={handleLogout}
          variant="inset"
        />
        <SidebarInset>
          <SiteHeader
            title={pageTitle}
            showVizToggle={activePage === "Dashboard"}
            visualizationMode={visualizationMode}
            onVisualizationModeChange={setVisualizationMode}
          />
          <div className="flex min-h-0 flex-1 flex-col">
            {activePage === "Scenarios" ? (
              <ScenariosPage onOpenDashboard={() => setActivePage("Dashboard")} />
            ) : activePage === "RL Training" ? (
              <RLTrainingPage />
            ) : activePage === "Runs & Reports" ? (
              <RunsReportsPage onOpenDashboard={() => setActivePage("Dashboard")} />
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
                onCancel={() => setActivePage("Dashboard")}
                onChangePassword={handleChangePassword}
              />
            ) : activePage === "Help" ? (
              <HelpAboutPage />
            ) : (
              <DashboardPage
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
