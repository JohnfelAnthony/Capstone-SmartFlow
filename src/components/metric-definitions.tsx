import { metricCatalog, metricDefinitions } from "@/lib/metrics"

export function MetricDefinitions({ keys }: { keys?: string[] }) {
  const definitions = keys ? metricDefinitions.filter((item) => keys.includes(item.key)) : metricDefinitions
  return (
    <details className="p-3">
      <summary>How these metrics are measured</summary>
      <p>{metricCatalog.scope} {metricCatalog.window}</p>
      <p>— means unavailable, not zero. Empty populations cannot establish a zero average. Older recordings may lack the counts needed to verify an average. These definitions describe {metricCatalog.engine_version}; a different historical engine retains its original evidence and is not assigned native metric meanings.</p>
      <dl className="flex flex-col gap-3">
        {definitions.map((item) => <div key={item.key}>
          <dt className="font-medium">{item.label} ({item.unit})</dt>
          <dd>{item.definition} Population: {item.population} {item.zero}</dd>
        </div>)}
      </dl>
      <p>{metricCatalog.unsupported.emissions}</p>
    </details>
  )
}
