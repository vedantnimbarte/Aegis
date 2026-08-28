// The Aegis API surface, as typed methods. Transport (auth, refresh-retry,
// the organization header) lives in ./api; this file is only the endpoints.

import { request, requestBlob } from "./api-transport";
import type {
  ApiToken,
  ApiTokenCreated,
  AuditEvent,
  BillingSummary,
  CostSummary,
  DashboardSummary,
  GitHubAppInfo,
  GitProvider,
  GreyboxConfig,
  Installation,
  IssueTracker,
  Member,
  Organization,
  OrgRole,
  ReportShare,
  ReportShareCreated,
  Scan,
  ScanFrequency,
  ScanMode,
  ScanProgress,
  ScanReport,
  Schedule,
  SourceRepo,
  SubscriptionTier,
  Target,
  TargetKind,
  Token,
  TriageStatus,
  User,
  Vulnerability,
} from "./types";

export const api = {
  // --- Auth ---
  register: (email: string, password: string) =>
    request<Token>("/auth/register", {
      method: "POST",
      body: { email, password },
      auth: false,
    }),
  login: (email: string, password: string) =>
    request<Token>("/auth/login", {
      method: "POST",
      body: { email, password },
      auth: false,
    }),
  forgotPassword: (email: string) =>
    request<{ detail: string }>("/auth/forgot-password", {
      method: "POST",
      body: { email },
      auth: false,
    }),
  resetPassword: (token: string, new_password: string) =>
    request<Token>("/auth/reset-password", {
      method: "POST",
      body: { token, new_password },
      auth: false,
    }),
  verifyEmail: (token: string) =>
    request<{ detail: string }>("/auth/verify-email", {
      method: "POST",
      body: { token },
      auth: false,
    }),
  resendVerification: () =>
    request<{ detail: string }>("/auth/resend-verification", { method: "POST" }),
  githubAuth: (code: string, redirect_uri?: string, state?: string) =>
    request<Token>("/auth/github", {
      method: "POST",
      body: { code, redirect_uri, state },
      auth: false,
    }),

  // --- User ---
  me: () => request<User>("/users/me"),
  acceptScanTerms: () =>
    request<User>("/users/me/accept-scan-terms", { method: "POST" }),
  updateIntegrations: (body: {
    llm_model?: string | null;
    llm_api_key?: string | null;
    slack_webhook_url?: string | null;
    webhook_url?: string | null;
    webhook_secret?: string | null;
    gitlab_token?: string | null;
    bitbucket_token?: string | null;
    jira_url?: string | null;
    jira_email?: string | null;
    jira_api_token?: string | null;
    jira_project_key?: string | null;
    linear_api_key?: string | null;
    linear_team_id?: string | null;
  }) => request<User>("/users/me/integrations", { method: "PATCH", body }),

  // --- Organizations ---
  listOrgs: () => request<Organization[]>("/orgs"),
  createOrg: (body: { name: string; parent_id?: string | null }) =>
    request<Organization>("/orgs", { method: "POST", body }),
  currentOrg: () => request<Organization>("/orgs/current"),
  updateOrg: (body: {
    name?: string;
    brand_name?: string | null;
    brand_primary_color?: string | null;
  }) => request<Organization>("/orgs/current", { method: "PATCH", body }),
  listMembers: () => request<Member[]>("/orgs/current/members"),
  addMember: (body: { email: string; role: OrgRole }) =>
    request<Member>("/orgs/current/members", { method: "POST", body }),
  updateMemberRole: (membershipId: string, role: OrgRole) =>
    request<Member>("/orgs/current/members/" + membershipId, {
      method: "PATCH",
      body: { role },
    }),
  removeMember: (membershipId: string) =>
    request<void>("/orgs/current/members/" + membershipId, { method: "DELETE" }),
  listAuditEvents: (limit = 100) =>
    request<AuditEvent[]>("/orgs/current/audit?limit=" + limit),
  listApiTokens: () => request<ApiToken[]>("/orgs/current/tokens"),
  createApiToken: (body: {
    name: string;
    role: OrgRole;
    expires_in_days?: number | null;
  }) => request<ApiTokenCreated>("/orgs/current/tokens", { method: "POST", body }),
  revokeApiToken: (id: string) =>
    request<void>("/orgs/current/tokens/" + id, { method: "DELETE" }),

  // --- Targets ---
  listTargets: (kind?: TargetKind) =>
    request<Target[]>(kind ? "/targets?kind=" + kind : "/targets"),
  getTarget: (id: string) => request<Target>("/targets/" + id),
  listAvailableRepos: (provider: GitProvider = "github") =>
    request<SourceRepo[]>("/targets/available?provider=" + provider),
  connectRepo: (body: {
    provider: GitProvider;
    external_repo_id: string;
    name: string;
    clone_url: string;
  }) => request<Target>("/targets/repos", { method: "POST", body }),
  createTarget: (body: {
    kind: TargetKind;
    name?: string | null;
    url?: string | null;
    openapi_url?: string | null;
    max_budget_usd?: number | null;
    discovery_enabled?: boolean;
  }) => request<Target>("/targets", { method: "POST", body }),
  updateTarget: (
    id: string,
    body: {
      name?: string;
      url?: string | null;
      openapi_url?: string | null;
      max_budget_usd?: number | null;
      gate_fail_severities?: string | null;
      gate_new_findings_only?: boolean;
      discovery_enabled?: boolean;
    }
  ) => request<Target>("/targets/" + id, { method: "PATCH", body }),
  deleteTarget: (id: string) =>
    request<void>("/targets/" + id, { method: "DELETE" }),
  getDerivedSpec: (id: string) =>
    request<Record<string, unknown>>("/targets/" + id + "/spec"),

  // --- Overview ---
  dashboardSummary: (allOrganizations = false) =>
    request<DashboardSummary>(
      allOrganizations
        ? "/dashboard/summary?all_organizations=true"
        : "/dashboard/summary"
    ),
  costSummary: () => request<CostSummary>("/dashboard/costs"),

  // --- Scans ---
  listScans: (targetId?: string) =>
    request<Scan[]>(
      targetId ? "/scans?target_id=" + encodeURIComponent(targetId) : "/scans"
    ),
  createScan: (body: {
    target_id: string;
    scan_mode: ScanMode;
    custom_instructions?: string | null;
  }) => request<Scan>("/scans", { method: "POST", body }),
  getScan: (id: string) => request<Scan>("/scans/" + id),
  getReport: (id: string) => request<ScanReport>("/scans/" + id + "/report"),
  getScanProgress: (id: string) =>
    request<ScanProgress>("/scans/" + id + "/progress"),
  cancelScan: (id: string) =>
    request<Scan>("/scans/" + id + "/cancel", { method: "POST" }),
  triageFinding: (
    scanId: string,
    findingId: string,
    body: { status: TriageStatus; note?: string | null }
  ) =>
    request<Vulnerability>(
      "/scans/" + scanId + "/findings/" + findingId + "/triage",
      { method: "PATCH", body }
    ),
  retestFinding: (scanId: string, findingId: string) =>
    request<{ scan_id: string; fingerprint: string; status: string }>(
      "/scans/" + scanId + "/findings/" + findingId + "/retest",
      { method: "POST" }
    ),
  createFindingIssue: (
    scanId: string,
    findingId: string,
    tracker?: IssueTracker
  ) =>
    request<{
      issue_url: string;
      tracker: IssueTracker;
      issue_key: string | null;
      created: boolean;
    }>("/scans/" + scanId + "/findings/" + findingId + "/issue", {
      method: "POST",
      body: { tracker: tracker ?? null },
    }),
  getReportPdf: (id: string, compliancePack = false) =>
    requestBlob(
      "/scans/" +
        id +
        "/report.pdf" +
        (compliancePack ? "?compliance_pack=true" : "")
    ),
  getReportSarif: (id: string) => requestBlob("/scans/" + id + "/report.sarif"),
  generateFixPr: (id: string) =>
    request<{ pull_request_url: string }>("/scans/" + id + "/autofix", {
      method: "POST",
    }),

  // --- Report sharing ---
  listShares: (scanId: string) =>
    request<ReportShare[]>("/scans/" + scanId + "/shares"),
  createShare: (
    scanId: string,
    body: {
      label?: string | null;
      expires_in_days?: number | null;
      include_poc?: boolean;
    }
  ) =>
    request<ReportShareCreated>("/scans/" + scanId + "/shares", {
      method: "POST",
      body,
    }),
  revokeShare: (scanId: string, shareId: string) =>
    request<void>("/scans/" + scanId + "/shares/" + shareId, {
      method: "DELETE",
    }),

  // --- Schedules ---
  listSchedules: () => request<Schedule[]>("/schedules"),
  createSchedule: (body: {
    target_id: string;
    frequency: ScanFrequency;
    scan_mode: ScanMode;
    custom_instructions?: string | null;
  }) => request<Schedule>("/schedules", { method: "POST", body }),
  updateSchedule: (
    id: string,
    body: {
      frequency?: ScanFrequency;
      scan_mode?: ScanMode;
      custom_instructions?: string | null;
      enabled?: boolean;
    }
  ) => request<Schedule>("/schedules/" + id, { method: "PATCH", body }),
  deleteSchedule: (id: string) =>
    request<void>("/schedules/" + id, { method: "DELETE" }),

  // --- Grey-box (authenticated testing) ---
  getGreybox: (targetId: string) =>
    request<GreyboxConfig>("/targets/" + targetId + "/greybox"),
  putGreybox: (
    targetId: string,
    body: {
      target_url: string;
      login_url?: string | null;
      username?: string | null;
      password?: string;
      extra?: string;
    }
  ) =>
    request<GreyboxConfig>("/targets/" + targetId + "/greybox", {
      method: "PUT",
      body,
    }),
  deleteGreybox: (targetId: string) =>
    request<void>("/targets/" + targetId + "/greybox", { method: "DELETE" }),

  // --- GitHub App ---
  getGitHubApp: () => request<GitHubAppInfo>("/github/app"),
  claimInstallation: (installation_id: string) =>
    request<Installation>("/github/installations", {
      method: "POST",
      body: { installation_id },
    }),
  deleteInstallation: (id: string) =>
    request<void>("/github/installations/" + id, { method: "DELETE" }),

  // --- Billing ---
  billingSummary: () => request<BillingSummary>("/billing/summary"),
  checkout: (tier: SubscriptionTier) =>
    request<{ checkout_url: string }>("/billing/checkout", {
      method: "POST",
      body: { tier },
    }),
  purchaseComplianceReport: (scanId: string) =>
    request<{ checkout_url: string }>("/billing/compliance-report/" + scanId, {
      method: "POST",
    }),
  billingPortal: () =>
    request<{ portal_url: string }>("/billing/portal", { method: "POST" }),
};
