import type { ReactNode } from "react";

import { motion, type Variants } from "framer-motion";
import {
  ArrowRight,
  BadgeCheck,
  Bot,
  ChevronRight,
  MoveRight,
  Play,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Users,
  MessageSquareQuote,
} from "lucide-react";
import { Link } from "react-router-dom";

import { useWorkspaceAuth } from "../auth/useWorkspaceAuth";
import {
  dashboardRows,
  featureCards,
  featureStats,
  heroStats,
  operationalSignals,
  sparkPoints,
  testimonials,
  trustMarks,
} from "./landingContent";

const pageTransition: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.08 },
  },
};

const riseIn: Variants = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0, transition: { duration: 0.55, ease: "easeOut" as const } },
};

const hoverLift: Variants = {
  rest: { y: 0, scale: 1 },
  hover: { y: -6, scale: 1.01 },
};

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[0.7rem] font-semibold uppercase tracking-[0.28em] text-cyan-200/90 backdrop-blur-xl">
      <Sparkles className="h-3.5 w-3.5" />
      <span>{children}</span>
    </div>
  );
}

function SectionHeading({
  label,
  title,
  description,
  align = "left",
}: {
  label: string;
  title: string;
  description: string;
  align?: "left" | "center";
}) {
  return (
    <motion.div variants={riseIn} className={align === "center" ? "mx-auto max-w-3xl text-center" : "max-w-3xl"}>
      <SectionLabel>{label}</SectionLabel>
      <h2 className="mt-5 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
        {title}
      </h2>
      <p className="mt-4 text-base leading-7 text-slate-300 sm:text-lg">{description}</p>
    </motion.div>
  );
}

function GradientButton({
  to,
  children,
  variant = "primary",
  icon,
}: {
  to: string;
  children: ReactNode;
  variant?: "primary" | "secondary";
  icon?: ReactNode;
}) {
  const base =
    "group inline-flex items-center justify-center gap-2 rounded-full px-5 py-3 text-sm font-semibold transition-all duration-300";
  const styles =
    variant === "primary"
      ? "bg-white text-slate-950 shadow-[0_18px_60px_rgba(96,165,250,0.28)] hover:-translate-y-0.5 hover:shadow-[0_24px_70px_rgba(139,92,246,0.28)]"
      : "border border-white/[0.12] bg-white/5 text-white backdrop-blur-xl hover:border-cyan-300/40 hover:bg-white/10";

  return (
    <Link className={`${base} ${styles}`} to={to}>
      <span>{children}</span>
      {icon}
    </Link>
  );
}

function GlassCard({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      variants={hoverLift}
      initial="rest"
      whileHover="hover"
      transition={{ type: "spring", stiffness: 260, damping: 22 }}
      className={`rounded-[1.6rem] border border-white/10 bg-white/[0.06] p-5 shadow-[0_24px_80px_rgba(2,6,23,0.45)] backdrop-blur-2xl ${className}`}
    >
      {children}
    </motion.div>
  );
}

