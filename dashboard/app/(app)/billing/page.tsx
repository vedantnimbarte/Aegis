"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CreditCard, ExternalLink, Loader2, Sparkles } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

import { Button, Card, ErrorState, PageHeader, Pill, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { Plan, SubscriptionStatus, SubscriptionTier } from "@/lib/types";

const STATUS_LABEL: Record<SubscriptionStatus, { label: string; pill: string }> = {
  none: { label: "No subscription", pill: "border-line bg-surface text-muted" },
  trialing: { label: "Trialing", pill: "border-cyan/30 bg-cyan/10 text-cyan-soft" },
  active: { label: "Active", pill: "border-signal/30 bg-signal/10 text-signal" },
  past_due: { label: "Past due", pill: "border-amber/30 bg-amber/10 text-amber" },
  canceled: { label: "Canceled", pill: "border-danger/30 bg-danger/10 text-danger" },
  incomplete: { label: "Incomplete", pill: "border-amber/30 bg-amber/10 text-amber" },
};

function BillingInner() {
  const router = useRouter();
  const params = useSearchParams();
  const queryClient = useQueryClient();

  const checkoutResult = params.get("checkout");

  const summaryQuery = useQuery({
    queryKey: ["billing", "summary"],
    queryFn: api.billingSummary,
  });

  // Returning from Checkout: refetch so the (webhook-updated) plan shows.
  useEffect(() => {
    if (checkoutResult) {
      queryClient.invalidateQueries({ queryKey: ["billing", "summary"] });
      queryClient.invalidateQueries({ queryKey: ["me"] });
    }
  }, [checkoutResult, queryClient]);

  const subscribe = useMutation({
    mutationFn: (tier: SubscriptionTier) => api.checkout(tier),
    onSuccess: ({ checkout_url }) => {
      window.location.href = checkout_url;
    },
  });

  const portal = useMutation({
    mutationFn: () => api.billingPortal(),
    onSuccess: ({ portal_url }) => {
      window.location.href = portal_url;
    },
  });

  if (summaryQuery.isLoading) return <Spinner label="Loading billing…" />;
  if (summaryQuery.error || !summaryQuery.data)
    return <ErrorState message="Could not load billing information." />;

  const s = summaryQuery.data;
  const status = STATUS_LABEL[s.status];
  const actionError =
    subscribe.error instanceof ApiError
      ? subscribe.error.message
      : portal.error instanceof ApiError
        ? portal.error.message
        : null;

  return (
    <>
      <PageHeader title="Billing" subtitle="Manage your subscription and usage." />

      {checkoutResult === "success" ? (
        <div className="mb-6 flex items-center gap-3 rounded-xl border border-signal/30 bg-signal/[0.06] px-4 py-3.5 text-[13px] text-signal">
          <Check className="h-4 w-4 shrink-0" strokeWidth={2} />
          Subscription confirmed. It may take a few seconds for your plan to update here.
        </div>
      ) : checkoutResult === "cancelled" ? (
        <div className="mb-6 rounded-xl border border-line bg-surface/50 px-4 py-3.5 text-[13px] text-muted">
          Checkout was cancelled — no changes were made.
        </div>
      ) : null}

      {/* Current plan */}
      <Card className="mb-8 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-wide text-faint">Current plan</p>
            <div className="mt-1.5 flex items-center gap-2.5">
              <h2 className="font-display text-xl font-bold text-fg">{s.limits.name}</h2>
              <Pill tone={status.pill}>{status.label}</Pill>
            </div>
            {s.current_period_end && s.has_active_subscription ? (
              <p className="mt-1 text-[12px] text-muted">
                Renews {new Date(s.current_period_end).toLocaleDateString()}
              </p>
            ) : null}
          </div>
          {s.tier !== "free" ? (
            <Button variant="secondary" icon={CreditCard} loading={portal.isPending} onClick={() => portal.mutate()}>
              Manage billing
            </Button>
          ) : null}
        </div>

        {/* Usage */}
        <div className="mt-5 grid gap-4 border-t border-line pt-5 sm:grid-cols-2">
          <UsageBar
            label="Scans this month"
            used={s.usage.scans_this_month}
            limit={s.limits.monthly_scans}
          />
          <UsageBar
            label="Connected repositories"
            used={s.usage.connected_repos}
            limit={s.limits.max_repos}
          />
        </div>
      </Card>

      {actionError ? (
        <div className="mb-6">
          <ErrorState message={actionError} />
        </div>
      ) : null}

      {/* Plan catalog */}
      <h2 className="mb-4 font-display text-[15px] font-semibold text-fg">Plans</h2>
      <div className="grid gap-3.5 sm:grid-cols-3">
        {s.plans.map((plan) => (
          <PlanCard
            key={plan.tier}
            plan={plan}
            current={plan.tier === s.tier && s.has_active_subscription}
            subscribing={subscribe.isPending && subscribe.variables === plan.tier}
            onSubscribe={() => subscribe.mutate(plan.tier)}
          />
        ))}
      </div>
    </>
  );
}

function UsageBar({ label, used, limit }: { label: string; used: number; limit: number | null }) {
  const pct = limit && limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  const atLimit = limit != null && used >= limit;
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-[12px]">
        <span className="text-muted">{label}</span>
        <span className="font-mono text-faint">
          {used} / {limit == null ? "∞" : limit}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-line">
        <div
          className="h-full rounded-full transition-all"
          style={{
            width: limit == null ? "8%" : `${pct}%`,
            backgroundColor: atLimit ? "#FB5C6B" : "#22D3EE",
          }}
        />
      </div>
    </div>
  );
}

