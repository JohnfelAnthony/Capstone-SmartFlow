import * as React from "react"
import { CheckIcon, CircleIcon, EyeIcon, EyeOffIcon, UserRoundIcon } from "lucide-react"
import { changePassword, type CurrentUser } from "@/api/auth"
import { applyTheme, clearRandomPalette, getInitialTheme, type ThemeMode } from "@/lib/appearance"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
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

function ProfileCard({ user }: { user: CurrentUser }) {
  const details = [
    ["Username", user.username],
    ["Email", user.email || "Not supplied"],
    ["Role", user.role],
    ["Status", user.status],
  ]
  return <Card><CardHeader><CardTitle>Account</CardTitle><CardDescription>Profile details are managed by your administrator.</CardDescription></CardHeader>
    <CardContent className="flex flex-col gap-5">
      <div className="flex items-center gap-4">
        <Avatar className="size-14"><AvatarFallback><UserRoundIcon className="size-7 text-muted-foreground" /></AvatarFallback></Avatar>
        <div className="min-w-0"><p className="truncate text-lg font-semibold">{user.full_name}</p>
          <div className="mt-1 flex flex-wrap gap-2"><Badge variant="secondary">{user.role}</Badge><Badge variant="outline">{user.status}</Badge></div></div>
      </div>
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-6 gap-y-3 border-t pt-4 text-sm">
        {details.map(([label, value]) => <React.Fragment key={label}><dt className="text-muted-foreground">{label}</dt><dd className="break-all">{value}</dd></React.Fragment>)}
      </dl>
    </CardContent></Card>
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
  function save() {
    try {
      clearRandomPalette()
      window.localStorage.setItem("smartflow-theme", theme)
      applyTheme(theme)
      window.dispatchEvent(new Event("smartflow-appearance"))
      setNotice("Theme saved on this browser.")
    } catch {
      setNotice("This browser could not save preferences. Check its local storage settings.")
    }
  }
  return <Card><CardHeader><CardTitle>Appearance</CardTitle><CardDescription>Theme applies to this browser.</CardDescription></CardHeader>
    <CardContent><FieldGroup>
      {notice && <Alert><AlertDescription role="status">{notice}</AlertDescription></Alert>}
      <Field><FieldLabel>Theme</FieldLabel><ToggleGroup value={[theme]} onValueChange={(values) => values[0] && setTheme(values[0] as ThemeMode)} aria-label="Theme"><ToggleGroupItem value="dark">Dark</ToggleGroupItem><ToggleGroupItem value="light">Light</ToggleGroupItem></ToggleGroup><FieldDescription>Saving restores the standard palette if Randomize was used.</FieldDescription></Field>
      <Button onClick={save}>Save preferences</Button>
    </FieldGroup></CardContent></Card>
}

export function SettingsPage({ user, onPasswordChanged }: {
  user: CurrentUser; onPasswordChanged: () => void
}) {
  return <main className="flex flex-col gap-6 p-4 lg:p-6">
    <div><h1 className="text-2xl font-semibold">Settings</h1><p className="text-muted-foreground">Your account, password and display preferences.</p></div>
    <div className="grid items-start gap-6 lg:grid-cols-2">
      <div className="flex flex-col gap-6"><ProfileCard user={user} /><PreferencesCard /></div>
      <PasswordCard mustChange={user.must_change_password} onChanged={onPasswordChanged} />
    </div>
  </main>
}
