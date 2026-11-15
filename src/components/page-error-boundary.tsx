import * as React from "react"
import { RefreshCcwIcon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

/** Keeps the sidebar and header when a page (or its lazy script or CSS) fails; give it `key={page}` so a page change resets it. */
export class PageErrorBoundary extends React.Component<{ children: React.ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error: unknown) {
    console.error("SmartFlow page failed to load.", error)
  }

  render() {
    if (!this.state.failed) return this.props.children
    return <div className="p-6">
      <Alert variant="destructive">
        <AlertTitle>This page failed to load</AlertTitle>
        <AlertDescription className="flex flex-col items-start gap-2">
          The connection may have dropped or the app was updated. Reload to try again; other pages still work.
          <Button size="sm" variant="outline" onClick={() => window.location.reload()}><RefreshCcwIcon data-icon="inline-start" />Reload</Button>
        </AlertDescription>
      </Alert>
    </div>
  }
}
