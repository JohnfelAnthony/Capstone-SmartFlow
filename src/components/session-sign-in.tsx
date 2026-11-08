import * as React from "react"
import { login, type CurrentUser } from "@/api/auth"
import { SESSION_EXPIRED_EVENT } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet"

export function SessionSignIn({ user, onSignedIn, onLogout }: {
  user: CurrentUser; onSignedIn: (user: CurrentUser) => void; onLogout: () => void
}) {
  const [open, setOpen] = React.useState(false)
  const [password, setPassword] = React.useState("")
  const [error, setError] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  React.useEffect(() => {
    const expired = () => { setOpen(true); setPassword(""); setError("") }
    window.addEventListener(SESSION_EXPIRED_EVENT, expired)
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expired)
  }, [])
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError("")
    try {
      const result = await login(user.username, password)
      setPassword("")
      onSignedIn(result.user)
      setOpen(false)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Unable to sign in.")
    } finally { setBusy(false) }
  }
  return <Sheet open={open}>
    <SheetContent showCloseButton={false}>
      <SheetHeader>
        <SheetTitle>Sign in to continue</SheetTitle>
        <SheetDescription>Your session ended. Your comparison stays in place; playback is paused.</SheetDescription>
      </SheetHeader>
      <form onSubmit={submit} className="flex flex-col gap-4 px-4">
        <FieldGroup>
          <Field><FieldLabel htmlFor="session-username">Username</FieldLabel>
            <Input id="session-username" autoComplete="username" value={user.username} readOnly /></Field>
          <Field><FieldLabel htmlFor="session-password">Password</FieldLabel>
            <Input id="session-password" type="password" autoComplete="current-password" value={password}
              onChange={(event) => setPassword(event.target.value)} required /></Field>
        </FieldGroup>
        {error ? <p role="alert" className="text-destructive">{error}</p> : null}
        <Button type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</Button>
        <Button type="button" variant="outline" disabled={busy} onClick={onLogout}>Sign out</Button>
      </form>
    </SheetContent>
  </Sheet>
}
