// TypeScript mirrors of the backend Pydantic schemas (see backend/app/schemas).

export type SubscriptionTier = "free" | "starter" | "pro" | "enterprise";
export type SubscriptionStatus =
  | "none"
  | "trialing"
  | "active"
  | "past_due"
  | "canceled"
  | "incomplete";
export type ScanStatus = "pending" | "running" | "completed" | "failed" | "canceled";
export type ScanMode = "quick" | "standard" | "deep";
export type ScanFrequency = "daily" | "weekly" | "monthly";
export type ScanTrigger =
  | "manual"
  | "scheduled"
  | "pull_request"
  | "retest"
  | "discovery";
export type Severity = "critical" | "high" | "medium" | "low" | "info";
export type OrgRole = "viewer" | "member" | "admin" | "owner";
export type TargetKind = "repo" | "web" | "api" | "llm" | "mcp";
export type GitProvider = "github" | "gitlab" | "bitbucket";
export type IssueTracker = "github" | "jira" | "linear";
export type RetestOutcome = "fixed" | "still_vulnerable" | "inconclusive";

/** Privilege order, mirroring ROLE_RANK in the backend enums. */
export const ROLE_RANK: Record<OrgRole, number> = {
  viewer: 0,
  member: 1,
  admin: 2,
  owner: 3,
};

export function atLeast(role: OrgRole | null | undefined, minimum: OrgRole): boolean {
  return role ? ROLE_RANK[role] >= ROLE_RANK[minimum] : false;
}

export interface Token {
  access_token: string;
  refresh_token: string;
  token_type?: string;
}

export interface User {
  id: string;
  email: string;
  email_verified: boolean;
  display_name: string | null;
  github_username: string | null;
  has_password: boolean;
  subscription_tier: SubscriptionTier;
  subscription_status: SubscriptionStatus;
  has_active_subscription: boolean;
  subscription_current_period_end: string | null;
  stripe_customer_id: string | null;
  is_active: boolean;
  created_at: string;
  has_accepted_scan_terms: boolean;
  // Integrations (secrets are never returned — only presence flags).
  llm_model: string | null;
  has_llm_key: boolean;
  has_slack: boolean;
  has_jira: boolean;
  has_linear: boolean;
  jira_url: string | null;
  jira_project_key: string | null;
  linear_team_id: string | null;
}

/** A condition that stops the account being deleted. */
export interface DeletionBlocker {
  code: string;
  message: string;
  /** What the person has to do about it, in the interface's words. */
  action: string;
}

/** Exactly what deleting the account destroys, counted from real rows. */
export interface DeletionManifest {
  organizations_deleted: string[];
  organizations_left: string[];
  targets: number;
  scans: number;
  findings: number;
  triage_verdicts: number;
  api_tokens: number;
  share_links: number;
  installations: number;
  running_scans: number;
  blockers: DeletionBlocker[];
  can_delete: boolean;
}

// --- Organizations --------------------------------------------------------
export interface Organization {
  id: string;
  name: string;
  slug: string;
  parent_id: string | null;
  brand_name: string | null;
  brand_primary_color: string | null;
  created_at: string;
  role: OrgRole | null;
  is_client_workspace: boolean;
}

export interface Member {
  id: string;
  user_id: string;
  email: string;
  role: OrgRole;
  created_at: string;
}

export interface AuditEvent {
  id: string;
  action: string;
  actor_email: string | null;
  subject_type: string | null;
  subject_id: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}

export interface ApiToken {
  id: string;
  name: string;
  token_prefix: string;
  role: OrgRole;
  last_used_at: string | null;
  expires_at: string | null;
  created_at: string;
}

/** Returned once, at creation — `token` is never retrievable again. */
export interface ApiTokenCreated extends ApiToken {
  token: string;
}

// --- Billing --------------------------------------------------------------
export interface Plan {
  tier: SubscriptionTier;
  name: string;
  max_targets: number | null;
  included_credits: number | null;
  included_seats: number | null;
  self_serve: boolean;
  price_configured: boolean;
  allow_overage: boolean;
  byok: boolean;
  compliance_reports: boolean;
  white_label: boolean;
  mssp: boolean;
}

export interface BillingUsage {
  credits_used: number;
  credits_included: number | null;
  connected_targets: number;
  seats_used: number;
  seats_included: number | null;
  credit_cost_by_mode: Record<ScanMode, number>;
}

export interface BillingSummary {
  tier: SubscriptionTier;
  status: SubscriptionStatus;
  has_active_subscription: boolean;
  current_period_end: string | null;
  usage: BillingUsage;
  limits: Plan;
  plans: Plan[];
  billed_to_parent: boolean;
}

// --- Targets --------------------------------------------------------------
export interface Target {
  id: string;
  organization_id: string;
  kind: TargetKind;
  name: string;
  provider: GitProvider | null;
  external_repo_id: string | null;
  clone_url: string | null;
  url: string | null;
  openapi_url: string | null;
  has_greybox: boolean;
  has_derived_spec: boolean;
  max_budget_usd: number | null;
  gate_fail_severities: string | null;
  gate_new_findings_only: boolean;
  discovery_enabled: boolean;
  discovered_from_id: string | null;
  created_at: string;
}

