import * as React from "react"
import { AlertDialog } from "@base-ui/react/alert-dialog"

import { Button } from "@/components/ui/button"

export function ConfirmAction({ open, title, description, actionLabel, destructive = true, onCancel, onConfirm }: {
  open: boolean
  title: string
  description: string
  actionLabel: string
  destructive?: boolean
  onCancel: () => void
  onConfirm: () => Promise<void>
}) {
  const cancelButton = React.useRef<HTMLButtonElement>(null)
  const submitting = React.useRef(false)
  const [busy, setBusy] = React.useState(false)

  async function confirm() {
    if (submitting.current) return
    submitting.current = true
    setBusy(true)
    try {
      await onConfirm()
    } finally {
      submitting.current = false
      setBusy(false)
      onCancel()
    }
  }

  return (
    <AlertDialog.Root open={open} onOpenChange={(next, details) => {
      if (next) return
      if (submitting.current) details.cancel()
      else onCancel()
    }}>
      <AlertDialog.Portal>
        <AlertDialog.Backdrop className="fixed inset-0 z-50 bg-black/40" />
        <AlertDialog.Popup initialFocus={cancelButton} className="fixed top-1/2 left-1/2 z-50 grid w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 gap-4 rounded-lg border bg-popover p-6 text-popover-foreground shadow-lg">
          <AlertDialog.Title className="font-heading text-lg font-semibold">{title}</AlertDialog.Title>
          <AlertDialog.Description className="text-sm text-muted-foreground">{description}</AlertDialog.Description>
          <div className="flex flex-wrap justify-end gap-2">
            <AlertDialog.Close render={<Button ref={cancelButton} type="button" variant="outline" disabled={busy} />}>Cancel</AlertDialog.Close>
            <Button type="button" variant={destructive ? "destructive" : "default"} disabled={busy} onClick={() => void confirm()}>
              {busy ? "Working…" : actionLabel}
            </Button>
          </div>
        </AlertDialog.Popup>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  )
}
