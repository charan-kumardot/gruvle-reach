"use client";

import Link from "next/link";
import { motion, type Variants } from "framer-motion";
import {
  ArrowRight, Search, Users, Landmark, Megaphone, PenSquare, Radar,
  ShieldCheck, CheckCircle2, Zap, TrendingUp, Swords, Mail,
} from "lucide-react";
import { MarketingNav } from "@/components/marketing/nav";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" } },
};

export default function LandingPage() {
  return (
    <div>
      <MarketingNav />

      {/* Hero */}
      <section className="mx-auto max-w-5xl px-6 pb-20 pt-24 text-center">
        <motion.div initial="hidden" animate="show" variants={fadeUp}>
          <Badge variant="outline" className="mb-6">Founder Growth Intelligence</Badge>
          <h1 className="mx-auto max-w-3xl text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
            Find the people, opportunities and actions that move your product forward.
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-base text-[var(--muted-foreground)] sm:text-lg">
            Gruvle Reach researches your market, finds high-fit customers and investors, discovers growth
            opportunities, and turns them into a prioritized action plan.
          </p>
          <div className="mt-8 flex items-center justify-center gap-3">
            <Button size="lg" asChild>
              <Link href="/register">Build my growth map <ArrowRight className="ml-1.5 h-4 w-4" /></Link>
            </Button>
            <Button size="lg" variant="secondary" asChild>
              <a href="#how-it-works">See how it works</a>
            </Button>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mx-auto mt-16 max-w-3xl rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)]/70 p-2 shadow-2xl backdrop-blur-xl"
        >
          <div className="rounded-[calc(var(--radius-lg)-4px)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] p-5 text-left">
            <p className="mb-3 text-xs font-medium text-[var(--muted-foreground)]">7 actions most likely to move Gruvle Radar forward today</p>
            <div className="flex flex-col gap-2">
              {[
                { title: "Contact XYZ SaaS", tag: "Customer", impact: "94", note: "Recently launched an AI feature — infra dependency rising." },
                { title: "Follow up with ABC Ventures", tag: "Investor", impact: "91", note: "Recently invested in an adjacent observability startup." },
                { title: "Respond to a relevant discussion", tag: "Brand", impact: "88", note: "\"What tools monitor API changes?\"" },
              ].map((row) => (
                <div key={row.title} className="flex items-center justify-between gap-3 rounded-[var(--radius-sm)] bg-[var(--border-subtle)] px-3 py-2.5">
                  <div className="min-w-0 text-left">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{row.title}</span>
                      <Badge variant="outline">{row.tag}</Badge>
                    </div>
                    <p className="mt-0.5 truncate text-xs text-[var(--muted-foreground)]">{row.note}</p>
                  </div>
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--accent-soft)] text-xs font-semibold text-[var(--accent)]">{row.impact}</span>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      </section>

      {/* Problem */}
      <Section eyebrow="The problem">
        <h2 className="text-2xl font-semibold tracking-tight">Building the product is only half the job.</h2>
        <div className="mt-10 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
          {["Product", "Customers", "Investors", "Distribution", "Growth"].map((step, i, arr) => (
            <div key={step} className="flex items-center gap-3">
              <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] px-4 py-2 text-sm font-medium">{step}</div>
              {i < arr.length - 1 && <ArrowRight className="h-4 w-4 text-[var(--muted-foreground)]" />}
            </div>
          ))}
        </div>
        <p className="mx-auto mt-8 max-w-xl text-sm text-[var(--muted-foreground)]">
          Stop searching manually. Customer discovery, investor research, launch platforms, communities, and content
          opportunities — Gruvle Reach researches all of it continuously.
        </p>
      </Section>

      {/* Agents */}
      <Section id="how-it-works" eyebrow="Your AI growth research team">
        <h2 className="text-2xl font-semibold tracking-tight">Specialized agents. A shared evidence ledger.</h2>
        <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[
            { icon: Search, name: "Research Agent", desc: "Finds and fetches evidence safely across the web." },
            { icon: Users, name: "Customer Agent", desc: "Discovers and scores target accounts against your ICP." },
            { icon: Landmark, name: "Investor Agent", desc: "Matches investors by sector, stage, and geography." },
            { icon: Megaphone, name: "Marketing Agent", desc: "Finds launch platforms, communities, and events." },
            { icon: PenSquare, name: "Content Agent", desc: "Repurposes one idea across every channel." },
            { icon: Swords, name: "Competitor Agent", desc: "Watches public pages for meaningful changes." },
          ].map((agent) => (
            <Card key={agent.name}>
              <CardContent className="p-5 text-left">
                <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-[var(--radius-md)] bg-[var(--accent-soft)] text-[var(--accent)]">
                  <agent.icon className="h-4.5 w-4.5" />
                </div>
                <p className="text-sm font-medium">{agent.name}</p>
                <p className="mt-1 text-xs text-[var(--muted-foreground)]">{agent.desc}</p>
              </CardContent>
            </Card>
          ))}
        </div>
        <p className="mx-auto mt-8 max-w-xl text-sm text-[var(--muted-foreground)]">
          A Chief Growth Agent combines all of it into <strong className="text-[var(--foreground)]">today&apos;s 7 best actions</strong> —
          ranked by evidence-backed expected value, not guesswork.
        </p>
      </Section>

      {/* Evidence */}
      <Section id="evidence" eyebrow="Research with evidence">
        <h2 className="text-2xl font-semibold tracking-tight">Every claim has a source.</h2>
        <p className="mx-auto mt-3 max-w-xl text-sm text-[var(--muted-foreground)]">
          Gruvle Reach never presents an assumption as a verified fact. Every finding is tagged FACT, HYPOTHESIS, or
          INFERENCE — with a source URL, a timestamp, and a confidence score.
        </p>
        <Card className="mx-auto mt-8 max-w-lg text-left">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">&quot;Company recently raised funding.&quot;</p>
              <Badge variant="success">FACT</Badge>
            </div>
            <div className="mt-3 flex flex-col gap-1.5 text-xs text-[var(--muted-foreground)]">
              <p><span className="text-[var(--foreground)]">Evidence:</span> Official announcement on company blog</p>
              <p><span className="text-[var(--foreground)]">Source:</span> techcrunch.com/2026/...</p>
              <p><span className="text-[var(--foreground)]">Retrieved:</span> 2 hours ago</p>
              <p><span className="text-[var(--foreground)]">Confidence:</span> 98%</p>
            </div>
          </CardContent>
        </Card>
      </Section>

      {/* Approval */}
      <Section eyebrow="Your approval. Your relationships.">
        <h2 className="text-2xl font-semibold tracking-tight">Research → Draft → Your approval → Action.</h2>
        <div className="mx-auto mt-10 flex max-w-2xl flex-wrap items-center justify-center gap-3">
          {[
            { icon: Search, label: "Research" },
            { icon: PenSquare, label: "Draft" },
            { icon: ShieldCheck, label: "Your approval" },
            { icon: Mail, label: "Action" },
          ].map((step, i, arr) => (
            <div key={step.label} className="flex items-center gap-3">
              <div className="flex flex-col items-center gap-2 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] px-5 py-3">
                <step.icon className="h-4 w-4 text-[var(--accent)]" />
                <span className="text-xs font-medium">{step.label}</span>
              </div>
              {i < arr.length - 1 && <ArrowRight className="h-4 w-4 text-[var(--muted-foreground)]" />}
            </div>
          ))}
        </div>
        <p className="mx-auto mt-8 max-w-xl text-sm text-[var(--muted-foreground)]">
          Nothing sends or publishes without you. Gruvle Reach never optimizes for message volume — only for
          relevance, personalization, and relationships you&apos;d actually want to have.
        </p>
      </Section>

      {/* Integrations */}
      <Section id="integrations" eyebrow="Works with the tools you already use">
        <h2 className="text-2xl font-semibold tracking-tight">Free-first. Paid providers optional.</h2>
        <p className="mx-auto mt-3 max-w-xl text-sm text-[var(--muted-foreground)]">
          Runs on Ollama locally by default. Every external platform — email, LinkedIn, X, Instagram, Product Hunt —
          is an optional adapter with read-only access and transparent permissions.
        </p>
        <div className="mx-auto mt-8 flex max-w-2xl flex-wrap items-center justify-center gap-2">
          {["Ollama", "Groq", "Resend", "SearxNG", "LinkedIn", "X", "Instagram", "Product Hunt", "Slack"].map((name) => (
            <Badge key={name} variant="outline" className="px-3 py-1 text-xs">{name}</Badge>
          ))}
        </div>
      </Section>

      {/* Pricing */}
      <Section id="pricing" eyebrow="Pricing">
        <h2 className="text-2xl font-semibold tracking-tight">Built for founders.</h2>
        <div className="mx-auto mt-10 grid max-w-3xl grid-cols-1 gap-4 sm:grid-cols-2">
          <Card className="text-left">
            <CardContent className="p-6">
              <p className="text-sm font-medium">Self-hosted</p>
              <p className="mt-1 text-2xl font-semibold">Free</p>
              <p className="mt-1 text-xs text-[var(--muted-foreground)]">Ollama + your own Postgres/Redis</p>
              <ul className="mt-4 flex flex-col gap-2 text-xs text-[var(--muted-foreground)]">
                {["Full core loop", "Self-hosted search (SearxNG)", "Unlimited workspaces", "Community support"].map((f) => (
                  <li key={f} className="flex items-center gap-2"><CheckCircle2 className="h-3.5 w-3.5 text-[var(--success)]" /> {f}</li>
                ))}
              </ul>
            </CardContent>
          </Card>
          <Card className="text-left ring-1 ring-[var(--accent)]">
            <CardContent className="p-6">
              <p className="text-sm font-medium">Managed</p>
              <p className="mt-1 text-2xl font-semibold">Talk to us</p>
              <p className="mt-1 text-xs text-[var(--muted-foreground)]">Hosted, with faster inference and priority support</p>
              <ul className="mt-4 flex flex-col gap-2 text-xs text-[var(--muted-foreground)]">
                {["Everything in self-hosted", "Managed infrastructure", "Priority AI inference", "Onboarding support"].map((f) => (
                  <li key={f} className="flex items-center gap-2"><CheckCircle2 className="h-3.5 w-3.5 text-[var(--success)]" /> {f}</li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      </Section>

      {/* FAQ */}
      <Section id="faq" eyebrow="FAQ">
        <div className="mx-auto flex max-w-2xl flex-col gap-4 text-left">
          {[
            { q: "Is this a lead-gen tool?", a: "No. Gruvle Reach determines who matters, why, and why now — then hands you an evidence-backed action, not a scraped list." },
            { q: "Does it spam on my behalf?", a: "Never. Every external action requires your explicit approval before anything sends or publishes." },
            { q: "Do I need paid APIs?", a: "No. The core product runs on Ollama and self-hosted search with zero paid dependencies. Paid providers are optional adapters." },
            { q: "What about fake data?", a: "Demo data is always explicitly marked DEMO. Production research is never fabricated — every claim carries a source." },
          ].map((item) => (
            <div key={item.q} className="border-b border-[var(--border)] pb-4">
              <p className="text-sm font-medium">{item.q}</p>
              <p className="mt-1.5 text-xs text-[var(--muted-foreground)]">{item.a}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* Final CTA */}
      <Section>
        <div className="mx-auto flex max-w-xl flex-col items-center gap-5 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] px-8 py-12">
          <div className="flex h-10 w-10 items-center justify-center rounded-[var(--radius-md)] bg-[var(--accent)] text-[var(--accent-foreground)]">
            <Radar className="h-5 w-5" />
          </div>
          <h2 className="text-xl font-semibold tracking-tight">From thousands of possibilities to today&apos;s 7 best actions.</h2>
          <Button size="lg" asChild>
            <Link href="/register">Build my growth map <ArrowRight className="ml-1.5 h-4 w-4" /></Link>
          </Button>
        </div>
      </Section>

      <footer className="border-t border-[var(--border)] px-6 py-10 text-center text-xs text-[var(--muted-foreground)]">
        <p>Gruvle Reach — Founder Growth Intelligence.</p>
      </footer>
    </div>
  );
}

function Section({ id, eyebrow, children }: { id?: string; eyebrow?: string; children: React.ReactNode }) {
  return (
    <motion.section
      id={id}
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.5 }}
      className="mx-auto max-w-5xl px-6 py-16 text-center"
    >
      {eyebrow && <p className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--accent)]">{eyebrow}</p>}
      {children}
    </motion.section>
  );
}
