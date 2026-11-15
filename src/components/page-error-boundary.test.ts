import { renderToStaticMarkup } from "react-dom/server"
import { expect, it } from "vitest"
import { PageErrorBoundary } from "@/components/page-error-boundary"

it("turns a failed page into a local message with Reload instead of blanking the app", () => {
  expect(PageErrorBoundary.getDerivedStateFromError()).toEqual({ failed: true })
  const boundary = new PageErrorBoundary({ children: "page" })
  expect(boundary.render()).toBe("page")
  boundary.state = { failed: true }
  const html = renderToStaticMarkup(boundary.render() as React.ReactElement)
  expect(html).toContain("This page failed to load")
  expect(html).toContain("Reload")
})
