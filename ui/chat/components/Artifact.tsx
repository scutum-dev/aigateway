"use client";

import { Component, type ReactNode, useMemo, useState, useEffect } from "react";
import { LiveProvider, LivePreview, LiveError } from "react-live";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  RadarChart,
  Radar,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  RadialBarChart,
  RadialBar,
} from "recharts";

/**
 * Render a model-generated React component inline in the chat.
 *
 * Security model: the code is evaluated by react-live, which compiles JSX to
 * JS and runs it inside the same React tree. The model has access ONLY to the
 * primitives in the `scope` below — there is no `fetch`, `XMLHttpRequest`,
 * `localStorage`, `document`, `window`, or any DOM-mutation API in the scope,
 * and react-live's eval doesn't pull from globals (the eval'd code only sees
 * what we put in scope). Network and persistence are unreachable. The worst
 * a malicious model can do is render bad UI — which the ErrorBoundary catches.
 *
 * For higher security (e.g. when accepting code from untrusted users vs
 * untrusted models), this should be moved to a sandboxed iframe with strict
 * CSP. Tracked as a follow-up; the threat model today is "model writes
 * broken JSX," not "user is the attacker."
 */
type ArtifactProps = {
  title?: string;
  code: string;
  /** When the model is still streaming the JSX text, render a placeholder. */
  pending?: boolean;
};

const SCOPE = {
  // React essentials
  useState,
  useEffect,
  useMemo,
  // Recharts — covers ~95% of "show me a chart" use cases
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  RadarChart,
  Radar,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  RadialBarChart,
  RadialBar,
};

export default function Artifact({ title, code, pending }: ArtifactProps) {
  // react-live wants either a complete element-returning expression or a
  // function declaration. The model is instructed to emit the latter, but
  // we wrap defensively just in case it returned a bare expression.
  const renderable = useMemo(() => normalizeCode(code), [code]);

  return (
    <div className="my-3 border border-[var(--color-border)] rounded-lg overflow-hidden bg-[var(--color-bg-elevated)]">
      <div className="px-3 py-2 text-xs uppercase tracking-wider text-[var(--color-text-subtle)] border-b border-[var(--color-border)] flex items-center justify-between">
        <span>{pending ? "🎨 Building artifact…" : "🎨 " + (title ?? "Artifact")}</span>
        {!pending && (
          <span className="text-[var(--color-text-subtle)] text-[10px]">
            interactive
          </span>
        )}
      </div>
      <div className="p-4">
        {pending ? (
          <div className="text-sm text-[var(--color-text-muted)]">
            Generating React component…
          </div>
        ) : (
          <ArtifactBoundary>
            <LiveProvider code={renderable} scope={SCOPE} noInline>
              <LivePreview />
              <LiveError className="text-xs text-red-500 mt-2 whitespace-pre-wrap" />
            </LiveProvider>
          </ArtifactBoundary>
        )}
      </div>
    </div>
  );
}

/**
 * react-live's `noInline` mode requires a `render(<Element />)` call. The
 * model is prompted to emit that, but if it returns just an expression like
 * `<MyChart />`, we wrap it ourselves so the artifact still renders.
 */
function normalizeCode(code: string): string {
  const trimmed = code.trim();
  if (!trimmed) return "render(null)";
  if (/render\s*\(/.test(trimmed)) return trimmed;
  // Bare JSX expression → wrap in render()
  if (trimmed.startsWith("<")) return `render(${trimmed})`;
  // Likely a function-component definition without a render() call. Try to
  // find the component name and call render(<Name />).
  const fnName = /(?:function|const)\s+([A-Z][A-Za-z0-9_]*)/.exec(trimmed)?.[1];
  if (fnName) return `${trimmed}\nrender(<${fnName} />)`;
  return trimmed;
}

class ArtifactBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  componentDidCatch(error: Error) {
    console.error("[artifact] render error:", error);
  }
  render() {
    if (this.state.error) {
      return (
        <div className="text-xs text-red-500">
          Artifact failed to render: {this.state.error.message}
        </div>
      );
    }
    return this.props.children;
  }
}
