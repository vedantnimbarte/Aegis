"use client";

// Switches which organization the app is acting in.
//
// Renders nothing when the user belongs to exactly one — most customers are a
// single team and should never have to think about this. It appears when
// somebody is in more than one, which in practice means an agency operating
// client workspaces.

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, ChevronDown } from "lucide-react";

import { api } from "@/lib/api";
import { getActiveOrg, setActiveOrg } from "@/lib/org";

export function OrgSwitcher() {
  const queryClient = useQueryClient();
  const orgsQuery = useQuery({ queryKey: ["orgs"], queryFn: () => api.listOrgs() });

  const orgs = orgsQuery.data ?? [];
  if (orgs.length < 2) return null;

  const active = getActiveOrg();
  const current = orgs.find((o) => o.slug === active || o.id === active) ?? orgs[0];

  const onChange = (slug: string) => {
    setActiveOrg(slug);
    // Every cached list is scoped to the old organization, so none of it
    // survives the switch.
    queryClient.clear();
  };

  return (
    <label className="relative flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2">
      <Building2 className="h-3.5 w-3.5 shrink-0 text-cyan-soft" strokeWidth={2} />
      <span className="sr-only">Active organization</span>
      <select
        value={current.slug}
        onChange={(e) => onChange(e.target.value)}
        className="w-full appearance-none bg-transparent pr-4 text-[12px] text-fg focus:outline-none"
      >
        {orgs.map((org) => (
          <option key={org.id} value={org.slug}>
            {org.name}
            {org.is_client_workspace ? " (client)" : ""}
          </option>
        ))}
      </select>
      <ChevronDown
        className="pointer-events-none absolute right-2.5 h-3.5 w-3.5 text-faint"
        strokeWidth={2}
      />
    </label>
  );
}