/** A repository on a source host, not necessarily connected yet. */
export interface SourceRepo {
  provider: GitProvider;
  external_repo_id: string;
  name: string;
  clone_url: string;
  private: boolean;
  description: string | null;
}

// --- Scans ----------------------------------------------------------------
export interface Scan {
  id: string;
  target_id: string;
  status: ScanStatus;
  scan_mode: ScanMode;
  trigger: ScanTrigger;
  github_pr_number: number | null;
  autofix_pr_url: string | null;
  custom_instructions: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  cost_usd: number | null;
  llm_requests: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  engine_model: string | null;
  retest_fingerprint: string | null;
  retest_outcome: RetestOutcome | null;
  target_name: string | null;
  target_kind: TargetKind | null;
  /** Open findings by severity. Null until the scan completes. */
  counts_by_severity: Record<Severity, number> | null;
  /** Every finding, including ones triaged away. Null until the scan completes. */
  findings_total: number | null;
}

/** Current posture across all targets — the latest completed scan of each. */
export interface DashboardSummary {
  total_scans: number;
  running_scans: number;
  connected_targets: number;
  scanned_targets: number;
  counts_by_severity: Record<Severity, number>;
  open_findings: number;
  suppressed_findings: number;
  verified_fixed: number;
  last_scan_at: string | null;
}

export interface TargetCost {
  target_id: string;
  target_name: string;
  scans: number;
  cost_usd: number;
  findings: number;
  validated_findings: number;
  cost_per_validated_finding: number | null;
}

export interface CostSummary {
  period_start: string;
  total_cost_usd: number;
  total_scans: number;
  total_findings: number;
  validated_findings: number;
  cost_per_scan: number | null;
  cost_per_validated_finding: number | null;
  by_target: TargetCost[];
  forecast_by_mode: Record<string, number>;
}

export interface ProgressStep {
  title: string;
  detail: string | null;
  status: "pending" | "active" | "done";
  agent: string | null;
}

export interface ScanProgress {
  status: ScanStatus;
  phase: string;
  run_id: string | null;
  steps: ProgressStep[];
  agents: { name: string; status: string }[];
  llm_requests: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number | null;
}

export type TriageStatus = "open" | "false_positive" | "accepted_risk" | "fixed";

export interface ScanDiff {
  has_baseline: boolean;
  previous_scan_id: string | null;
  new_count: number;
  fixed_count: number;
  persisting_count: number;
}

/** What was actually observed — the receipt behind a finding. */
export interface Evidence {
  request: string | null;
  response: string | null;
  poc_output: string | null;
  target_url: string | null;
  commit_sha: string | null;
  engine: string | null;
  model: string | null;
  observed_at: string | null;
  notes: string | null;
}

export interface Vulnerability {
  id: string;
  severity: Severity;
  title: string;
  description: string;
  poc_code: string | null;
  remediation: string | null;
  owasp_category: string | null;
  cvss_score: number | null;
  file_path: string | null;
  has_fix: boolean;
  fingerprint: string | null;
  triage_status: TriageStatus;
  triage_note: string | null;
  github_issue_url: string | null;
  issue_tracker: IssueTracker | null;
  issue_key: string | null;
  is_new: boolean;
  evidence: Evidence | null;
  retest_outcome: RetestOutcome | null;
  retested_at: string | null;
}

/** Findings that compose into an outcome none of them reaches alone. */
export interface AttackChain {
  title: string;
  severity: Severity;
  narrative: string;
  fingerprints: string[];
  steps: string[];
}

export interface ScanReport {
  scan: Scan;
  total: number;
  counts_by_severity: Record<Severity, number>;
  fixable_count: number;
  open_count: number;
  suppressed_count: number;
  verified_fixed_count: number;
  diff: ScanDiff;
  attack_chains: AttackChain[];
  vulnerabilities: Vulnerability[];
}

export interface ReportShare {
  id: string;
  scan_id: string;
  label: string | null;
  expires_at: string;
  include_poc: boolean;
  view_count: number;
  last_viewed_at: string | null;
  created_at: string;
}

/** Returned once, at creation — the URL embeds the only copy of the token. */
export interface ReportShareCreated extends ReportShare {
  url: string;
}

export interface Schedule {
  id: string;
  target_id: string;
  scan_mode: ScanMode;
  frequency: ScanFrequency;
  custom_instructions: string | null;
  enabled: boolean;
  next_run_at: string;
  last_run_at: string | null;
  created_at: string;
}

export interface GreyboxConfig {
  id: string;
  target_id: string;
  target_url: string;
  login_url: string | null;
  username: string | null;
  has_password: boolean;
  has_extra: boolean;
  created_at: string;
}

export interface Installation {
  id: string;
  installation_id: string;
  account_login: string;
  created_at: string;
}

export interface GitHubAppInfo {
  configured: boolean;
  install_url: string;
  installations: Installation[];
}
