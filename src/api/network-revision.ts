import { apiRequest } from "@/api/client"
import type { VisualNetwork } from "@/api/visual-network"

type ObjectChanges = { available: true; added: string[]; removed: string[]; modified: string[] } | { available: false; reason: string }
export type NetworkRevisionReview = {
  network_id: string
  installed_sha256: string
  candidate_sha256: string | null
  installed_visual: VisualNetwork
  changes: Record<"nodes" | "roads" | "islands", ObjectChanges>
  affected_scenarios: Array<{ id: number; name: string; archived: boolean }>
  validation: { structurally_valid: boolean; clearance_checked: boolean; visual: VisualNetwork | null; issues: Array<{ severity: string; message: string }> }
  installable: false
  message: string
}

export function previewNetworkRevision(site: string, network: Record<string, unknown>) {
  return apiRequest<NetworkRevisionReview>(`/api/admin/networks/${encodeURIComponent(site)}/preview`, { method: "POST", body: { network } })
}
