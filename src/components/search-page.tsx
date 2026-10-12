import * as React from "react"
import { searchWorkspace, type SearchResult } from "@/api/research"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"

export function SearchPage({ onOpen }: { onOpen: (result: SearchResult) => void }) {
  const [query, setQuery] = React.useState("")
  const [results, setResults] = React.useState<SearchResult[]>([])
  const [loading, setLoading] = React.useState(false)
  const [message, setMessage] = React.useState("")
  React.useEffect(() => {
    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      if (!query.trim()) { setResults([]); setMessage(""); setLoading(false); return }
      setLoading(true); setMessage("")
      try {
        const response = await searchWorkspace(query.trim(), controller.signal)
        if (!controller.signal.aborted) { setResults(response.results); setMessage(response.has_more ? "Showing up to 25 matches per category. Refine your search for more specific results." : response.results.length ? "" : "No matching pages or records found.") }
      } catch (error) {
        if (!controller.signal.aborted) { setResults([]); setMessage(error instanceof Error ? error.message : "Search failed.") }
      } finally { if (!controller.signal.aborted) setLoading(false) }
    }, 250)
    return () => { controller.abort(); window.clearTimeout(timer) }
  }, [query])
  return <main className="flex flex-col gap-6 p-4 lg:p-6">
    <div><h1 className="text-2xl font-semibold">Search</h1><p className="text-muted-foreground">Find pages, scenarios, saved runs, models and calibration records you can access.</p></div>
    <FieldGroup><Field><FieldLabel htmlFor="workspace-search">Search SmartFlow</FieldLabel><Input id="workspace-search" autoFocus maxLength={160} value={query} onChange={(event) => { setQuery(event.target.value); setResults([]) }} placeholder="Scenario name, run ID, model algorithm or study site" /><FieldDescription>Search uses saved record names and descriptions, not raw video or artifact contents.</FieldDescription></Field></FieldGroup>
    {loading && <Skeleton className="h-20 w-full" />}
    {message && <Alert><AlertDescription role="status">{message}</AlertDescription></Alert>}
    {!query.trim() && <Empty><EmptyHeader><EmptyTitle>Search your workspace</EmptyTitle><EmptyDescription>Enter a name or keyword to begin.</EmptyDescription></EmptyHeader></Empty>}
    <div className="grid gap-4 md:grid-cols-2" aria-live="polite">{results.map((result) => <Card key={`${result.kind}-${result.id ?? result.page}`}><CardHeader><CardTitle>{result.title}</CardTitle><CardDescription><Badge variant="outline">{result.kind}{result.id !== null ? ` #${result.id}` : ""}</Badge></CardDescription></CardHeader><CardContent className="flex flex-col gap-3"><p className="break-words">{result.description}</p><Button variant="outline" onClick={() => onOpen(result)}>Open {result.page}</Button></CardContent></Card>)}</div>
  </main>
}
