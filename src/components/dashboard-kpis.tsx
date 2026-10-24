import { CircleHelpIcon, TrendingDownIcon, TrendingUpIcon } from "lucide-react"

import type { SimulationRunRecord } from "@/api/simulation"
import { Badge } from "@/components/ui/badge"
import { Card, CardAction, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { formatMetric, metricDescription, metricValue, percentChange } from "@/lib/metrics"

const KPIS = [
  { key: "avg_wait", label: "Average wait", unit: "s", digits: 1, lowerIsBetter: true },
  { key: "avg_queue", label: "Average queue", unit: "veh", digits: 1, lowerIsBetter: true },
  { key: "throughput_per_hour", label: "Throughput", unit: "veh/h", digits: 0, lowerIsBetter: false },
  { key: "throughput", label: "Completed trips", unit: "veh", digits: 0, lowerIsBetter: false },
]

export function DashboardKpis({ metrics, baseline, isBaselineRun }: {
  metrics: Record<string, unknown> | null | undefined
  baseline: SimulationRunRecord | null
  isBaselineRun: boolean
}) {
  const comparisonNote = isBaselineRun ? "This run uses the fixed-time plan"
    : baseline ? `vs fixed-time run #${baseline.id} (same scenario and seed)` : "No fixed-time baseline run yet"
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
    {KPIS.map((kpi) => {
      const current = metricValue(metrics, kpi.key)
      const change = isBaselineRun ? undefined : percentChange(current, metricValue(baseline?.metrics, kpi.key))
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
            {formatMetric(current, kpi.digits)} <span className="text-sm font-normal text-muted-foreground">{kpi.unit}</span>
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
