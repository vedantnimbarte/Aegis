"use client";

// Client-side route protection. Redirects to /login when there is no session,
// and back to the dashboard shell once one exists. Auth state is only known on
// the client (tokens live in localStorage), so we gate rendering on mount.

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { useAuth } from "@/lib/auth";
import { AuthExpiredError } from "@/lib/api";
import { Spinner } from "./ui";

export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (mounted && !isAuthenticated) router.replace("/login");
  }, [mounted, isAuthenticated, router]);

  if (!mounted) {
    return (
      <div className="min-h-screen bg-obsidian">
        <Spinner />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-obsidian">
        <Spinner label="Redirecting to sign in…" />
      </div>
    );
  }

  return <>{children}</>;
}

/** Re-export so pages can narrow on session-expiry errors if needed. */
export { AuthExpiredError };
