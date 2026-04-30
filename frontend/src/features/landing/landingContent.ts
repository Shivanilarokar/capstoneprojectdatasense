import {
  Activity,
  BarChart3,
  BrainCircuit,
  Database,
  LineChart,
  Lock,
  MessagesSquare,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";

export const heroStats = [
  { value: "18.7M", label: "records indexed", tone: "from-cyan-400 to-blue-500" },
  { value: "2.4s", label: "median answer time", tone: "from-violet-400 to-fuchsia-500" },
  { value: "99.98%", label: "route health", tone: "from-emerald-400 to-cyan-400" },
] as const;

export const featureCards = [
  {
    icon: BrainCircuit,
    title: "Reasoning layer",
    description:
      "A guided orchestration surface that turns fragmented signals into investor-grade operational decisions.",
  },
  {
    icon: Database,
    title: "Multi-source evidence",
    description:
      "SEC, sanctions, weather, and trade data are stitched into one trusted context window without clutter.",
  },
  {
    icon: Workflow,
    title: "Route intelligence",
    description:
      "Every query, graph, and admin workflow stays tenant-aware while maintaining a polished product feel.",
  },
  {
    icon: ShieldCheck,
    title: "Policy-grade trust",
    description:
      "Clear provenance, guardrails, and role-based visibility keep the experience enterprise-ready.",
  },
] as const;

export const operationalSignals = [
  { label: "Live anomaly watch", value: "12 flags", change: "+18%", accent: "text-cyan-300" },
  { label: "Graph expansion", value: "3.6k nodes", change: "+24%", accent: "text-violet-300" },
  { label: "Precision score", value: "96.4%", change: "+3.1%", accent: "text-emerald-300" },
] as const;

export const trustMarks = ["Northstar Freight", "Helix Supply", "Aster Cargo", "Vector Trade"] as const;

export const testimonials = [
  {
    quote:
      "The interface feels like a premium internal AI product, not a demo shell. The hierarchy and motion make the value obvious immediately.",
    name: "Maya Chen",
    role: "VP Operations, Northstar Freight",
  },
  {
    quote:
      "The dashboard preview communicates depth without crowding the page. It would hold up in front of a board or investor.",
    name: "Jordan Blake",
    role: "Director of Product, Helix Supply",
  },
  {
    quote:
      "Strong visual structure, crisp typography, and the right amount of glow. It reads as a serious platform, not a marketing site.",
    name: "Sofia Ramirez",
    role: "Founder, Vector Trade",
  },
] as const;

export const dashboardRows = [
  { route: "Ocean lane risk", signal: "Weather spike", status: "Stable" },
  { route: "Supplier cluster", signal: "OFAC delta", status: "Watch" },
  { route: "Inbound ETA", signal: "Delay forecast", status: "Mitigated" },
] as const;

export const sparkPoints = [
  [0, 82],
  [12, 78],
  [24, 84],
  [36, 69],
  [48, 72],
  [60, 58],
  [72, 64],
  [84, 49],
  [96, 54],
  [108, 42],
  [120, 46],
] as const;

export const featureStats = [
  { icon: BarChart3, label: "Realtime coverage", value: "94%" },
  { icon: LineChart, label: "Forecast confidence", value: "91.2" },
  { icon: MessagesSquare, label: "Active workflows", value: "128" },
  { icon: Lock, label: "Permission layers", value: "6" },
  { icon: Activity, label: "Signals monitored", value: "42" },
  { icon: Sparkles, label: "Human review rate", value: "11%" },
] as const;
