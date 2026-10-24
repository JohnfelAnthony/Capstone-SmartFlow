import type * as React from "react"
import {
  BookOpenIcon,
  CircleHelpIcon,
  DatabaseIcon,
  FileDownIcon,
  GaugeIcon,
  MapPinnedIcon,
  MicrochipIcon,
  PlayIcon,
  RocketIcon,
  RouteIcon,
  Settings2Icon,
  SlidersHorizontalIcon,
} from "lucide-react"

import { metricCatalog, metricDefinitions } from "@/lib/metrics"
import { MetricDefinitions } from "@/components/metric-definitions"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import "@/styles/help-about.css"

type HelpStep = {
  title: string
  description: string
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>
}

type MetricGlossaryItem = {
  title: string
  description: string
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>
  tone: "warning" | "info" | "error" | "success" | "purple" | "accent"
}

type FaqItem = {
  question: string
  answer: string
}

const quickStartSteps: HelpStep[] = [
  {
    title: "Choose a Scenario",
    icon: MapPinnedIcon,
    description: "Choose a saved scenario. Identify its modeled network, input source and assumptions before making field claims.",
  },
  {
    title: "Select Control Mode",
    icon: SlidersHorizontalIcon,
    description: "Choose fixed-time or a compatible registered policy for one selected junction. Routing is separate from signal learning.",
  },
  {
    title: "Run the Simulation",
    icon: PlayIcon,
    description: "Start a live run from the dashboard, then monitor the phase, signal timer, queues, and live telemetry.",
  },
  {
    title: "Monitor Metrics",
    icon: GaugeIcon,
    description: "Watch waiting time, queue length, throughput, pedestrian activity, and event history during a run.",
  },
  {
    title: "Review Outputs",
    icon: FileDownIcon,
    description: "Use saved runs, generated timelines, reports, and comparison workflows to evaluate completed experiments.",
  },
]

const glossaryKeys = new Set(["avg_wait", "avg_queue", "max_queue", "throughput", "avg_travel_time", "avg_ped_delay",
  "requested_vehicles", "total_vehicles_spawned", "pending_demand", "dropped_vehicles", "unfinished_vehicles",
  "boundary_wait_seconds", "avg_admitted_boundary_wait", "measurement_start", "measurement_seconds"])
const metricGlossary: MetricGlossaryItem[] = metricDefinitions
  .filter((metric) => glossaryKeys.has(metric.key))
  .map((metric) => ({
    title: `${metric.label} (${metric.unit})`,
    icon: BookOpenIcon,
    tone: "info",
    description: `${metric.definition} Population: ${metric.population} ${metric.zero}`,
  }))

const faqs: FaqItem[] = [
  {
    question: "How is the AI reinforcement learning model trained?",
    answer:
      "SMARTFLOW keeps RL training in Python. React starts and monitors training through backend services, while traffic simulation, reward calculation, and model artifacts stay in the Python runtime.",
  },
  {
    question: "Can I run multiple simulations at the same time?",
    answer:
      "The runtime is designed around one active simulation session at a time for local reliability. Completed live runs and pre-recorded timelines can still be reviewed and compared later.",
  },
  {
    question: "What happens if a user account is pending?",
    answer:
      "Registration can create inactive accounts when approval-only mode is enabled. An administrator must approve the user before that account can sign in.",
  },
  {
    question: "How does fixed-time control differ from AI control?",
    answer:
      "Fixed-time uses saved signal plans with shared safety and pedestrian rules. A compatible registered RL policy can request safe service at one selected junction. Routing uses a separate graph algorithm; no controller effectiveness is established by a successful demonstration.",
  },
  {
    question: "How do pre-recorded timelines work?",
    answer:
      "A pre-record run fast-forwards Python in the backend, writes frame data to timeline artifacts, saves the run record in SQLite, and lets the dashboard load the recording for playback.",
  },
]

