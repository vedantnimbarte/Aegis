"use client";

// The primary "New scan" call-to-action, with subscription/target gating
// baked in so callers don't repeat the logic:
//   - no active subscription -> "Upgrade to scan" (→ /billing)
//   - no connected targets   -> "Add a target" (→ /targets)
//   - otherwise              -> opens the New scan dialog

import { Crosshair, Plus, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/lib/auth";
import type { Target } from "@/lib/types";
import { Button, cn } from "./ui";
import { NewScanDialog } from "./NewScanDialog";

const linkClasses =
  "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 font-display text-[13px] font-semibold transition-all";

export function NewScanAction({
  targets,
  label = "New scan",
  className,
}: {
  targets: Target[];
  label?: string;
  className?: string;
}) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);

  // Gate on subscription first — this is the whole point of the billing tier.
  if (user && !user.has_active_subscription) {
    return (
      <Link
        href="/billing"
        className={cn(linkClasses, "bg-cyan text-obsidian shadow-lg shadow-cyan/20 hover:bg-cyan-soft", className)}
      >
        <Sparkles className="h-4 w-4" strokeWidth={2} />
        Upgrade to scan
      </Link>
    );
  }

  if (targets.length === 0) {
    return (
      <Link
        href="/targets"
        className={cn(linkClasses, "border border-line bg-surface/80 text-fg hover:border-cyan/40", className)}
      >
        <Crosshair className="h-4 w-4" strokeWidth={2} />
        Add a target
      </Link>
    );
  }

  return (
    <>
      <Button icon={Plus} className={className} onClick={() => setOpen(true)}>
        {label}
      </Button>
      {open ? <NewScanDialog targets={targets} onClose={() => setOpen(false)} /> : null}
    </>
  );
}
