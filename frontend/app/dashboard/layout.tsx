"use client";

import { useState, type ComponentType } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FolderGit2,
  ScanLine,
  Plus,
  LogOut,
  Menu,
  X,
} from "lucide-react";
import { AegisMark, cx, btn } from "@/components/aegis/kit";

type NavItem = {
  href: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  exact?: boolean;
};

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/dashboard/repos", label: "Repositories", icon: FolderGit2 },
  { href: "/dashboard/scans", label: "Scan History", icon: ScanLine },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname === href || pathname.startsWith(href + "/");

  return (
    <div className="min-h-screen bg-obsidian">
      {/* Mobile top bar */}
      <div className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-line bg-obsidian/90 px-4 backdrop-blur md:hidden">
        <Link href="/dashboard" className="flex items-center gap-2.5">
          <AegisMark size={30} />
          <span className="font-display text-[15px] font-semibold text-fg">Aegis</span>
        </Link>
        <button
          onClick={() => setOpen(true)}
          className="grid h-9 w-9 place-items-center rounded-lg border border-line text-muted"
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </button>
      </div>

      {/* Scrim (mobile) */}
      {open && (
        <button
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-40 bg-black/60 md:hidden"
        />
      )}

      {/* Sidebar */}
      <aside
        className={cx(
          "fixed inset-y-0 left-0 z-50 flex w-[264px] flex-col border-r border-line bg-ink transition-transform duration-200 md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center justify-between border-b border-line px-5">
          <Link
            href="/dashboard"
            className="flex items-center gap-2.5"
            onClick={() => setOpen(false)}
          >
            <AegisMark />
            <span className="leading-tight">
              <span className="block font-display text-base font-semibold tracking-tight text-fg">
                Aegis
              </span>
              <span className="block font-mono text-[10px] uppercase tracking-[0.18em] text-faint">
                Threat Console
              </span>
            </span>
          </Link>
          <button
            onClick={() => setOpen(false)}
            className="grid h-8 w-8 place-items-center rounded-md text-muted hover:text-fg md:hidden"
            aria-label="Close navigation"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-3 pt-4">
          <button className={cx(btn.primary, "w-full")}>
            <Plus className="h-4 w-4" />
            New scan
          </button>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-5">
          <p className="px-3 pb-2 font-mono text-[10px] uppercase tracking-[0.18em] text-faint">
            Monitoring
          </p>
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href, item.exact);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                aria-current={active ? "page" : undefined}
                className={cx(
                  "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-violet/10 text-fg"
                    : "text-muted hover:bg-surface hover:text-fg",
                )}
              >
                {active && (
                  <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full bg-violet" />
                )}
                <Icon
                  className={cx(
                    "h-[18px] w-[18px] transition-colors",
                    active ? "text-violet-soft" : "text-faint group-hover:text-muted",
                  )}
                />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* User / logout */}
        <div className="border-t border-line p-3">
          <div className="flex items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-surface">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-raised font-mono text-[13px] font-semibold text-violet-soft">
              VN
            </span>
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block truncate text-sm font-medium text-fg">
                Vedant Nimbarte
              </span>
              <span className="block truncate font-mono text-[11px] text-faint">
                marketing@cloudairy.com
              </span>
            </span>
            <button
              className="grid h-8 w-8 shrink-0 place-items-center rounded-md text-faint transition-colors hover:bg-raised hover:text-danger"
              aria-label="Log out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Content */}
      <div className="md:pl-[264px]">
        <main className="mx-auto max-w-[1200px] px-5 py-7 md:px-9 md:py-10">
          {children}
        </main>
      </div>
    </div>
  );
}
