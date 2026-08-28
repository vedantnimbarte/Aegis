# Running Aegis from CI

On GitHub, install the **Aegis GitHub App** instead of using anything here. It
gets check runs, a findings comment, and the new-findings-only merge gate, none
of which a generic script can produce.

Everywhere else, [`aegis-scan.sh`](aegis-scan.sh) launches a scan with an API
token and fails the build on blocking findings. It needs only `curl` and a
POSIX shell.

## Getting a token

Dashboard → **Team** → **API tokens** → *Create token*. Give it the **member**
role: enough to launch scans and read reports, not enough to invite people or
touch billing. The plaintext is shown once.

Copy the target's id from its URL in the dashboard.

## GitLab CI

```yaml
security:
  image: alpine:3
  before_script:
    - apk add --no-cache curl
  script:
    - ./ops/ci/aegis-scan.sh
  variables:
    AEGIS_TARGET_ID: "00000000-0000-0000-0000-000000000000"
    AEGIS_MODE: quick
  # AEGIS_TOKEN comes from a masked, protected CI/CD variable.
```

## Jenkins

```groovy
stage('Security') {
  environment {
    AEGIS_TOKEN     = credentials('aegis-api-token')
    AEGIS_TARGET_ID = '00000000-0000-0000-0000-000000000000'
  }
  steps { sh './ops/ci/aegis-scan.sh' }
}
```

## CircleCI

```yaml
- run:
    name: Aegis scan
    command: ./ops/ci/aegis-scan.sh
    environment:
      AEGIS_TARGET_ID: 00000000-0000-0000-0000-000000000000
```

## Tuning the gate

| Variable | Default | Notes |
| --- | --- | --- |
| `AEGIS_MODE` | `quick` | `quick` for every push; `deep` costs ~10× the credits |
| `AEGIS_FAIL_ON` | `critical,high` | Set to `""` to report without ever failing |
| `AEGIS_TIMEOUT` | `3600` | Seconds to wait before giving up |
| `AEGIS_ORG` | — | Only when the token should act in another organization |

A first run on an existing codebase will surface whatever was already there.
Start with `AEGIS_FAIL_ON=""` for a week, triage the backlog in the dashboard
(anything marked false-positive or accepted-risk stops counting), then turn the
gate on. A check that fails on the backlog is a check somebody removes.
