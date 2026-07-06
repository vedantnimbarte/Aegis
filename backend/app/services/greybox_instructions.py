"""Build the Strix instruction for authenticated grey-box testing.

Pure and dependency-free so it can be unit-tested in isolation. The returned
text is written to a mode-0600 instruction file in the ephemeral scan workdir
(never passed on the command line, so credentials don't appear in `ps`).
"""
from __future__ import annotations

from typing import Optional


def build_instruction(
    *,
    target_url: str,
    login_url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    extra: Optional[str] = None,
    custom_instructions: Optional[str] = None,
) -> str:
    """Compose an authenticated grey-box testing instruction for Strix."""
    lines: list[str] = [
        "# Authenticated grey-box testing",
        "",
        "Perform authenticated dynamic testing against the live application "
        "below, in addition to reviewing the source code.",
        "",
        f"Live target: {target_url}",
    ]
    if login_url and login_url.strip():
        lines.append(f"Login page: {login_url.strip()}")

    creds: list[str] = []
    if username and username.strip():
        creds.append(f'username "{username.strip()}"')
    if password:
        creds.append(f'password "{password}"')
    if creds:
        lines.append("Credentials: " + " and ".join(creds) + ".")

    if extra and extra.strip():
        lines += ["", "Additional authentication material / notes:", extra.strip()]

    lines += [
        "",
        "After authenticating, exercise authenticated functionality and test for "
        "broken access control, IDOR, privilege escalation, session/auth flaws, "
        "and business-logic vulnerabilities.",
    ]

    if custom_instructions and custom_instructions.strip():
        lines += ["", "# Additional instructions", custom_instructions.strip()]

    return "\n".join(lines)