function Sparkline() {
  const path = sparkPoints
    .map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x} ${y}`)
    .join(" ");

  return (
    <svg viewBox="0 0 120 90" className="h-24 w-full overflow-visible">
      <defs>
        <linearGradient id="spark-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="50%" stopColor="#818cf8" />
          <stop offset="100%" stopColor="#22d3ee" />
        </linearGradient>
        <linearGradient id="spark-fill" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="rgba(56,189,248,0.35)" />
          <stop offset="100%" stopColor="rgba(56,189,248,0.02)" />
        </linearGradient>
      </defs>
      <path d={`${path} L 120 90 L 0 90 Z`} fill="url(#spark-fill)" />
      <path d={path} fill="none" stroke="url(#spark-gradient)" strokeWidth="2.5" strokeLinecap="round" />
      {sparkPoints.map(([x, y]) => (
        <circle key={`${x}-${y}`} cx={x} cy={y} r="2.8" fill="#f8fafc" fillOpacity="0.95" />
      ))}
    </svg>
  );
}

function MessageQuote() {
  return (
    <div className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-cyan-400/10 text-cyan-200">
      <MessageSquareQuote className="h-5 w-5" />
    </div>
  );
}

export function LandingPage() {
  const auth = useWorkspaceAuth();
  const primaryCta = auth.isAuthenticated ? "/query" : "/signin";

  return (
    <div className="relative isolate min-h-screen overflow-hidden bg-[#050816] text-slate-100">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.24),_transparent_28%),radial-gradient(circle_at_82%_18%,_rgba(168,85,247,0.24),_transparent_26%),radial-gradient(circle_at_50%_110%,_rgba(14,165,233,0.12),_transparent_32%)]" />
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.04)_1px,transparent_1px)] bg-[size:72px_72px] opacity-20 [mask-image:linear-gradient(to_bottom,white,transparent_88%)]" />

      <div className="relative mx-auto flex min-h-screen w-full max-w-7xl flex-col px-6 pb-12 pt-6 lg:px-8">
        <motion.header
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="sticky top-4 z-20 rounded-full border border-white/10 bg-slate-950/60 px-4 py-3 backdrop-blur-2xl"
        >
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              <div className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-cyan-400 via-blue-500 to-violet-500 shadow-[0_12px_40px_rgba(59,130,246,0.35)]">
                <Bot className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.26em] text-cyan-200/80">
                  SupplyChainNexus
                </p>
                <p className="text-sm text-slate-400">AI dashboard for serious supply-chain teams</p>
              </div>
            </div>

            <nav className="hidden items-center gap-6 text-sm text-slate-300 md:flex">
              <a href="#features" className="transition-colors hover:text-white">
                Features
              </a>
              <a href="#dashboard-preview" className="transition-colors hover:text-white">
                Dashboard
              </a>
              <a href="#trust" className="transition-colors hover:text-white">
                Proof
              </a>
            </nav>

            <div className="flex items-center gap-3">
              <Link
                to="/signin"
                className="rounded-full border border-white/10 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-white/20 hover:bg-white/5"
              >
                {auth.isAuthenticated ? "Switch account" : "Sign in"}
              </Link>
              <GradientButton to={primaryCta} icon={<ArrowRight className="h-4 w-4" />}>
                {auth.isAuthenticated ? "Open workspace" : "Launch workspace"}
              </GradientButton>
            </div>
          </div>
        </motion.header>

        <main className="flex-1">
          <motion.section
            variants={pageTransition}
            initial="hidden"
            animate="show"
            className="grid items-center gap-14 py-16 lg:grid-cols-[1.08fr_0.92fr] lg:py-24"
          >
            <div className="max-w-3xl">
              <motion.div variants={riseIn} className="inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100">
                <ShieldCheck className="h-4 w-4" />
                Investor-demo ready operational intelligence
              </motion.div>

              <motion.h1
                variants={riseIn}
                className="mt-6 text-5xl font-semibold tracking-tight text-white sm:text-6xl lg:text-7xl"
              >
                A premium AI control room for{" "}
                <span className="bg-gradient-to-r from-cyan-300 via-blue-400 to-violet-400 bg-clip-text text-transparent">
                  supply-chain decisions
                </span>
                .
              </motion.h1>

              <motion.p variants={riseIn} className="mt-6 max-w-2xl text-lg leading-8 text-slate-300 sm:text-xl">
                Fuse query, graph, and admin workflows into one polished dashboard that feels fast,
                trustworthy, and ready for high-stakes operational reviews.
              </motion.p>

              <motion.div variants={riseIn} className="mt-8 flex flex-col gap-4 sm:flex-row">
                <GradientButton to={primaryCta} icon={<MoveRight className="h-4 w-4" />}>
                  {auth.isAuthenticated ? "Enter workspace" : "Sign in to continue"}
                </GradientButton>
                <a
                  href="#dashboard-preview"
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-white/[0.12] bg-white/5 px-5 py-3 text-sm font-semibold text-white backdrop-blur-xl transition hover:border-cyan-300/30 hover:bg-white/10"
                >
                  <Play className="h-4 w-4" />
                  View dashboard preview
                </a>
              </motion.div>

              <motion.div variants={riseIn} className="mt-10 grid gap-4 sm:grid-cols-3">
                {heroStats.map((stat) => (
                  <GlassCard key={stat.label} className="p-4">
                    <div
                      className={`inline-flex rounded-full bg-gradient-to-r px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-white ${stat.tone}`}
                    >
                      Live
                    </div>
                    <div className="mt-4 text-3xl font-semibold tracking-tight text-white">{stat.value}</div>
                    <div className="mt-1 text-sm text-slate-400">{stat.label}</div>
                  </GlassCard>
                ))}
              </motion.div>
            </div>

            <motion.div variants={riseIn} className="relative">
              <div className="absolute -inset-8 -z-10 rounded-[2.5rem] bg-gradient-to-br from-cyan-500/20 via-violet-500/10 to-transparent blur-3xl" />
              <GlassCard className="overflow-hidden p-0">
                <div className="border-b border-white/10 px-5 py-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-slate-300">Command Center</p>
                      <p className="text-xs text-slate-500">Live signal orchestration</p>
                    </div>
                    <div className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs font-semibold text-emerald-200">
                      Operational
                    </div>
                  </div>
                </div>

                <div className="grid gap-4 p-5 sm:grid-cols-[1.1fr_0.9fr]">
                  <div className="rounded-[1.35rem] border border-white/10 bg-slate-950/50 p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Routing velocity</p>
                        <h3 className="mt-2 text-2xl font-semibold text-white">96.4% confidence</h3>
                      </div>
                      <div className="rounded-full bg-cyan-400/10 px-3 py-1 text-xs font-medium text-cyan-200">
                        +12.8%
                      </div>
                    </div>
                    <div className="mt-5 rounded-2xl border border-white/10 bg-white/5 p-3">
                      <Sparkline />
                    </div>
                  </div>

                  <div className="space-y-4">
                    {operationalSignals.map((signal) => (
                      <div
                        key={signal.label}
                        className="rounded-[1.35rem] border border-white/10 bg-white/5 p-4 backdrop-blur-xl"
                      >
                        <div className="flex items-center justify-between text-sm text-slate-400">
                          <span>{signal.label}</span>
                          <span className={signal.accent}>{signal.change}</span>
                        </div>
                        <div className="mt-2 text-xl font-semibold text-white">{signal.value}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="grid gap-3 border-t border-white/10 bg-white/[0.03] px-5 py-4 sm:grid-cols-3">
                  {featureStats.slice(0, 3).map((stat) => (
                    <div key={stat.label} className="rounded-2xl border border-white/10 bg-slate-950/[0.45] p-3">
                      <div className="flex items-center gap-2 text-slate-400">
                        <stat.icon className="h-4 w-4 text-cyan-300" />
                        <span className="text-xs uppercase tracking-[0.2em]">{stat.label}</span>
                      </div>
                      <div className="mt-2 text-lg font-semibold text-white">{stat.value}</div>
                    </div>
                  ))}
                </div>
              </GlassCard>
            </motion.div>
          </motion.section>

          <motion.section
            id="features"
            variants={pageTransition}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, amount: 0.25 }}
            className="py-10 lg:py-14"
          >
            <SectionHeading
              label="Capabilities"
              title="Built like a premium AI product, not a template."
              description="Every section is designed to read cleanly at a glance: high contrast, clear hierarchy, and subtle motion that reinforces the product story."
            />

            <div className="mt-10 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
              {featureCards.map((card) => (
                <motion.div key={card.title} variants={riseIn}>
                  <GlassCard className="h-full">
                    <card.icon className="h-6 w-6 text-cyan-300" />
                    <h3 className="mt-5 text-xl font-semibold text-white">{card.title}</h3>
                    <p className="mt-3 text-sm leading-7 text-slate-300">{card.description}</p>
                  </GlassCard>
                </motion.div>
              ))}
            </div>
          </motion.section>

          <motion.section
            id="dashboard-preview"
            variants={pageTransition}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, amount: 0.24 }}
            className="py-14 lg:py-20"
          >
            <SectionHeading
              label="Dashboard preview"
              title="A dense information surface that still feels effortless."
              description="Charts, scorecards, and table-style evidence are arranged with enough breathing room to stay legible in a demo, on a laptop, or on a projector."
            />

            <div className="mt-10 grid gap-5 lg:grid-cols-[1.15fr_0.85fr]">
              <GlassCard className="p-0">
                <div className="border-b border-white/10 px-5 py-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Operational overview</p>
                      <h3 className="mt-2 text-2xl font-semibold text-white">Global supply picture</h3>
                    </div>
                    <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-slate-200">
                      <TrendingUp className="h-3.5 w-3.5 text-emerald-300" />
                      Trending up
                    </div>
                  </div>
                </div>

                <div className="grid gap-4 p-5 xl:grid-cols-[1.1fr_0.9fr]">
                  <div className="rounded-[1.4rem] border border-white/10 bg-slate-950/55 p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-slate-400">Signal density</p>
                        <h4 className="mt-1 text-2xl font-semibold text-white">High confidence lane</h4>
                      </div>
                      <div className="rounded-full bg-violet-400/10 px-3 py-1 text-xs font-semibold text-violet-200">
                        96 / 100
                      </div>
                    </div>

                    <div className="mt-5 grid grid-cols-3 gap-3">
                      {[
                        ["Incoming", "142"],
                        ["Risk", "09"],
                        ["Resolved", "118"],
                      ].map(([label, value]) => (
                        <div key={label} className="rounded-2xl border border-white/10 bg-white/5 p-3">
                          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</p>
                          <p className="mt-2 text-xl font-semibold text-white">{value}</p>
                        </div>
                      ))}
                    </div>

                    <div className="mt-5 rounded-3xl border border-white/10 bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.12),_transparent_65%)] p-4">
                      <div className="flex items-end justify-between gap-4">
                        <div>
                          <p className="text-sm text-slate-400">Processing time</p>
                          <div className="mt-1 text-4xl font-semibold tracking-tight text-white">2.4s</div>
                        </div>
                        <div className="h-20 w-32 rounded-2xl border border-white/10 bg-slate-950/55 p-2">
                          <div className="flex h-full items-end gap-1.5">
                            {[38, 62, 44, 71, 58, 83, 67, 91].map((height, index) => (
                              <span
                                key={`${height}-${index}`}
                                className="w-full rounded-full bg-gradient-to-t from-cyan-500 via-blue-500 to-violet-400"
                                style={{ height: `${height}%` }}
                              />
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="rounded-[1.4rem] border border-white/10 bg-white/5 p-4">
                      <div className="flex items-center justify-between">
                        <h4 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">
                          Latest signals
                        </h4>
                        <BadgeCheck className="h-4 w-4 text-emerald-300" />
                      </div>
                      <div className="mt-4 space-y-3">
                        {dashboardRows.map((row) => (
                          <div
                            key={row.route}
                            className="flex items-center justify-between rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3"
                          >
                            <div>
                              <p className="text-sm font-medium text-white">{row.route}</p>
                              <p className="text-xs text-slate-400">{row.signal}</p>
                            </div>
                            <span className="rounded-full bg-cyan-400/10 px-3 py-1 text-xs font-semibold text-cyan-200">
                              {row.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-[1.4rem] border border-white/10 bg-slate-950/55 p-4">
                      <div className="flex items-center gap-3">
                        <div className="grid h-12 w-12 place-items-center rounded-2xl bg-cyan-400/10 text-cyan-200">
                          <ShieldCheck className="h-5 w-5" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-white">Provenance-first evidence</p>
                          <p className="text-sm text-slate-400">
                            Every scorecard links to traceable sources and role-aware access.
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </GlassCard>

              <div className="grid gap-5">
                {featureStats.map((stat) => (
                  <GlassCard key={stat.label} className="p-5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="grid h-11 w-11 place-items-center rounded-2xl bg-white/5 text-cyan-200">
                          <stat.icon className="h-5 w-5" />
                        </div>
                        <div>
                          <p className="text-sm text-slate-400">{stat.label}</p>
                          <p className="text-2xl font-semibold text-white">{stat.value}</p>
                        </div>
                      </div>
                      <ChevronRight className="h-4 w-4 text-slate-500" />
                    </div>
                  </GlassCard>
                ))}
              </div>
            </div>
          </motion.section>

          <motion.section
            id="trust"
            variants={pageTransition}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, amount: 0.24 }}
            className="py-14 lg:py-20"
          >
            <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
              <SectionHeading
                label="Trust"
                title="Designed to feel credible in the first five seconds."
                description="A strong public-facing landing page should communicate seriousness before the user has time to think about the technology behind it."
              />

              <div className="grid gap-4 md:grid-cols-2">
                {testimonials.map((testimonial, index) => (
                  <motion.div key={testimonial.name} variants={riseIn} className={index === 2 ? "md:col-span-2" : ""}>
                    <GlassCard className="h-full">
                      <MessageQuote />
                      <p className="mt-4 text-sm leading-7 text-slate-300">{testimonial.quote}</p>
                      <div className="mt-6 flex items-center gap-3">
                        <div className="grid h-11 w-11 place-items-center rounded-full bg-gradient-to-br from-cyan-400 via-blue-500 to-violet-500 text-sm font-semibold text-white">
                          {testimonial.name
                            .split(" ")
                            .map((part) => part[0])
                            .join("")}
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-white">{testimonial.name}</p>
                          <p className="text-sm text-slate-400">{testimonial.role}</p>
                        </div>
                      </div>
                    </GlassCard>
                  </motion.div>
                ))}
              </div>
            </div>

            <div className="mt-10 rounded-[1.8rem] border border-white/10 bg-white/5 px-5 py-5 backdrop-blur-2xl">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">
                    Trusted by teams shipping real workflows
                  </p>
                  <div className="mt-4 flex flex-wrap gap-3">
                    {trustMarks.map((mark) => (
                      <span
                        key={mark}
                        className="rounded-full border border-white/10 bg-slate-950/60 px-4 py-2 text-sm text-slate-200"
                      >
                        {mark}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="flex flex-col gap-3 sm:flex-row">
                  <GradientButton to={primaryCta} icon={<ArrowRight className="h-4 w-4" />}>
                    {auth.isAuthenticated ? "Open workspace" : "Start securely"}
                  </GradientButton>
                  <a
                    href="#features"
                    className="inline-flex items-center justify-center gap-2 rounded-full border border-white/[0.12] bg-white/5 px-5 py-3 text-sm font-semibold text-white backdrop-blur-xl transition hover:border-white/20 hover:bg-white/10"
                  >
                    <Users className="h-4 w-4" />
                    Review capabilities
                  </a>
                </div>
              </div>
            </div>
          </motion.section>
        </main>

        <footer className="border-t border-white/10 py-6 text-sm text-slate-500">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p>SupplyChainNexus. Premium intelligence for supply-chain operations.</p>
            <div className="flex items-center gap-4">
              <a href="#features" className="transition hover:text-slate-200">
                Features
              </a>
              <a href="#dashboard-preview" className="transition hover:text-slate-200">
                Dashboard
              </a>
              <a href="#trust" className="transition hover:text-slate-200">
                Proof
              </a>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