function PlanCard({
  plan,
  current,
  subscribing,
  onSubscribe,
}: {
  plan: Plan;
  current: boolean;
  subscribing: boolean;
  onSubscribe: () => void;
}) {
  const features = [
    plan.max_repos == null ? "Unlimited repositories" : `${plan.max_repos} repositories`,
    plan.monthly_scans == null ? "Unlimited scans" : `${plan.monthly_scans} scans / month`,
  ];

  return (
    <Card className={"flex flex-col p-5" + (current ? " border-cyan/40" : "")}>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-display text-[15px] font-semibold text-fg">{plan.name}</h3>
        {current ? (
          <Pill tone="border-cyan/30 bg-cyan/10 text-cyan-soft">Current</Pill>
        ) : plan.tier === "pro" ? (
          <Sparkles className="h-4 w-4 text-cyan-soft" strokeWidth={1.75} />
        ) : null}
      </div>

      <ul className="mb-5 flex-1 space-y-2">
        {features.map((f) => (
          <li key={f} className="flex items-center gap-2 text-[13px] text-muted">
            <Check className="h-3.5 w-3.5 shrink-0 text-signal" strokeWidth={2.5} />
            {f}
          </li>
        ))}
      </ul>

      {current ? (
        <Button variant="secondary" disabled className="w-full">
          Current plan
        </Button>
      ) : plan.self_serve ? (
        plan.price_configured ? (
          <Button className="w-full" loading={subscribing} onClick={onSubscribe}>
            Subscribe
          </Button>
        ) : (
          <Button variant="secondary" disabled className="w-full">
            Unavailable
          </Button>
        )
      ) : (
        <a
          href="mailto:sales@aegis.security?subject=Aegis%20Enterprise"
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-line bg-surface/80 px-4 py-2.5 font-display text-[13px] font-semibold text-fg transition-colors hover:border-cyan/40"
        >
          Contact sales
          <ExternalLink className="h-3.5 w-3.5" strokeWidth={2} />
        </a>
      )}
    </Card>
  );
}

export default function BillingPage() {
  return (
    <Suspense fallback={<Spinner label="Loading billing…" />}>
      <BillingInner />
    </Suspense>
  );
}
