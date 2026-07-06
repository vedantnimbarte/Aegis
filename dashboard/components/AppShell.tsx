"use client";

// The authenticated app chrome: a fixed sidebar nav + top bar with the user
// menu. Wraps every page under the (app) route group.

import {
  LayoutDashboard,
  GitBranch,
  Radar,
  ShieldHalf,
  LogOut,
  CreditCard,
  Settings,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { useAuth } from "@/lib/auth";
import { cn } from "./ui";
import { VerifyEmailBanner } from "./VerifyEmailBanner";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard, exact: true },
  { href: "/repos", label: "Repositories", icon: GitBranch, exact: false },
  { href: "/scans", label: "Scans", icon: Radar, exact: false },
  { href: "/billing", label: "Billing", icon: CreditCard, exact: false },
  { href: "/settings", label: "Settings", icon: Settings, exact: false },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const isActive = (href: string, exact: boolean) =>
    exact ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <div className="flex min-h-screen bg-obsidian">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col border-r border-line bg-ink/80 backdrop-blur lg:flex">
        <Link href="/" className="flex items-center gap-2.5 px-5 py-5">
          <span className="grid h-8 w-8 place-items-center rounded-lg border border-cyan/40 bg-cyan/10 text-cyan-soft">
            <ShieldHalf className="h-4 w-4" strokeWidth={2} />
          </span>
          <span className="font-display text-[15px] font-semibold tracking-tight text-fg">
            Aegis
          </span>
        </Link>

        <nav className="mt-2 flex flex-1 flex-col gap-1 px-3">
          {NAV.map(({ href, label, icon: Icon, exact }) => {
            const active = isActive(href, exact);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-medium transition-colors",
                  active
                    ? "bg-cyan/10 text-cyan-soft"
                    : "text-muted hover:bg-surface/70 hover:text-fg"
                )}
              >
                <Icon className="h-4 w-4" strokeWidth={2} />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-line p-3">
          <div className="flex items-center gap-3 rounded-lg px-3 py-2">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-line bg-surface font-mono text-[12px] uppercase text-cyan-soft">
              {(user?.email ?? "?").charAt(0)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-[12px] font-medium text-fg">
                {user?.github_username ?? user?.email ?? "Signed in"}
              </p>
              <p className="truncate font-mono text-[10px] uppercase tracking-wide text-faint">
                {user?.subscription_tier ?? "free"} plan
              </p>
            </div>
            <button
              onClick={logout}
              aria-label="Sign out"
              className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-faint transition-colors hover:bg-surface hover:text-danger"
            >
              <LogOut className="h-4 w-4" strokeWidth={2} />
            </button>
          </div>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="fixed inset-x-0 top-0 z-20 flex items-center justify-between border-b border-line bg-ink/90 px-4 py-3 backdrop-blur lg:hidden">
        <Link href="/" className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-lg border border-cyan/40 bg-cyan/10 text-cyan-soft">
            <ShieldHalf className="h-3.5 w-3.5" strokeWidth={2} />
          </span>
          <span className="font-display text-sm font-semibold text-fg">Aegis</span>
        </Link>
        <nav className="flex items-center gap-1">
          {NAV.map(({ href, label, icon: Icon, exact }) => (
            <Link
              key={href}
              href={href}
              aria-label={label}
              className={cn(
                "grid h-9 w-9 place-items-center rounded-lg transition-colors",
                isActive(href, exact) ? "bg-cyan/10 text-cyan-soft" : "text-muted hover:text-fg"
              )}
            >
              <Icon className="h-4 w-4" strokeWidth={2} />
            </Link>
          ))}
          <button
            onClick={logout}
            aria-label="Sign out"
            className="grid h-9 w-9 place-items-center rounded-lg text-faint hover:text-danger"
          >
            <LogOut className="h-4 w-4" strokeWidth={2} />
          </button>
        </nav>
      </div>

      {/* Main content */}
      <main className="flex-1 px-5 pb-16 pt-20 sm:px-8 lg:ml-60 lg:pt-10">
        <div className="mx-auto max-w-5xl">
          <VerifyEmailBanner />
          {children}
        </div>
      </main>
    </div>
  );
}
