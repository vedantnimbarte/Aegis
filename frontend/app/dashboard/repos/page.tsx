import {
  Github,
  ExternalLink,
  Clock,
  Radar,
  Lock,
  Globe,
  ShieldAlert,
} from "lucide-react";
import { Card, Eyebrow, RepoStatusPill, btn, cx } from "@/components/aegis/kit";
import { repos } from "@/lib/mock-data";

export default function ReposPage() {
  const atRisk = repos.filter((r) => r.status === "at_risk").length;

  return (
    <>
      {/* Header */}
      <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <Eyebrow className="mb-2">
            {repos.length} connected · {atRisk} at risk
          </Eyebrow>
          <h1 className="font-display text-2xl font-semibold tracking-tight text-fg">
            Repositories
          </h1>
          <p className="mt-1.5 text-sm text-muted">
            Aegis re-tests each repo the moment its code changes.
          </p>
        </div>
        <button className={btn.primary}>
          <Github className="h-4 w-4" />
          Connect GitHub Repo
        </button>
      </header>

      {/* Repo grid */}
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {repos.map((repo) => {
          const [org, name] = repo.name.split("/");
          const Visibility = repo.visibility === "private" ? Lock : Globe;
          return (
            <Card
              key={repo.id}
              className="group flex flex-col p-5 transition-all hover:-translate-y-0.5 hover:border-violet/40"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 font-mono text-sm">
                    <span className="text-faint">{org}/</span>
                    <span className="truncate font-medium text-fg">{name}</span>
                  </div>
                  <a
                    href={repo.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1.5 inline-flex items-center gap-1 font-mono text-[11px] text-faint transition-colors hover:text-violet-soft"
                  >
                    {repo.url.replace("https://", "")}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
                <RepoStatusPill status={repo.status} />
              </div>

              {/* Meta grid */}
              <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-3.5 border-t border-line pt-4">
                <div>
                  <dt className="font-mono text-[10px] uppercase tracking-wider text-faint">
                    Language
                  </dt>
                  <dd className="mt-1 flex items-center gap-1.5 text-sm text-muted">
                    <span
                      className="h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: repo.langColor }}
                    />
                    {repo.language}
                  </dd>
                </div>
                <div>
                  <dt className="font-mono text-[10px] uppercase tracking-wider text-faint">
                    Visibility
                  </dt>
                  <dd className="mt-1 flex items-center gap-1.5 text-sm capitalize text-muted">
                    <Visibility className="h-3.5 w-3.5 text-faint" />
                    {repo.visibility}
                  </dd>
                </div>
                <div>
                  <dt className="font-mono text-[10px] uppercase tracking-wider text-faint">
                    Last scan
                  </dt>
                  <dd className="mt-1 flex items-center gap-1.5 font-mono text-xs text-muted">
                    <Clock className="h-3.5 w-3.5 text-faint" />
                    {repo.lastScanLabel ?? "Never"}
                  </dd>
                </div>
                <div>
                  <dt className="font-mono text-[10px] uppercase tracking-wider text-faint">
                    Open findings
                  </dt>
                  <dd
                    className={cx(
                      "mt-1 flex items-center gap-1.5 font-mono text-sm font-semibold",
                      repo.openFindings > 0 ? "text-sev-high" : "text-signal",
                    )}
                  >
                    <ShieldAlert className="h-3.5 w-3.5" />
                    {repo.openFindings}
                  </dd>
                </div>
              </dl>

              {/* Footer action */}
              <div className="mt-5 flex items-center gap-2">
                <button className={cx(btn.subtle, "flex-1")}>
                  <Radar className="h-3.5 w-3.5" />
                  Scan now
                </button>
              </div>
            </Card>
          );
        })}
      </section>
    </>
  );
}
