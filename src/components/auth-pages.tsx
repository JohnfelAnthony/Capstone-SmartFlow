import * as React from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

type AuthPageProps = {
  onNavigate: (page: "Login" | "Register") => void
}

type LoginPageProps = AuthPageProps & {
  onLogin: (username: string, password: string) => Promise<void>
}

type RegisterPageProps = AuthPageProps & {
  onRegister: (payload: {
    full_name: string
    username: string
    email?: string
    password: string
    confirm_password: string
  }) => Promise<{ message: string }>
}

type ChangePasswordPageProps = {
  onCancel: () => void
  onChangePassword: (payload: {
    current_password: string
    new_password: string
    confirm_password: string
  }) => Promise<{ message: string }>
}

type AuthFieldProps = {
  id: string
  label: string
  placeholder: string
  type?: string
  autoComplete?: string
  hint?: string
  value?: string
  onChange?: (value: string) => void
}

function AuthField({
  id,
  label,
  placeholder,
  type = "text",
  autoComplete,
  hint,
  value,
  onChange,
}: AuthFieldProps) {
  return (
    <div className="auth-field form-group">
      <label htmlFor={id}>{label}</label>
      <div className="auth-field-shell">
        <Input
          id={id}
          type={type}
          placeholder={placeholder}
          autoComplete={autoComplete}
          value={value}
          onChange={(event) => onChange?.(event.target.value)}
          className="input-field"
        />
      </div>
      {hint ? <div className="auth-field-hint">{hint}</div> : null}
    </div>
  )
}

function AuthVisualPanel({
  subline,
  kicker,
  title,
  description,
  rlStatus,
}: {
  subline: string
  kicker: string
  title: string
  description: string
  rlStatus: string
}) {
  return (
    <section className="auth-visual-panel">
      <div className="auth-visual-nav">
        <div className="auth-brand-lockup">
          <img src="/logo.svg" className="auth-brand-mark" alt="SMARTFLOW" />
          <div>
            <span className="auth-brand-name">SMARTFLOW</span>
            <span className="auth-brand-subline">{subline}</span>
          </div>
        </div>
      </div>

      <div className="auth-traffic-scene">
        <div className="scene-grid" />
        <div className="scene-road scene-road-east-west" />
        <div className="scene-road scene-road-north-south" />
        <div className="scene-road scene-road-diagonal" />
        <div className="scene-intersection-core" />
        <div className="scene-crosswalk scene-crosswalk-north" />
        <div className="scene-crosswalk scene-crosswalk-east" />
        <div className="scene-car scene-car-green" />
        <div className="scene-car scene-car-amber" />
        <div className="scene-car scene-car-white" />
        <div className="scene-signal scene-signal-a" />
        <div className="scene-signal scene-signal-b" />
        <div className="scene-pulse scene-pulse-one" />
        <div className="scene-pulse scene-pulse-two" />
      </div>

      <div className="auth-visual-copy">
        <p className="auth-kicker">{kicker}</p>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>

      <div className="auth-proof-row auth-proof-row-inline">
        <div className="auth-proof-inline-item">
          <span>SUMO</span>
          <strong>Connected</strong>
        </div>
        <div className="auth-proof-inline-item">
          <span>TraCI</span>
          <strong>Live bridge</strong>
        </div>
        <div className="auth-proof-inline-item">
          <span>RL</span>
          <strong>{rlStatus}</strong>
        </div>
      </div>
    </section>
  )
}

function AuthSection({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <div className="auth-form-section">
      <div className="auth-section-label">{title}</div>
      <div className="auth-section-fields">{children}</div>
    </div>
  )
}

export function LoginPage({ onNavigate, onLogin }: LoginPageProps) {
  const [username, setUsername] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [error, setError] = React.useState("")
  const [isSubmitting, setIsSubmitting] = React.useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!username.trim() || !password) {
      setError("Please enter both username and password.")
      return
    }

    setIsSubmitting(true)
    setError("")
    try {
      await onLogin(username, password)
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "Invalid username or password.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="auth-page auth-page-login">
      <div className="auth-shell auth-shell-login">
        <AuthVisualPanel
          subline="Traffic Intelligence"
          kicker="Tagum City main intersection"
          title="Coordinate live SUMO traffic with confidence."
          description="Monitor queues, signal phases, pedestrians, and emergency priority from one research-grade control room."
          rlStatus="Planning"
        />

        <section className="auth-form-panel">
          <div className="auth-form-card">
            <div className="auth-form-header">
              <div className="auth-form-eyebrow">Secure access</div>
              <h1 className="auth-form-title">Welcome back</h1>
              <p className="auth-form-description">
                Sign in to continue managing the SmartFlow simulation dashboard.
              </p>
            </div>

            <form className="auth-form-content" onSubmit={handleSubmit}>
              <div className={error ? "alert alert-error" : "alert alert-error hidden"}>
                {error}
              </div>
              <AuthField
                id="username-input"
                label="Username"
                placeholder="Enter your username"
                autoComplete="username"
                hint="Use the account assigned to your SMARTFLOW workspace."
                value={username}
                onChange={setUsername}
              />
              <AuthField
                id="password-input"
                label="Password"
                placeholder="Enter your password"
                type="password"
                autoComplete="current-password"
                hint="Password is case-sensitive."
                value={password}
                onChange={setPassword}
              />
              <Button className="btn btn-primary btn-full" type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Signing In..." : "Sign In"}
              </Button>
              <div className="auth-footer">
                <span>Don&apos;t have an account? </span>
                <button type="button" onClick={() => onNavigate("Register")}>
                  Create account
                </button>
              </div>
            </form>
          </div>
        </section>
      </div>
    </div>
  )
}

