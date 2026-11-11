import * as React from "react"
import { toast } from "sonner"
import { UploadIcon } from "lucide-react"

import { apiRequest } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"

function readBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "")
    reader.onerror = () => reject(new Error(`Could not read ${file.name}.`))
    reader.readAsDataURL(file)
  })
}

export function DesktopModelImport({ onImported }: { onImported: () => void }) {
  const input = React.useRef<HTMLInputElement>(null)
  const [trusted, setTrusted] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState("")
  const [open, setOpen] = React.useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!trusted || busy) return
    setError("")
    setBusy(true)
    try {
      const files = Array.from(input.current?.files ?? [])
      const artifact = files.find((file) => /\.(zip|json)$/i.test(file.name) && !file.name.endsWith(".metadata.json"))
      if (!artifact) throw new Error("Select a QL JSON file or a DQL/PPO ZIP with its metadata.")
      const isNeural = artifact.name.toLowerCase().endsWith(".zip")
      const metadata = isNeural ? files.find((file) => file.name === artifact.name.slice(0, -4) + ".metadata.json") : undefined
      if (isNeural ? !metadata || files.length !== 2 : files.length !== 1) {
        throw new Error("Choose one model at a time and include the matching metadata for a ZIP.")
      }
      if (artifact.size > 32 * 1024 * 1024 || (metadata && metadata.size > 2 * 1024 * 1024)) {
        throw new Error("Select a model up to 32 MB and metadata up to 2 MB.")
      }
      const result = await apiRequest<{ algorithm: string; already_imported: boolean }>("/api/desktop/rl/models/import", {
        method: "POST",
        body: {
          filename: artifact.name,
          content: await readBase64(artifact),
          metadata_filename: metadata?.name,
          metadata: metadata && await readBase64(metadata),
          trusted,
        },
      })
      toast.success(`${result.algorithm.toUpperCase()} model ${result.already_imported ? "already in your library" : "imported"}`)
      if (input.current) input.current.value = ""
      setTrusted(false)
      setOpen(false)
      onImported()
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not import the model.")
    } finally {
      setBusy(false)
    }
  }

  return <Sheet open={open} onOpenChange={(next) => {
    if (busy) return
    setOpen(next)
    if (!next) {
      setTrusted(false)
      setError("")
    }
  }}>
    <SheetTrigger render={<Button variant="outline" size="sm" />}>
      <UploadIcon data-icon="inline-start" /> Import model
    </SheetTrigger>
    <SheetContent className="overflow-y-auto">
      <SheetHeader className="pr-12">
        <SheetTitle>Import model</SheetTitle>
        <SheetDescription>Choose a SmartFlow QL JSON, or select a DQL/PPO ZIP and its matching .metadata.json together.</SheetDescription>
      </SheetHeader>
      <form className="px-4 pb-4" onSubmit={(event) => void submit(event)}>
        <FieldGroup>
          <Field data-invalid={Boolean(error)}>
            <FieldLabel htmlFor="desktop-model-files">Model files</FieldLabel>
            <Input ref={input} id="desktop-model-files" type="file" multiple accept=".json,.zip" disabled={busy}
              aria-invalid={Boolean(error)} onChange={() => { setTrusted(false); setError("") }} />
            {error && <FieldError>{error}</FieldError>}
          </Field>
          <Field orientation="horizontal">
            <Checkbox id="desktop-model-trusted" checked={trusted} onCheckedChange={setTrusted} disabled={busy} />
            <FieldLabel htmlFor="desktop-model-trusted">I trust these files. Loading a DQL or PPO archive can execute code on this PC.</FieldLabel>
          </Field>
          <Button className="self-start" type="submit" disabled={!trusted || busy}>{busy ? "Importing…" : "Import model"}</Button>
        </FieldGroup>
      </form>
    </SheetContent>
  </Sheet>
}
