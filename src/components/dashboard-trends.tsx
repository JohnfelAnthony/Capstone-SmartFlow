import * as React from "react"
import { ChevronDownIcon } from "lucide-react"
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts"

import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"

export type TrendPoint = { timeLabel: string; avgWait: number | null; avgQueue: number | null }

const chartConfig = {
  avgWait: { label: "Average wait (s)", color: "var(--chart-1)" },
  avgQueue: { label: "Average queue (veh)", color: "var(--chart-2)" },
} satisfies ChartConfig

export function DashboardTrends({ history }: { history: TrendPoint[] }) {
  const [open, setOpen] = React.useState(true)
  return <Collapsible open={open} onOpenChange={setOpen} render={<Card size="sm" />}>
    <CardHeader>
      <CardTitle>Trends over time</CardTitle>
      <CardDescription>Average wait and average queue during this run. Gaps mean no vehicles were measured yet.</CardDescription>
      <CardAction>
        <CollapsibleTrigger render={<Button variant="ghost" size="icon-sm" aria-label={open ? "Hide trends" : "Show trends"} />}>
          <ChevronDownIcon className={open ? "rotate-180" : undefined} />
        </CollapsibleTrigger>
      </CardAction>
    </CardHeader>
    <CollapsibleContent>
      <CardContent>
        {history.length < 2 ? <Empty>
          <EmptyHeader><EmptyTitle>No trend yet</EmptyTitle><EmptyDescription>Start or replay a simulation to see how wait and queue change.</EmptyDescription></EmptyHeader>
        </Empty> : <ChartContainer config={chartConfig} className="aspect-auto h-56 w-full">
          <LineChart data={history} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="timeLabel" tickLine={false} axisLine={false} minTickGap={24} />
            <YAxis yAxisId="wait" tickLine={false} axisLine={false} width={36} />
            <YAxis yAxisId="queue" orientation="right" tickLine={false} axisLine={false} width={36} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <ChartLegend content={<ChartLegendContent />} />
            <Line yAxisId="wait" type="monotone" dataKey="avgWait" stroke="var(--color-avgWait)" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line yAxisId="queue" type="monotone" dataKey="avgQueue" stroke="var(--color-avgQueue)" strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ChartContainer>}
      </CardContent>
    </CollapsibleContent>
  </Collapsible>
}
