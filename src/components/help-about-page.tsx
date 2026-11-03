import type * as React from "react"
import {
  BookOpenIcon,
  CircleHelpIcon,
  FileDownIcon,
  GaugeIcon,
  MapPinnedIcon,
  MicrochipIcon,
  PlayIcon,
  RocketIcon,
  RouteIcon,
  SlidersHorizontalIcon,
} from "lucide-react"

import { metricDefinitions } from "@/lib/metrics"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import "@/styles/help-about.css"

type Icon = React.ComponentType<React.SVGProps<SVGSVGElement>>

const quickStartSteps: { title: string; description: string; icon: Icon }[] = [
  { title: "Choose a scenario", icon: MapPinnedIcon, description: "Pick a saved scenario on Scenarios. It sets the site, traffic density and pedestrians." },
  { title: "Choose signal control", icon: SlidersHorizontalIcon, description: "Run with no signal, a fixed-time plan, or a trained RL model for the junction." },
  { title: "Run the simulation", icon: PlayIcon, description: "Start a live run on the Dashboard, or replay a saved recording." },
  { title: "Watch the metrics", icon: GaugeIcon, description: "Follow waiting time, queues and completed trips while the run plays." },
  { title: "Review results", icon: FileDownIcon, description: "Export runs on Runs & Reports, or put two runs side by side on Compare Runs." },
]

// Plain-language summaries; the full catalog definitions are on Runs & Reports.
const keyMetrics: { key: string; summary: string; tone: string }[] = [
  { key: "avg_wait", summary: "Average time vehicles spend stopped during the measurement.", tone: "warning" },
  { key: "avg_queue", summary: "Average number of stopped vehicles per incoming lane.", tone: "info" },
  { key: "max_queue", summary: "Largest number of stopped vehicles seen on any one lane.", tone: "error" },
  { key: "throughput", summary: "Vehicle trips completed during the measurement.", tone: "success" },
  { key: "avg_travel_time", summary: "Average time a completed trip took to cross the network.", tone: "purple" },
  { key: "avg_ped_delay", summary: "Average time pedestrians wait before crossing.", tone: "accent" },
]
const metricLabels = new Map(metricDefinitions.map((metric) => [metric.key, `${metric.label} (${metric.unit})`]))

const faqs = [
  {
    question: "Can several simulations run at once?",
    answer: "No. One live run, recording or training job runs at a time. Others can watch it, and saved runs can be reviewed any time.",
  },
  {
    question: "What is the difference between fixed-time and RL control?",
    answer: "Fixed-time follows the saved signal plan. An RL model chooses which phase to serve at one junction, within the same safety rules.",
  },
  {
    question: "Do these results show real Tagum traffic?",
    answer: "Not yet. Demand and site details are provisional until field observations are reviewed and the site passes validation.",
  },
  {
    question: "Why can't I see some pages?",
    answer: "Pages follow your role's permissions. Ask an administrator to change your access on Role & Access Control.",
  },
]

function Section({ title, description, icon: Icon, children }: {
  title: string; description: string; icon: Icon; children: React.ReactNode
}) {
  return (
    <Card className="help-section-card">
      <CardHeader>
        <CardTitle className="help-section-title"><Icon /><span>{title}</span></CardTitle>
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
          <Badge variant="secondary"><CircleHelpIcon data-icon="inline-start" />Help Center</Badge>
          <h1>Help & Documentation</h1>
          <p>How to run a simulation, read its results and find your way around SmartFlow.</p>
        </div>
        <div className="help-hero-system">
          <RouteIcon />
          <span>SmartFlow Traffic</span>
          <strong>Tagum City study</strong>
        </div>
      </section>

      <Section title="Getting started" icon={RocketIcon} description="Five steps from a scenario to a result.">
        <ol className="help-step-grid">
          {quickStartSteps.map((step, index) => (
            <li className="help-step-card" key={step.title}>
              <span className="help-step-number">{index + 1}</span>
              <step.icon />
              <h3>{step.title}</h3>
              <p>{step.description}</p>
            </li>
          ))}
        </ol>
      </Section>

      <section className="help-top-grid">
        <Section title="Key metrics" icon={BookOpenIcon} description="What the main numbers mean. Full definitions are on Runs & Reports.">
          <div className="help-metric-grid">
            {keyMetrics.map((metric) => (
              <article className="help-metric-card" data-tone={metric.tone} key={metric.key}>
                <div className="help-metric-icon"><BookOpenIcon /></div>
                <div>
                  <h3>{metricLabels.get(metric.key) ?? metric.key}</h3>
                  <p>{metric.summary}</p>
                </div>
              </article>
            ))}
          </div>
        </Section>

        <Section title="Common questions" icon={CircleHelpIcon} description="Quick answers to what people ask most.">
          <div className="help-faq-list">
            {faqs.map((faq) => (
              <details className="help-faq-item" key={faq.question}>
                <summary>{faq.question}</summary>
                <p>{faq.answer}</p>
              </details>
            ))}
          </div>
        </Section>
      </section>

      <section className="help-footer-note">
        <MicrochipIcon />
        <span>Native research prototype: React interface, Python traffic engine and FastAPI, with data stored locally in SQLite.</span>
      </section>
    </main>
  )
}
