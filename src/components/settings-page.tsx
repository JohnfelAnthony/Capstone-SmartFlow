import { toast } from "sonner"
import * as React from "react"
import { BadgeCheckIcon, CalendarDaysIcon, CheckIcon, CircleIcon, ExternalLinkIcon, EyeIcon, EyeOffIcon, ShieldCheckIcon, UserRoundIcon } from "lucide-react"
import "@/styles/admin-user-management.css"
import { openFieldObserver } from "@/api/admin"
import { changePassword, type CurrentUser } from "@/api/auth"
import { parseServerTimestamp } from "@/lib/display-format"
import { applyTheme, clearRandomPalette, getInitialTheme, type ThemeMode } from "@/lib/appearance"
import { writePreference } from "@/lib/local-preference-store"
import { NetworkRevisionReviewCard } from "@/components/network-revision-review-card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

// Mirrors auth.validate_password_strength; the server stays the authority.
const MINIMUM_PASSWORD_LENGTH = 8

function passwordRules(password: string, confirmation: string) {
  return [
    { label: `At least ${MINIMUM_PASSWORD_LENGTH} characters`, met: password.length >= MINIMUM_PASSWORD_LENGTH },
    { label: "An uppercase letter", met: /[A-Z]/.test(password) },
    { label: "A lowercase letter", met: /[a-z]/.test(password) },
    { label: "A digit", met: /\d/.test(password) },
    { label: "Matches the confirmation", met: password.length > 0 && password === confirmation },
  ]
}

function AccountStrip({ user }: { user: CurrentUser }) {
  const created = parseServerTimestamp(user.created_at)
  const metrics = [
    { label: "User", value: user.username, hint: user.full_name, icon: UserRoundIcon, tone: "info" },
    { label: "Created", value: created ? created.toLocaleDateString("en", { month: "short", day: "numeric", year: "numeric" }) : "Unknown",
      hint: created ? `at ${created.toLocaleTimeString("en", { hour: "numeric", minute: "2-digit" })}` : "Not recorded", icon: CalendarDaysIcon, tone: "success" },
    { label: "Role", value: user.role, hint: user.email || "No email on file", icon: ShieldCheckIcon, tone: "warning" },
    { label: "Status", value: user.status, hint: user.must_change_password ? "Change your password" : "Account in good standing", icon: BadgeCheckIcon, tone: user.must_change_password ? "danger" : "info" },
  ]
  return <section className="audit-metric-strip" aria-label="Your account">
    {metrics.map(({ label, value, hint, icon: Icon, tone }) => <div key={label} className={`audit-strip-metric ${tone}`}>
      <Icon aria-hidden="true" className="shrink-0" /><div className="min-w-0"><div className="flex-wrap"><strong className={`whitespace-nowrap ${label === "User" ? "" : "capitalize"}`}>{value}</strong><span>{label}</span></div><small>{hint}</small></div>
    </div>)}
  </section>
}

