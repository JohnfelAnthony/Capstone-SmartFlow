import { CircleHelpIcon, TrendingDownIcon, TrendingUpIcon } from "lucide-react"

import type { SimulationRunRecord } from "@/api/simulation"
import { Badge } from "@/components/ui/badge"
import { Card, CardAction, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { controlLabel } from "@/lib/control-labels"
import { formatMetric, metricDescription, metricValue, percentChange } from "@/lib/metrics"
import type { ReferenceRun } from "@/lib/reference-run"

const KPIS = [
  { key: "avg_wait", label: "Average wait", unit: "s", digits: 1, lowerIsBetter: true, scale: 1 },
  { key: "avg_queue", label: "Average queue", unit: "veh", digits: 1, lowerIsBetter: true, scale: 1 },
  { key: "throughput_per_hour", label: "Throughput", unit: "veh/h", digits: 0, lowerIsBetter: false, scale: 1 },
  // Engine reports seconds; minutes read better for whole trips.
  { key: "avg_travel_time", label: "Average travel time", unit: "min", digits: 1, lowerIsBetter: true, scale: 1 / 60 },
]

export function DashboardKpis({ metrics, reference, isReferenceRun }: {
  metrics: Record<string, unknown> | null | undefined
  reference: ReferenceRun | null
  isReferenceRun: boolean
}) {
  const baseline: SimulationRunRecord | null = reference?.run ?? null
  const comparisonNote = isReferenceRun ? `This run is the ${controlLabel("no-signal")} reference`
    : reference ? `vs ${controlLabel(reference.kind)} run #${reference.run.id} (same settings, demand, seed and duration)`
    : "No matching no-signal or fixed-time run yet (same settings, demand, seed and duration)"
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
    {KPIS.map((kpi) => {
      const current = metricValue(metrics, kpi.key)
      const change = isReferenceRun ? undefined : percentChange(current, metricValue(baseline?.metrics, kpi.key))
      const isBetter = change !== undefined && (kpi.lowerIsBetter ? change < 0 : change > 0)
      const isUnchanged = change !== undefined && Math.abs(change) < 0.5
      const TrendIcon = change !== undefined && change < 0 ? TrendingDownIcon : TrendingUpIcon
      return <Card key={kpi.key} size="sm">
        <CardHeader>
          <CardDescription className="flex items-center gap-1">
            {kpi.label}
            <Tooltip>
              <TooltipTrigger render={<button type="button" aria-label={`How ${kpi.label.toLowerCase()} is measured`} />}>
                <CircleHelpIcon className="size-3.5" />
              </TooltipTrigger>
              <TooltipContent className="max-w-72">{metricDescription(kpi.key)}</TooltipContent>
            </Tooltip>
          </CardDescription>
          <CardTitle className="text-2xl font-semibold tabular-nums">
            {formatMetric(current === null ? null : current * kpi.scale, kpi.digits)} <span className="text-sm font-normal text-muted-foreground">{kpi.unit}</span>
          </CardTitle>
          {change !== undefined ? <CardAction>
            <Badge variant={isUnchanged || isBetter ? "secondary" : "destructive"}>
              {isUnchanged ? null : <TrendIcon />}
              {isUnchanged ? "Same" : `${Math.abs(change).toFixed(0)}% ${isBetter ? "better" : "worse"}`}
            </Badge>
          </CardAction> : null}
        </CardHeader>
        <CardFooter className="text-xs text-muted-foreground">{comparisonNote}</CardFooter>
      </Card>
    })}
  </div>
}
