"use client";

// The primary "New scan" call-to-action, with subscription/repo gating baked
// in so callers don't repeat the logic:
//   - no active subscription  -> "Upgrade to scan" (→ /billing)
//   - no connected repos       -> "Connect a repository" (→ /repos)
//   - otherwise                -> opens the New scan dialog

import { GitBranch, Plus, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/lib/auth";
import type { Repository } from "@/lib/types";
import { Button, cn } from "./ui";
import { NewScanDialog } from "./NewScanDialog";

const linkClasses =
  "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 font-display text-[13px] font-semibold transition-all";

export function NewScanAction({
  repositories,
  label = "New scan",
  className,
}: {
  repositories: Repository[];
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

  if (repositories.length === 0) {
    return (
      <Link
        href="/repos"
        className={cn(linkClasses, "border border-line bg-surface/80 text-fg hover:border-cyan/40", className)}
      >
        <GitBranch className="h-4 w-4" strokeWidth={2} />
        Connect a repository
      </Link>
    );
  }

  return (
    <>
      <Button icon={Plus} className={className} onClick={() => setOpen(true)}>
        {label}
      </Button>
      {open ? <NewScanDialog repositories={repositories} onClose={() => setOpen(false)} /> : null}
    </>
  );
}