function PasswordCard({ mustChange, onChanged }: { mustChange: boolean; onChanged: () => void }) {
  const [currentPassword, setCurrentPassword] = React.useState("")
  const [newPassword, setNewPassword] = React.useState("")
  const [confirmPassword, setConfirmPassword] = React.useState("")
  const [showPasswords, setShowPasswords] = React.useState(false)
  const [error, setError] = React.useState("")
  const [success, setSuccess] = React.useState("")
  const [isSubmitting, setIsSubmitting] = React.useState(false)
  const rules = passwordRules(newPassword, confirmPassword)
  const isReady = Boolean(currentPassword) && rules.every((rule) => rule.met)
  const inputType = showPasswords ? "text" : "password"

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")
    setSuccess("")
    if (!isReady) {
      setError("Enter your current password and a new password that meets every requirement.")
      return
    }
    setIsSubmitting(true)
    try {
      const response = await changePassword({ current_password: currentPassword, new_password: newPassword, confirm_password: confirmPassword })
      setSuccess(response.message)
      toast.success("Password updated")
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword(""); setShowPasswords(false)
      onChanged()
    } catch (changeError) {
      setError(changeError instanceof Error ? changeError.message : "Password update failed.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return <Card><CardHeader><CardTitle>Change password</CardTitle><CardDescription>Confirm your current password, then choose a new one. You stay signed in.</CardDescription></CardHeader>
    <CardContent><form onSubmit={submit} noValidate><FieldGroup>
      {mustChange && <Alert><AlertDescription>Change your initial password before using this account for study work.</AlertDescription></Alert>}
      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
      {success && <Alert><AlertDescription>{success}</AlertDescription></Alert>}
      <Field><FieldLabel htmlFor="settings-current-password">Current password</FieldLabel>
        <Input id="settings-current-password" type={inputType} autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></Field>
      <Field><FieldLabel htmlFor="settings-new-password">New password</FieldLabel>
        <Input id="settings-new-password" type={inputType} autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></Field>
      <Field><FieldLabel htmlFor="settings-confirm-password">Confirm new password</FieldLabel>
        <Input id="settings-confirm-password" type={inputType} autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
        <ul className="mt-1 flex flex-col gap-1 text-sm text-muted-foreground" aria-label="Password requirements">
          {rules.map((rule) => <li key={rule.label} className={`flex items-center gap-2 ${rule.met ? "text-foreground" : ""}`}>
            {rule.met ? <CheckIcon className="size-3.5 text-primary" /> : <CircleIcon className="size-3.5" />}{rule.label}</li>)}
        </ul></Field>
      <div className="flex flex-wrap justify-between gap-2">
        <Button type="button" variant="ghost" aria-pressed={showPasswords} onClick={() => setShowPasswords((visible) => !visible)}>
          {showPasswords ? <EyeOffIcon /> : <EyeIcon />}{showPasswords ? "Hide passwords" : "Show passwords"}</Button>
        <Button type="submit" disabled={isSubmitting || !isReady}>{isSubmitting ? "Updating..." : "Update password"}</Button>
      </div>
    </FieldGroup></form></CardContent></Card>
}

function PreferencesCard() {
  const [theme, setTheme] = React.useState<ThemeMode>(getInitialTheme)
  const [notice, setNotice] = React.useState("")
  async function save() {
    try {
      await clearRandomPalette()
      await writePreference("smartflow-theme", theme)
      applyTheme(theme)
      window.dispatchEvent(new Event("smartflow-appearance"))
      setNotice(import.meta.env.VITE_SMARTFLOW_DESKTOP === "1" ? "Theme saved on this computer." : "Theme saved on this browser.")
      toast.success("Preferences saved")
    } catch {
      setNotice("Could not save preferences. Please try again.")
    }
  }
  return <Card><CardHeader><CardTitle>Appearance</CardTitle><CardDescription>{import.meta.env.VITE_SMARTFLOW_DESKTOP === "1" ? "Theme is saved on this computer." : "Theme applies to this browser."}</CardDescription></CardHeader>
    <CardContent><FieldGroup>
      {notice && <Alert><AlertDescription role="status">{notice}</AlertDescription></Alert>}
      <Field><FieldLabel>Theme</FieldLabel><ToggleGroup value={[theme]} onValueChange={(values) => values[0] && setTheme(values[0] as ThemeMode)} aria-label="Theme"><ToggleGroupItem value="dark">Dark</ToggleGroupItem><ToggleGroupItem value="light">Light</ToggleGroupItem></ToggleGroup><FieldDescription>Saving restores the standard palette if Randomize was used.</FieldDescription></Field>
      <Button onClick={save}>Save preferences</Button>
    </FieldGroup></CardContent></Card>
}

function ToolsCard() {
  const [notice, setNotice] = React.useState("")
  const [isOpening, setIsOpening] = React.useState(false)
  async function open() {
    setIsOpening(true)
    try {
      setNotice((await openFieldObserver()).message)
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Unable to start Field Observer.")
    } finally {
      setIsOpening(false)
    }
  }
  return <Card><CardHeader><CardTitle>Tools</CardTitle><CardDescription>Field Observer counts vehicles and pedestrians in your intersection videos. It opens on this computer in a new browser tab.</CardDescription></CardHeader>
    <CardContent className="flex flex-col gap-3">
      {notice && <Alert><AlertDescription role="status">{notice}</AlertDescription></Alert>}
      <Button className="self-start" onClick={() => void open()} disabled={isOpening}><ExternalLinkIcon data-icon="inline-start" />{isOpening ? "Starting..." : "Open Field Observer"}</Button>
    </CardContent></Card>
}

export function SettingsPage({ user, onPasswordChanged }: {
  user: CurrentUser; onPasswordChanged: () => void
}) {
  return <main className="flex flex-col gap-6 p-4 lg:p-6">
    <div><h1 className="text-2xl font-semibold">Settings</h1><p className="text-muted-foreground">Your account, password and display preferences.</p></div>
    <AccountStrip user={user} />
    <div className="grid items-start gap-6 lg:grid-cols-2">
      <div className="flex flex-col gap-6"><PreferencesCard />{user.role.toLowerCase() === "admin" && <>{import.meta.env.VITE_SMARTFLOW_DESKTOP !== "1" && <ToolsCard />}<NetworkRevisionReviewCard /></>}</div>
      <div className="flex flex-col gap-6"><PasswordCard mustChange={user.must_change_password} onChanged={onPasswordChanged} /></div>
    </div>
  </main>
}
