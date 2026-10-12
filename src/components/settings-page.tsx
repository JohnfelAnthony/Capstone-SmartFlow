import * as React from "react"
import type { CurrentUser } from "@/api/auth"
import { applyTheme, clearRandomPalette, getInitialTheme, type ThemeMode } from "@/lib/appearance"
import { defaultVisualization, saveDefaultVisualization } from "@/lib/preferences"
import type { VisualizationMode } from "@/simulation/visualization-mode"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

export function SettingsPage({ user, onChangePassword, onVisualizationChange }: {
  user: CurrentUser; onChangePassword: () => void; onVisualizationChange: (mode: VisualizationMode) => void
}) {
  const [theme, setTheme] = React.useState<ThemeMode>(getInitialTheme)
  const [view, setView] = React.useState(() => defaultVisualization(user.id))
  const [notice, setNotice] = React.useState("")
  function save() {
    try {
      clearRandomPalette()
      window.localStorage.setItem("smartflow-theme", theme)
      saveDefaultVisualization(user.id, view)
      applyTheme(theme)
      window.dispatchEvent(new Event("smartflow-appearance"))
      onVisualizationChange(view)
      setNotice("Preferences saved on this browser. The default view will be restored when you sign in.")
    } catch {
      setNotice("This browser could not save preferences. Check its local storage settings.")
    }
  }
  return <main className="flex flex-col gap-6 p-4 lg:p-6">
    <div><h1 className="text-2xl font-semibold">Settings</h1><p className="text-muted-foreground">Your account and display preferences.</p></div>
    {notice && <Alert><AlertDescription role="status">{notice}</AlertDescription></Alert>}
    <div className="grid gap-6 lg:grid-cols-2">
      <Card><CardHeader><CardTitle>Account</CardTitle><CardDescription>Account details are managed by your administrator.</CardDescription></CardHeader>
        <CardContent className="flex flex-col gap-4"><dl className="grid grid-cols-2 gap-3"><dt>Name</dt><dd>{user.full_name}</dd><dt>Username</dt><dd>{user.username}</dd><dt>Email</dt><dd className="break-all">{user.email || "Not supplied"}</dd><dt>Role</dt><dd><Badge variant="secondary">{user.role}</Badge></dd><dt>Status</dt><dd>{user.status}</dd></dl>
          {user.must_change_password && <Alert><AlertDescription>Change your initial password before using this account for study work.</AlertDescription></Alert>}
          <Button variant="outline" onClick={onChangePassword}>Change password</Button></CardContent></Card>
      <Card><CardHeader><CardTitle>Appearance and simulation view</CardTitle><CardDescription>Theme applies to this browser. Default visualization is saved for your account on this browser.</CardDescription></CardHeader>
        <CardContent><FieldGroup>
          <Field><FieldLabel>Theme</FieldLabel><ToggleGroup value={[theme]} onValueChange={(values) => values[0] && setTheme(values[0] as ThemeMode)} aria-label="Theme"><ToggleGroupItem value="dark">Dark</ToggleGroupItem><ToggleGroupItem value="light">Light</ToggleGroupItem></ToggleGroup><FieldDescription>Saving restores the standard palette if Randomize was used.</FieldDescription></Field>
          <Field><FieldLabel>Default simulation view</FieldLabel><ToggleGroup value={[view]} onValueChange={(values) => values[0] && setView(values[0] as VisualizationMode)} aria-label="Default simulation view"><ToggleGroupItem value="3d">3D</ToggleGroupItem><ToggleGroupItem value="2d">2D</ToggleGroupItem></ToggleGroup></Field>
          <Button onClick={save}>Save preferences</Button>
        </FieldGroup></CardContent></Card>
    </div>
  </main>
}
