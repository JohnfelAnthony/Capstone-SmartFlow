import { CarFrontIcon, CircleHelpIcon, GaugeIcon, RouteIcon, TimerIcon } from "lucide-react"

import type { SimulationRunRecord } from "@/api/simulation"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { controlLabel } from "@/lib/control-labels"
import { formatMetric, metricDescription, metricValue, percentChange } from "@/lib/metrics"
import type { ReferenceRun } from "@/lib/reference-run"
import { cn } from "@/lib/utils"
import "@/styles/admin-user-management.css"

const KPIS = [
  { key: "avg_wait", label: "Average wait", unit: "s", digits: 1, lowerIsBetter: true, scale: 1, icon: TimerIcon, tone: "info" },
  { key: "avg_queue", label: "Average queue", unit: "veh", digits: 1, lowerIsBetter: true, scale: 1, icon: CarFrontIcon, tone: "warning" },
  { key: "throughput_per_hour", label: "Throughput", unit: "veh/h", digits: 0, lowerIsBetter: false, scale: 1, icon: GaugeIcon, tone: "success" },
  // Engine reports seconds; minutes read better for whole trips.
  { key: "avg_travel_time", label: "Average travel time", unit: "min", digits: 1, lowerIsBetter: true, scale: 1 / 60, icon: RouteIcon, tone: "danger" },
]

export function DashboardKpis({ metrics, reference, isReferenceRun }: {
  metrics: Record<string, unknown> | null | undefined
  reference: ReferenceRun | null
  isReferenceRun: boolean
}) {
  const baseline: SimulationRunRecord | null = reference?.run ?? null
  const referenceName = reference ? `${controlLabel(reference.kind)} run #${reference.run.id}` : ""
  return <section className="audit-metric-strip" aria-label="Simulation KPIs">
    {KPIS.map((kpi) => {
      const current = metricValue(metrics, kpi.key)
      const change = isReferenceRun ? undefined : percentChange(current, metricValue(baseline?.metrics, kpi.key))
      const isBetter = change !== undefined && (kpi.lowerIsBetter ? change < 0 : change > 0)
      const isUnchanged = change !== undefined && Math.abs(change) < 0.5
      const hint = isReferenceRun ? `This is the ${controlLabel("no-signal")} reference`
        : change === undefined ? (reference ? `vs ${referenceName}` : "No reference run yet")
        : isUnchanged ? `Same as ${referenceName}` : `${Math.abs(change).toFixed(0)}% ${isBetter ? "better" : "worse"} than ${referenceName}`
      const Icon = kpi.icon
      return <div key={kpi.key} className={cn("audit-strip-metric", kpi.tone)}>
        <Icon className="shrink-0" />
        <div>
          <div>
            <strong className="tabular-nums">{formatMetric(current === null ? null : current * kpi.scale, kpi.digits)}</strong>
            <span>{kpi.unit}</span>
          </div>
          <small className="flex items-center gap-1">
            {kpi.label}
            <Tooltip>
              <TooltipTrigger render={<button type="button" aria-label={`How ${kpi.label.toLowerCase()} is measured`} />}>
                <CircleHelpIcon className="size-3.5" />
              </TooltipTrigger>
              <TooltipContent className="max-w-72">{metricDescription(kpi.key)}</TooltipContent>
            </Tooltip>
          </small>
          <small className={cn(change !== undefined && !isUnchanged && (isBetter ? "text-primary" : "text-destructive"))}>{hint}</small>
        </div>
      </div>
    })}
  </section>
}
