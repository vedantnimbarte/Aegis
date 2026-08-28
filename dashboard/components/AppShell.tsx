"use client";

// The authenticated app chrome: a fixed sidebar nav + top bar with the user
// menu. Wraps every page under the (app) route group.

import {
  LayoutDashboard,
  Crosshair,
  Radar,
  LogOut,
  CreditCard,
  Receipt,
  Settings,
  Users,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { useAuth } from "@/lib/auth";
import { cn } from "./ui";
import { OrgSwitcher } from "./OrgSwitcher";
import { VerifyEmailBanner } from "./VerifyEmailBanner";

// `short` is the tab-bar label — the sidebar has room for the full wording.
const NAV = [
  { href: "/", label: "Overview", short: "Overview", icon: LayoutDashboard, exact: true },
  { href: "/targets", label: "Targets", short: "Targets", icon: Crosshair, exact: false },
  { href: "/scans", label: "Scans", short: "Scans", icon: Radar, exact: false },
  { href: "/team", label: "Team", short: "Team", icon: Users, exact: false },
  { href: "/costs", label: "Costs", short: "Costs", icon: Receipt, exact: false },
  { href: "/billing", label: "Billing", short: "Billing", icon: CreditCard, exact: false },
  { href: "/settings", label: "Settings", short: "Settings", icon: Settings, exact: false },
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
          <span className="grid h-8 w-8 place-items-center rounded-lg border border-cyan/40 bg-cyan/10">
            <Image src="/logo.png" alt="" width={20} height={20} priority />
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

        <div className="space-y-2 border-t border-line p-3">
          <OrgSwitcher />
          <div className="flex items-center gap-3 rounded-lg px-1 py-1">
            <Link
              href="/account"
              aria-label="Account settings"
              className="flex min-w-0 flex-1 items-center gap-3 rounded-lg px-2 py-1.5 transition-colors hover:bg-surface/70"
            >
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-line bg-surface font-mono text-[12px] uppercase text-cyan-soft">
                {(user?.display_name ?? user?.email ?? "?").charAt(0)}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[12px] font-medium text-fg">
                  {user?.display_name ?? user?.github_username ?? user?.email ?? "Signed in"}
                </p>
                <p className="truncate font-mono text-[10px] uppercase tracking-wide text-faint">
                  {user?.subscription_tier ?? "free"} plan
                </p>
              </div>
            </Link>
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

      {/* Mobile top bar — identity and sign-out only; navigation lives in the
          bottom tab bar, where the labels fit and the targets are reachable. */}
      <div className="fixed inset-x-0 top-0 z-20 flex items-center justify-between border-b border-line bg-ink/90 px-4 py-3 backdrop-blur lg:hidden">
        <Link href="/" className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-lg border border-cyan/40 bg-cyan/10">
            <Image src="/logo.png" alt="" width={18} height={18} priority />
          </span>
          <span className="font-display text-sm font-semibold text-fg">Aegis</span>
        </Link>
        <div className="flex items-center gap-2">
          <span className="max-w-[9rem] truncate font-mono text-[11px] text-faint">
            {user?.github_username ?? user?.email ?? ""}
          </span>
          <button
            onClick={logout}
            aria-label="Sign out"
            className="grid h-9 w-9 place-items-center rounded-lg text-faint transition-colors hover:text-danger"
          >
            <LogOut className="h-4 w-4" strokeWidth={2} />
          </button>
        </div>
      </div>

      {/* Mobile bottom tab bar */}
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-20 flex border-t border-line bg-ink/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
      >
        {NAV.map(({ href, label, short, icon: Icon, exact }) => {
          const active = isActive(href, exact);
          return (
            <Link
              key={href}
              href={href}
              aria-label={label}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex flex-1 flex-col items-center gap-1 px-1 py-2.5 transition-colors",
                active ? "text-cyan-soft" : "text-muted"
              )}
            >
              <Icon className="h-[18px] w-[18px]" strokeWidth={2} />
              <span className="text-[10px] font-medium leading-none">{short}</span>
            </Link>
          );
        })}
      </nav>

      {/* Main content */}
      <main className="flex-1 px-5 pb-28 pt-20 sm:px-8 lg:ml-60 lg:pb-16 lg:pt-10">
        <div className="mx-auto max-w-5xl">
          <VerifyEmailBanner />
          {children}
        </div>
      </main>
    </div>
  );
}