const systemSpecs = [
  ["App Version", "Native research prototype"],
  ["Frontend", "React, Vite, TypeScript"],
  ["API Layer", "FastAPI with HTTP and WebSocket endpoints"],
  ["Simulation Engine", "Native Python traffic model"],
  ["Database", "SQLite3 with local run, metric, scenario, user, and session data"],
  ["Authentication", "Werkzeug PBKDF2 password hashing with SQLite sessions"],
  ["Runtime Assets", "OSM road networks, generated visual-network JSON, timelines, and model artifacts"],
  ["Target Area", "Tagum City traffic intersections"],
]

function PageSection({
  title,
  description,
  icon: Icon,
  children,
}: {
  title: string
  description: string
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>
  children: React.ReactNode
}) {
  return (
    <Card className="help-section-card">
      <CardHeader>
        <CardTitle className="help-section-title">
          <Icon />
          <span>{title}</span>
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

export function HelpAboutPage() {
  return (
    <main className="help-about-page">
      <section className="help-hero">
        <div>
          <Badge variant="secondary">
            <CircleHelpIcon data-icon="inline-start" />
            Help Center
          </Badge>
          <h1>Help & Documentation</h1>
          <p>
            Run traffic simulation experiments, understand saved metrics, and keep the migrated React/FastAPI workflow clear.
          </p>
        </div>
        <div className="help-hero-system">
          <RouteIcon />
          <span>SMARTFLOW Traffic</span>
          <strong>Python + FastAPI + React</strong>
        </div>
      </section>

      <section className="help-top-grid">
        <PageSection
          title="Getting Started"
          icon={RocketIcon}
          description="The usual path for running your first scenario experiment."
        >
          <div className="help-step-grid">
            {quickStartSteps.map((step, index) => {
              const Icon = step.icon
              return (
                <article className="help-step-card" key={step.title}>
                  <span className="help-step-number">{index + 1}</span>
                  <Icon />
                  <h3>{step.title}</h3>
                  <p>{step.description}</p>
                </article>
              )
            })}
          </div>
        </PageSection>

        <PageSection
          title="System Specifications"
          icon={MicrochipIcon}
          description="Current architecture after the standalone SmartFlow migration."
        >
          <div className="help-spec-list">
            {systemSpecs.map(([label, value]) => (
              <div className="help-spec-row" key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
          <Separator />
          <div className="help-callout">
            <DatabaseIcon />
            <p>
              SmartFlow stores users, scenarios, simulation runs, run metrics, timeline paths, RL jobs, and model metadata in local SQLite.
            </p>
          </div>
        </PageSection>
      </section>

      <PageSection
        title="Traffic Metrics Glossary"
        icon={BookOpenIcon}
        description="Definitions shared with Python reports and calibration. — means unavailable; an empty population is not a measured zero average."
      >
        <p>{metricCatalog.scope} {metricCatalog.window} {metricCatalog.unsupported.emissions}</p>
        <div className="help-metric-grid">
          {metricGlossary.map((metric) => {
            const Icon = metric.icon
            return (
              <article className="help-metric-card" data-tone={metric.tone} key={metric.title}>
                <div className="help-metric-icon">
                  <Icon />
                </div>
                <div>
                  <h3>{metric.title}</h3>
                  <p>{metric.description}</p>
                </div>
              </article>
            )
          })}
        </div>
      </PageSection>

      <MetricDefinitions />

      <PageSection
        title="Frequently Asked Questions"
        icon={CircleHelpIcon}
        description="Answers to common questions about the migrated platform."
      >
        <div className="help-faq-list">
          {faqs.map((faq) => (
            <details className="help-faq-item" key={faq.question}>
              <summary>{faq.question}</summary>
              <p>{faq.answer}</p>
            </details>
          ))}
        </div>
      </PageSection>

      <section className="help-footer-note">
        <Settings2Icon />
        <span>Use the sidebar to move between scenarios, dashboard simulation, runs, reports, and admin pages based on your permissions.</span>
      </section>
    </main>
  )
}