export function RegisterPage({ onNavigate, onRegister }: RegisterPageProps) {
  const [fullName, setFullName] = React.useState("")
  const [email, setEmail] = React.useState("")
  const [username, setUsername] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [confirmPassword, setConfirmPassword] = React.useState("")
  const [error, setError] = React.useState("")
  const [success, setSuccess] = React.useState("")
  const [isSubmitting, setIsSubmitting] = React.useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")
    setSuccess("")
    if (!fullName.trim() || !username.trim() || !password || !confirmPassword) {
      setError("Please fill in all required fields.")
      return
    }

    setIsSubmitting(true)
    try {
      const response = await onRegister({
        full_name: fullName,
        username,
        email: email || undefined,
        password,
        confirm_password: confirmPassword,
      })
      setSuccess(response.message)
      setFullName("")
      setEmail("")
      setUsername("")
      setPassword("")
      setConfirmPassword("")
    } catch (registerError) {
      setError(registerError instanceof Error ? registerError.message : "Registration failed.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="auth-page auth-page-register">
      <div className="auth-shell auth-shell-register">
        <AuthVisualPanel
          subline="Research Lab Access"
          kicker="Simulation workspace"
          title="Join the team improving adaptive traffic control."
          description="Create an account for scenario experiments, SUMO runs, performance reports, and upcoming controller research."
          rlStatus="Ready"
        />

        <section className="auth-form-panel">
          <div className="auth-form-card">
            <div className="auth-form-header">
              <div className="auth-form-eyebrow">Request workspace access</div>
              <h1 className="auth-form-title">Create account</h1>
              <p className="auth-form-description">
                Set up your SmartFlow profile. Admins can adjust roles after registration.
              </p>
            </div>

            <form className="auth-form-content" onSubmit={handleSubmit}>
              <div className={error ? "alert alert-error" : "alert alert-error hidden"}>{error}</div>
              <div className={success ? "alert alert-success" : "alert alert-success hidden"}>{success}</div>

              <AuthSection title="Identity">
                <div className="form-row">
                  <AuthField
                    id="fullname-input"
                    label="Full Name"
                    placeholder="Enter your full name"
                    autoComplete="name"
                    value={fullName}
                    onChange={setFullName}
                  />
                  <AuthField
                    id="email-input"
                    label="Email"
                    placeholder="your.email@example.com"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={setEmail}
                  />
                </div>
              </AuthSection>

              <AuthSection title="Account">
                <AuthField
                  id="reg-username-input"
                  label="Username"
                  placeholder="Choose a username"
                  autoComplete="username"
                  value={username}
                  onChange={setUsername}
                />
              </AuthSection>

              <AuthSection title="Security">
                <div className="form-row">
                  <AuthField
                    id="reg-password-input"
                    label="Password"
                    placeholder="Create a password"
                    type="password"
                    autoComplete="new-password"
                    hint="Use a strong password for lab access."
                    value={password}
                    onChange={setPassword}
                  />
                  <AuthField
                    id="reg-confirm-input"
                    label="Confirm Password"
                    placeholder="Confirm your password"
                    type="password"
                    autoComplete="new-password"
                    hint="Must match the password above."
                    value={confirmPassword}
                    onChange={setConfirmPassword}
                  />
                </div>
              </AuthSection>

              <Button className="btn btn-primary btn-full" type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Creating Account..." : "Create Account"}
              </Button>
              <div className="auth-footer">
                <span>Already have an account? </span>
                <button type="button" onClick={() => onNavigate("Login")}>
                  Sign in
                </button>
              </div>
            </form>
          </div>
        </section>
      </div>
    </div>
  )
}

export function ChangePasswordPage({ onCancel, onChangePassword }: ChangePasswordPageProps) {
  const [currentPassword, setCurrentPassword] = React.useState("")
  const [newPassword, setNewPassword] = React.useState("")
  const [confirmPassword, setConfirmPassword] = React.useState("")
  const [showPasswords, setShowPasswords] = React.useState(false)
  const [error, setError] = React.useState("")
  const [success, setSuccess] = React.useState("")
  const [isSubmitting, setIsSubmitting] = React.useState(false)
  const redirectTimeoutRef = React.useRef<number | null>(null)
  const minimumPasswordLength = 8

  React.useEffect(() => {
    void import("../../assets/auth.css")

    return () => {
      if (redirectTimeoutRef.current !== null) {
        window.clearTimeout(redirectTimeoutRef.current)
      }
    }
  }, [])

  function handleCancel() {
    if (redirectTimeoutRef.current !== null) {
      window.clearTimeout(redirectTimeoutRef.current)
      redirectTimeoutRef.current = null
    }
    onCancel()
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")
    setSuccess("")

    if (!currentPassword || !newPassword || !confirmPassword) {
      setError("All fields are required.")
      return
    }
    if (newPassword.length < minimumPasswordLength) {
      setError(`New password must be at least ${minimumPasswordLength} characters.`)
      return
    }
    if (newPassword !== confirmPassword) {
      setError("New password and confirmation do not match.")
      return
    }

    setIsSubmitting(true)
    try {
      const response = await onChangePassword({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      })
      setSuccess(response.message)
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
      setShowPasswords(false)
      redirectTimeoutRef.current = window.setTimeout(() => {
        redirectTimeoutRef.current = null
        onCancel()
      }, 2000)
    } catch (changeError) {
      setError(changeError instanceof Error ? changeError.message : "Password update failed.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="auth-page auth-page-change-password">
      <div className="auth-shell auth-shell-change-password">
        <AuthVisualPanel
          subline="Account Security"
          kicker="Protected workspace"
          title="Keep your simulation workspace secure."
          description="Refresh your credentials without leaving the SmartFlow control environment or interrupting your active research session."
          rlStatus="Session active"
        />

        <section className="auth-form-panel">
          <div className="auth-form-card">
            <div className="auth-form-header">
              <div className="auth-form-eyebrow">Security settings</div>
              <h1 className="auth-form-title">Change password</h1>
              <p className="auth-form-description">
                Verify your current password, then create a new password for your SmartFlow account.
              </p>
            </div>

            <form className="auth-form-content" onSubmit={handleSubmit} noValidate>
              {error ? (
                <div className="alert alert-error" role="alert">
                  {error}
                </div>
              ) : null}
              {success ? (
                <div className="alert alert-success auth-password-success" role="status" aria-live="polite">
                  {success} Returning to the workspace in two seconds.
                </div>
              ) : null}

              <AuthSection title="Verify Identity">
                <AuthField
                  id="current-password-input"
                  label="Current Password"
                  placeholder="Enter your current password"
                  type={showPasswords ? "text" : "password"}
                  autoComplete="current-password"
                  hint="Required to confirm that this account belongs to you."
                  value={currentPassword}
                  onChange={setCurrentPassword}
                />
              </AuthSection>

              <AuthSection title="New Credentials">
                <div className="form-row">
                  <AuthField
                    id="new-password-input"
                    label="New Password"
                    placeholder="Create a new password"
                    type={showPasswords ? "text" : "password"}
                    autoComplete="new-password"
                    hint={`Use at least ${minimumPasswordLength} characters.`}
                    value={newPassword}
                    onChange={setNewPassword}
                  />
                  <AuthField
                    id="confirm-password-input"
                    label="Confirm Password"
                    placeholder="Repeat your new password"
                    type={showPasswords ? "text" : "password"}
                    autoComplete="new-password"
                    hint="Must match the new password."
                    value={confirmPassword}
                    onChange={setConfirmPassword}
                  />
                </div>
              </AuthSection>

              <div className="auth-password-actions">
                <Button
                  className="auth-password-visibility"
                  type="button"
                  variant="outline"
                  aria-pressed={showPasswords}
                  onClick={() => setShowPasswords((isVisible) => !isVisible)}
                  disabled={isSubmitting || Boolean(success)}
                >
                  {showPasswords ? "Hide all passwords" : "Show all passwords"}
                </Button>
              </div>

              <Button
                className="btn btn-primary btn-full"
                type="submit"
                disabled={isSubmitting || Boolean(success)}
              >
                {isSubmitting ? "Updating Password..." : "Update Password"}
              </Button>
              <div className="auth-footer">
                <span>Keep your current password? </span>
                <button type="button" onClick={handleCancel} disabled={isSubmitting}>
                  Back to workspace
                </button>
              </div>
            </form>
          </div>
        </section>
      </div>
    </div>
  )
}
