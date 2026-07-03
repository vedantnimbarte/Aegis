# Product Requirements Document (PRD): Continuous Pentesting SaaS

## 1. Product Overview
**Product Name:** AutoPentest (Placeholder)  
**Tagline:** Continuous, AI-driven penetration testing that acts like a real hacker.  
**Description:** A SaaS platform powered by the open-source Strix AI engine. It provides automated, continuous penetration testing for web applications and APIs. Unlike traditional SAST tools that flood developers with false positives, AutoPentest leverages Strix's autonomous AI agents to dynamically execute code, validate vulnerabilities, and provide actual Proof-of-Concept (PoC) exploits and actionable remediation.

## 2. Target Audience & Personas
The product serves a spectrum of users who need validated security testing without the high cost or slow turnaround of traditional manual pentests.

* **Solo Developers & Indie Hackers:** Need an affordable, automated way to ensure their side projects and micro-SaaS apps are secure before launch.
* **Non-Technical Startup Founders:** Need clear, readable security reports to unblock enterprise sales deals or satisfy compliance checklists (e.g., SOC 2 readiness) without hiring a dedicated security team.
* **Enterprise Security Teams (CISOs, AppSec):** Looking to scale their security operations by implementing continuous, high-signal dynamic testing across dozens of repositories.
* **Agency Penetration Testers:** Can use the platform as a white-label backend to automate the tedious reconnaissance and initial exploitation phases of their client engagements.

## 3. MVP Scope & Core Features
For v1.0, the focus is strictly on the core loop: connecting a codebase, running a scan, and viewing historical results.

### 3.1. User Authentication & Onboarding
* **Sign up / Log in:** Email/password and GitHub OAuth integration.
* **Subscription Gate:** Users must select a SaaS tier and input payment details (via Stripe) before initiating their first scan.

### 3.2. GitHub Integration & Repository Scanning
* **Connect GitHub:** OAuth integration to authorize read-only access to user/organization repositories.
* **Target Selection:** Users can select specific repositories from a dropdown to be scanned.
* **Scan Configuration:** * Set scan mode (e.g., Quick Scan for CI/CD parity, Deep Scan for comprehensive review).
    * Optional: Provide custom instructions or context (e.g., "Focus on business logic and IDOR").
* **Scan Execution:** Trigger the Strix engine backend to pull the repo, build the Docker sandbox, and execute the multi-agent pentest.

### 3.3. Web Dashboard & Historical Tracking
* **Dashboard Home:** High-level metrics (Total Scans, Active Vulnerabilities, Average Risk Score).
* **Scan History (List View):** A table displaying historical runs with metadata (Date, Repo Name, Duration, Vulnerability Count, Status: Running/Completed/Failed).
* **Detailed Scan Report (Single View):**
    * **Vulnerability List:** Grouped by severity (Critical, High, Medium, Low).
    * **Finding Details:** For each vulnerability, display the Strix output: OWASP classification, CVSS score, reproduction steps, working Proof-of-Concept (PoC) code, and AI-generated remediation patches.
    * **Export:** Ability to export the report to PDF for compliance and sharing.

## 4. User Flow (MVP)
1.  **Signup:** User lands on marketing site, clicks "Start Scanning", and creates an account.
2.  **Subscribe:** User selects a monthly SaaS plan.
3.  **Connect:** User authorizes the GitHub App.
4.  **Configure:** User selects a repository, configures scan depth, and clicks "Launch Pentest".
5.  **Monitor:** User is redirected to the Dashboard where the scan status shows "In Progress". (Backend Strix agents are consuming LLM tokens and running tools).
6.  **Review:** Scan completes. User receives an email notification. User clicks into the detailed report to view validated vulnerabilities and PoCs.
7.  **Remediate:** User applies the suggested fixes to their codebase.

## 5. Technical Architecture & Stack

### 5.1. Frontend
* **Framework:** React.js (Next.js recommended for routing and SEO).
* **UI Components:** Tailwind CSS, shadcn/ui (for rapid dashboard development).
* **State Management:** React Query / Zustand.

### 5.2. Backend & Database
* **Database:** PostgreSQL (to store user profiles, GitHub tokens, scan metadata, and JSON outputs of Strix reports).
* **API Layer:** Node.js (Express/NestJS) or Python (FastAPI). Python is highly recommended as Strix is built in Python, making custom integrations easier.
* **Job Queue:** Redis + BullMQ / Celery (Crucial for managing long-running Strix scans asynchronously so the web server doesn't time out).

### 5.3. Security Engine (Strix Integration)
* **Execution Environment:** Strix must be run in isolated Docker containers to safely execute untrusted code and perform dynamic analysis.
* **Orchestration:** When a user triggers a scan, the backend spins up a temporary Docker container, injects the target codebase, configures the `STRIX_LLM` environment variables, and executes the Strix CLI in headless mode (`strix -n --target ./repo`).
* **LLM Provider:** The backend will manage API keys for frontier models (e.g., OpenAI GPT-4o or Anthropic Claude 3.5 Sonnet) required by Strix agents.

## 6. Monetization Strategy
The platform will operate on a **SaaS Monthly Subscription** model, tiered by usage and target audience. Because Strix consumes LLM tokens heavily during scans, pricing must account for API overhead.

* **Starter / Indie Tier:** ~$49 - $99/month. Limited to 1-3 repositories. Capped at a specific number of "Quick Scans" per month.
* **Pro / Business Tier:** ~$299 - $499/month. Unlimited repositories. Access to "Deep Scans". PDF exports for compliance. Integration with Slack/Jira.
* **Enterprise Tier:** Custom pricing. Dedicated support, SAML/SSO, option for BYOK (Bring Your Own Key) for LLM costs, and on-premise deployment options.

## 7. Future Scope (Post-MVP)
* **CI/CD Pipeline Integration:** Provide a native GitHub App that automatically triggers Strix scans on every Pull Request and posts comments with findings before code is merged.
* **Authenticated (Grey-Box) Testing:** Allow users to input test credentials so Strix can scan behind login walls.
* **Auto-Fixing:** Allow users to click a button in the dashboard to automatically generate and open a PR with the AI-suggested patch in their GitHub repo.
* **Continuous Attack Surface Monitoring:** Schedule automated recurring weekly scans to detect regressions or new CVEs.
