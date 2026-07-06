// TypeScript mirrors of the backend Pydantic schemas (see backend/app/schemas).

export type SubscriptionTier = "free" | "starter" | "pro" | "enterprise";
export type SubscriptionStatus =
  | "none"
  | "trialing"
  | "active"
  | "past_due"
  | "canceled"
  | "incomplete";
export type ScanStatus = "pending" | "running" | "completed" | "failed";
export type ScanMode = "quick" | "standard" | "deep";
export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface Token {
  access_token: string;
  refresh_token: string;
  token_type?: string;
}

export interface User {
  id: string;
  email: string;
  email_verified: boolean;
  github_username: string | null;
  subscription_tier: SubscriptionTier;
  subscription_status: SubscriptionStatus;
  has_active_subscription: boolean;
  subscription_current_period_end: string | null;
  stripe_customer_id: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Plan {
  tier: SubscriptionTier;
  name: string;
  max_repos: number | null;
  monthly_scans: number | null;
  self_serve: boolean;
  price_configured: boolean;
}

export interface BillingSummary {
  tier: SubscriptionTier;
  status: SubscriptionStatus;
  has_active_subscription: boolean;
  current_period_end: string | null;
  usage: { scans_this_month: number; connected_repos: number };
  limits: Plan;
  plans: Plan[];
}

export interface Repository {
  id: string;
  github_repo_id: string;
  name: string;
  url: string;
  created_at: string;
}

export interface GitHubRepo {
  github_repo_id: string;
  name: string;
  url: string;
  private: boolean;
  description: string | null;
}

export interface Scan {
  id: string;
  repository_id: string;
  status: ScanStatus;
  scan_mode: ScanMode;
  custom_instructions: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
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
}

export interface ScanReport {
  scan: Scan;
  total: number;
  counts_by_severity: Record<Severity, number>;
  vulnerabilities: Vulnerability[];
}
