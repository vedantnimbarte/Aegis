"""Render a scan report to a PDF document (for compliance / sharing).

Uses fpdf2 (pure Python, no system libraries). The layout is a light,
print-friendly theme with severity-colored chips. To keep this module
unit-testable in isolation it imports only fpdf at runtime and reads the report
via duck typing, so a ``types.SimpleNamespace`` stand-in works in tests.

fpdf2's core fonts are Latin-1 only, so all text is sanitized through ``_s``
before rendering (Strix output can contain smart quotes, arrows, etc.). Note
fpdf2's ``multi_cell`` leaves the cursor at the right margin by default, so we
pass ``new_x=LMARGIN, new_y=NEXT`` (via ``_NL``) to return to the left margin.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos

if TYPE_CHECKING:
    from app.schemas.scan import ScanReport

# multi_cell kwargs: advance to the next line, cursor back at the left margin.
_NL = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}

# Ordered worst-first so findings and the summary read top-down by risk.
_SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]

# RGB chips for each severity (white text on a filled pill).
_SEVERITY_RGB: dict[str, tuple[int, int, int]] = {
    "critical": (220, 38, 38),
    "high": (234, 88, 12),
    "medium": (124, 58, 237),
    "low": (2, 132, 199),
    "info": (100, 116, 139),
}

_INK = (17, 21, 28)
_MUTED = (100, 116, 139)
_ACCENT = (8, 145, 178)  # cyan-600, legible on white
_RULE = (214, 220, 228)
_CODE_BG = (244, 246, 249)

_UNICODE_MAP = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "•": "-", "…": "...",
    "→": "->", "←": "<-", " ": " ",
}


def _s(text: Any) -> str:
    """Coerce to a Latin-1-safe string fpdf2's core fonts can render."""
    if text is None:
        return ""
    s = str(text)
    for k, v in _UNICODE_MAP.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def _val(x: Any) -> str:
    """Enum member -> its value; anything else -> str."""
    return str(getattr(x, "value", x))


def _fmt_dt(value: Any) -> str:
    if not value:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M UTC")
    return _s(value)


class _ReportPDF(FPDF):
    """FPDF subclass adding a repeating wordmark header and page footer."""

    # multi_cell(markdown=True) also treats `--` as underline and `__` as
    # italics, which eats the dashes off CLI flags (`--userns=keep-id`) and the
    # underscores off dunder names. Findings are full of both, so only bold is
    # left enabled; these markers are set to sequences that never occur in
    # Latin-1 sanitized prose.
    MARKDOWN_ITALICS_MARKER = "\x01\x01"
    MARKDOWN_UNDERLINE_MARKER = "\x02\x02"

    def header(self) -> None:
        content = self.w - self.l_margin - self.r_margin
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*_ACCENT)
        self.cell(content / 2, 8, self.brand, align="L")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*_MUTED)
        self.cell(0, 8, "Penetration Test Report", align="R", **_NL)
        self.set_draw_color(*_RULE)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*_MUTED)
        self.cell(self.w / 2 - self.l_margin, 8, "Confidential", align="L")
        self.cell(0, 8, f"Page {self.page_no()}/{{nb}}", align="R")


def build_report_pdf(
    report: "ScanReport",
    target_name: str,
    *,
    compliance: Any = None,
    brand: str = "AEGIS",
    include_poc: bool = True,
) -> bytes:
    """Render ``report`` to PDF bytes. ``target_name`` titles the document.

    Passing a ``compliance`` context (see ``services/compliance.py``) turns the
    findings list into the pack an auditor expects: an executive summary,
    scope, methodology, control mappings, stated limitations, and a signed
    attestation letter around the same findings.

    ``include_poc=False`` strips working exploit code, which is what a shared
    link hands to someone outside the company.
    """
    pdf = _ReportPDF(orientation="P", unit="mm", format="A4")
    pdf.brand = _s(brand)
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_title(f"{_s(brand)} Report - {_s(target_name)}")
    pdf.alias_nb_pages()
    pdf.add_page()

    _title_block(pdf, report, target_name, compliance is not None)
    if compliance is not None:
        _compliance_front_matter(pdf, compliance)
    _summary_block(pdf, report)
    _chains_block(pdf, report)
    _findings(pdf, report, include_poc=include_poc)
    if compliance is not None:
        _compliance_back_matter(pdf, compliance)

    return bytes(pdf.output())


def _content_width(pdf: FPDF) -> float:
    return pdf.w - pdf.l_margin - pdf.r_margin


def _title_block(
    pdf: _ReportPDF,
    report: "ScanReport",
    target_name: str,
    is_compliance: bool = False,
) -> None:
    scan = report.scan
    if is_compliance:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*_ACCENT)
        pdf.multi_cell(0, 6, "PENETRATION TEST REPORT", **_NL)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(0, 9, _s(target_name), **_NL)
    pdf.ln(1)

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows = [
        ("Scan mode", _val(scan.scan_mode).capitalize()),
        ("Status", _val(scan.status).capitalize()),
        ("Started", _fmt_dt(getattr(scan, "started_at", None) or scan.created_at)),
        ("Completed", _fmt_dt(getattr(scan, "completed_at", None))),
        ("Scan ID", _s(scan.id)),
        ("Generated", generated),
    ]
    engine_model = getattr(scan, "engine_model", None)
    if engine_model:
        rows.insert(2, ("Engine", _s(engine_model)))
    pdf.set_font("Helvetica", "", 9)
    for label, value in rows:
        pdf.set_text_color(*_MUTED)
        pdf.cell(30, 5.5, _s(label))
        pdf.set_text_color(*_INK)
        pdf.multi_cell(0, 5.5, _s(value), **_NL)
    pdf.ln(3)


def _summary_block(pdf: _ReportPDF, report: "ScanReport") -> None:
    _section_heading(pdf, "Summary")

    counts = report.counts_by_severity or {}
    total = getattr(report, "total", sum(counts.values()))
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*_INK)
    plural = "vulnerability" if total == 1 else "vulnerabilities"
    pdf.multi_cell(0, 6, _s(f"{total} validated {plural} found in this scan."), **_NL)
    pdf.ln(1)

    # A row of severity chips with counts (only non-zero shown, worst-first).
    any_shown = False
    for sev in _SEVERITY_ORDER:
        n = counts.get(sev, 0)
        if not n:
            continue
        any_shown = True
        _chip(pdf, f"{sev.capitalize()}: {n}", _SEVERITY_RGB[sev])
        pdf.cell(2, 7, "")  # spacer between chips
    if any_shown:
        pdf.ln(11)
        verified = getattr(report, "verified_fixed_count", 0) or 0
        if verified:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*_MUTED)
            pdf.multi_cell(
                0,
                5,
                _s(
                    f"{verified} finding(s) have been remediated and verified by "
                    "re-running the original proof of concept."
                ),
                **_NL,
            )
            pdf.ln(1)
    else:
        pdf.set_text_color(*_MUTED)
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(0, 6, "No vulnerabilities were found.", **_NL)
        pdf.ln(2)


def _findings(pdf: _ReportPDF, report: "ScanReport", include_poc: bool = True) -> None:
    vulns = list(getattr(report, "vulnerabilities", []) or [])
    if not vulns:
        return
    _section_heading(pdf, "Findings")

    # Render worst-first regardless of input order.
    vulns.sort(
        key=lambda v: _SEVERITY_ORDER.index(_val(v.severity))
        if _val(v.severity) in _SEVERITY_ORDER
        else 99
    )

    for i, v in enumerate(vulns, start=1):
        _finding(pdf, i, v, include_poc=include_poc)


def _finding(pdf: _ReportPDF, index: int, v: Any, include_poc: bool = True) -> None:
    sev = _val(v.severity)
    rgb = _SEVERITY_RGB.get(sev, _MUTED)

    # Avoid orphaning a finding's title at the very bottom of a page.
    if pdf.get_y() > pdf.h - 45:
        pdf.add_page()

    pdf.ln(2)
    y = pdf.get_y()
    _chip(pdf, sev.capitalize(), rgb)
    pdf.set_xy(pdf.l_margin + 26, y)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(0, 7, _s(f"{index}. {v.title}"), **_NL)
    pdf.ln(0.5)

    # Metadata line (CVSS / class / location), only what's present.
    meta_bits = []
    if getattr(v, "cvss_score", None) is not None:
        meta_bits.append(f"CVSS {float(v.cvss_score):.1f}")
    if getattr(v, "owasp_category", None):
        meta_bits.append(_s(v.owasp_category))
    if getattr(v, "file_path", None):
        meta_bits.append(_s(v.file_path))
    if meta_bits:
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.multi_cell(0, 5, _s("   ".join(meta_bits)), **_NL)

    _labeled_body(pdf, "Description", getattr(v, "description", ""))
    if include_poc:
        _labeled_code(pdf, "Proof of concept", getattr(v, "poc_code", None))
    _evidence_block(pdf, getattr(v, "evidence", None), include_poc)
    _retest_line(pdf, v)
    _labeled_body(pdf, "Remediation", getattr(v, "remediation", None))

    pdf.ln(1)
    pdf.set_draw_color(*_RULE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())


def _evidence_block(pdf: _ReportPDF, evidence: Any, include_poc: bool) -> None:
    """Print what was observed, so the reader can check the claim themselves.

    On a shared report the transcript is withheld along with the PoC: a
    request/response pair for a live exploit is a working recipe whatever the
    surrounding document is called. Provenance still prints, because "tested
    on this date against this commit" is the part an auditor needs.
    """
    if not evidence:
        return
    get = evidence.get if isinstance(evidence, dict) else lambda k: getattr(evidence, k, None)

    if include_poc:
        _labeled_code(pdf, "Evidence - request", get("request"))
        _labeled_code(pdf, "Evidence - response", get("response"))
        _labeled_code(pdf, "Evidence - proof-of-concept output", get("poc_output"))

    provenance = []
    if get("target_url"):
        provenance.append(f"Target: {_s(get('target_url'))}")
    if get("commit_sha"):
        provenance.append(f"Commit: {_s(get('commit_sha'))[:12]}")
    if get("model"):
        provenance.append(f"Model: {_s(get('model'))}")
    if get("observed_at"):
        provenance.append(f"Observed: {_s(get('observed_at'))}")
    if provenance:
        _label(pdf, "Evidence - provenance")
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*_MUTED)
        pdf.multi_cell(0, 4.8, _s("   ".join(provenance)), **_NL)


def _retest_line(pdf: _ReportPDF, v: Any) -> None:
    """State the verification verdict, when this finding has been retested."""
    outcome = _val(getattr(v, "retest_outcome", None) or "") or ""
    if not outcome or outcome == "None":
        return
    when = getattr(v, "retested_at", None)
    stamp = f" on {_fmt_dt(when)}" if when else ""
    text = {
        "fixed": f"Verified fixed{stamp} - the original exploit no longer succeeds.",
        "still_vulnerable": f"Retested{stamp} - the exploit still succeeds.",
        "inconclusive": f"Retested{stamp} - the retest did not complete; nothing was proven.",
    }.get(outcome)
    if not text:
        return
    _label(pdf, "Verification")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(0, 5, _s(text), **_NL)


def _chains_block(pdf: _ReportPDF, report: "ScanReport") -> None:
    """Findings that compose into a worse outcome than any of them alone."""
    chains = list(getattr(report, "attack_chains", []) or [])
    if not chains:
        return
    _section_heading(pdf, "Attack chains")
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(
        0,
        5,
        _s(
            "Individually these findings are limited. Combined, each group below "
            "reaches an outcome none of its parts reaches alone, and should be "
            "prioritised accordingly."
        ),
        **_NL,
    )
    pdf.ln(2)

    for chain in chains:
        severity = _val(getattr(chain, "severity", None) or "info")
        title = _s(getattr(chain, "title", "") or "Attack chain")
        if pdf.get_y() > pdf.h - 45:
            pdf.add_page()
        y = pdf.get_y()
        _chip(pdf, severity.capitalize(), _SEVERITY_RGB.get(severity, _MUTED))
        pdf.set_xy(pdf.l_margin + 26, y)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*_INK)
        pdf.multi_cell(0, 6.5, title, **_NL)

        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*_INK)
        pdf.multi_cell(0, 5, _s(getattr(chain, "narrative", "") or ""), **_NL)
        for step in getattr(chain, "steps", []) or []:
            _md_item(pdf, "-", _s(step))
        pdf.ln(2)


def _compliance_front_matter(pdf: _ReportPDF, context: Any) -> None:
    """Executive summary, scope and methodology — the pages auditors read."""
    from app.services import compliance as compliance_service

    _section_heading(pdf, "Executive summary")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(0, 5.5, _s(compliance_service.executive_summary(context)), **_NL)
    pdf.ln(2)

    _section_heading(pdf, "Scope")
    pdf.set_font("Helvetica", "", 9.5)
    pdf.multi_cell(0, 5, _s(context.scope_description), **_NL)
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_MUTED)
    for label, value in (
        ("Client", context.organization_name),
        ("Tested by", context.vendor_name),
        ("Engine", context.engine + (f" ({context.model})" if context.model else "")),
    ):
        pdf.multi_cell(0, 5, _s(f"{label}: {value}"), **_NL)
    pdf.ln(2)

    _section_heading(pdf, "Methodology")
    for name, description in compliance_service.METHODOLOGY_STEPS:
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(*_INK)
        pdf.multi_cell(0, 5, _s(name), **_NL)
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*_MUTED)
        pdf.multi_cell(0, 5, _s(description), **_NL)
        pdf.ln(1)

    _section_heading(pdf, "Control mapping")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(
        0,
        5,
        _s(
            "This assessment provides evidence toward the controls below. It is "
            "not a certification of compliance with any framework."
        ),
        **_NL,
    )
    pdf.ln(1)
    for mapping in compliance_service.CONTROL_MAPPINGS:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*_INK)
        pdf.multi_cell(0, 5, _s(f"{mapping.framework} - {mapping.control}"), **_NL)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*_MUTED)
        pdf.multi_cell(0, 5, _s(mapping.description), **_NL)
        pdf.ln(0.5)
    pdf.ln(2)


def _compliance_back_matter(pdf: _ReportPDF, context: Any) -> None:
    """Limitations, then the attestation letter on its own page."""
    from app.services import compliance as compliance_service

    _section_heading(pdf, "Limitations")
    for limitation in compliance_service.LIMITATIONS:
        _md_item(pdf, "-", _s(limitation))
    pdf.ln(2)

    # The letter is what gets detached and handed to an auditor, so it starts
    # on a clean page and carries the report reference on its face.
    pdf.add_page()
    _section_heading(pdf, "Letter of attestation")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*_INK)
    for paragraph in compliance_service.attestation_letter(context).split("\n\n"):
        pdf.multi_cell(0, 5.5, _s(paragraph), **_NL)
        pdf.ln(2)


def _labeled_body(pdf: _ReportPDF, label: str, text: Any) -> None:
    text = _s(text)
    if not text.strip():
        return
    _label(pdf, label)
    _markdown(pdf, text)


def _labeled_code(pdf: _ReportPDF, label: str, text: Any) -> None:
    text = _s(text)
    if not text.strip():
        return
    _label(pdf, label)
    _code_block(pdf, text)


def _label(pdf: _ReportPDF, label: str) -> None:
    pdf.ln(1.5)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*_ACCENT)
    pdf.cell(0, 5, label.upper(), **_NL)


def _code_block(pdf: _ReportPDF, text: str) -> None:
    pdf.set_font("Courier", "", 8.5)
    pdf.set_text_color(*_INK)
    pdf.set_fill_color(*_CODE_BG)
    pdf.multi_cell(_content_width(pdf), 4.6, text, border=0, fill=True, **_NL)


# --- Markdown -------------------------------------------------------------
# Findings come back from the model as GitHub-flavoured markdown. fpdf2 has no
# block-level markdown renderer, so blocks are handled here and inline spans
# are left to multi_cell(markdown=True), which understands **bold**, __italic__
# and --underline--. A literal __dunder__ in prose therefore comes out italic;
# accepted, since the alternative is losing bold everywhere.
_MD_FENCE = "```"
_MD_HEADING = re.compile(r"(#{1,6})\s+(.*)")
_MD_RULE = re.compile(r"(-{3,}|\*{3,}|_{3,})")
_MD_BULLET = re.compile(r"[-*+]\s+(.*)")
_MD_NUMBER = re.compile(r"(\d+)[.)]\s+(.*)")
_MD_TABLE_SEP = re.compile(r"\|[\s|:-]+\|?")
_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
# A lone *emphasis* pair; the lookarounds keep it off **bold**.
_MD_EMPHASIS = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")


def _md_inline(text: str) -> str:
    """Reduce inline spans to what multi_cell's markdown mode can render."""
    text = _MD_LINK.sub(r"\1 (\2)", text)  # [label](url) -> label (url)
    text = _MD_EMPHASIS.sub(r"\1", text)  # italics are off; drop the markers
    return text.replace("`", "")  # no monospace runs in a cell; drop the ticks


def _markdown(pdf: _ReportPDF, text: str) -> None:
    """Render finding prose as markdown, in the report's own typography."""
    lines = text.split("\n")
    para: list[str] = []
    i = 0

    def flush() -> None:
        if para:
            _md_paragraph(pdf, " ".join(para))
            para.clear()

    while i < len(lines):
        line = lines[i].strip()
        heading = _MD_HEADING.fullmatch(line)
        bullet = _MD_BULLET.fullmatch(line)
        number = _MD_NUMBER.fullmatch(line)

        if line.startswith(_MD_FENCE):
            flush()
            i += 1
            block: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith(_MD_FENCE):
                block.append(lines[i])
                i += 1
            _code_block(pdf, "\n".join(block).strip("\n") or " ")
        elif not line:
            flush()
        elif _MD_RULE.fullmatch(line):
            flush()
            _md_rule(pdf)
        elif heading:
            flush()
            _md_heading(pdf, heading.group(2), len(heading.group(1)))
        elif bullet:
            flush()
            _md_item(pdf, "-", bullet.group(1))
        elif number:
            flush()
            _md_item(pdf, number.group(1) + ".", number.group(2))
        elif line.startswith(">"):
            flush()
            _md_quote(pdf, line.lstrip("> ").strip())
        elif line.startswith("|"):
            flush()
            # Tables become spaced rows; the |---|---| divider carries nothing.
            if not _MD_TABLE_SEP.fullmatch(line):
                cells = [c.strip() for c in line.strip("|").split("|")]
                _md_paragraph(pdf, "   ".join(cells))
        else:
            para.append(line)
        i += 1

    flush()


def _md_paragraph(pdf: _ReportPDF, text: str) -> None:
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(0, 5, _md_inline(text), markdown=True, **_NL)


def _md_heading(pdf: _ReportPDF, text: str, level: int) -> None:
    pdf.ln(1.5)
    pdf.set_font("Helvetica", "B", 11 if level <= 2 else 10)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(0, 5.5, _md_inline(text), **_NL)


def _md_item(pdf: _ReportPDF, marker: str, text: str) -> None:
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*_INK)
    pdf.cell(6, 5, marker)
    # Wrapped lines keep the cell's own left edge, so the text hangs indented.
    pdf.multi_cell(_content_width(pdf) - 6, 5, _md_inline(text), markdown=True, **_NL)


def _md_quote(pdf: _ReportPDF, text: str) -> None:
    pdf.set_font("Helvetica", "I", 9.5)
    pdf.set_text_color(*_MUTED)
    pdf.set_x(pdf.l_margin + 4)
    pdf.multi_cell(_content_width(pdf) - 4, 5, _md_inline(text), markdown=True, **_NL)


def _md_rule(pdf: _ReportPDF) -> None:
    pdf.ln(1)
    pdf.set_draw_color(*_RULE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)


def _section_heading(pdf: _ReportPDF, text: str) -> None:
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*_INK)
    pdf.cell(0, 8, _s(text), **_NL)
    pdf.ln(1)


def _chip(pdf: _ReportPDF, text: str, rgb: tuple[int, int, int]) -> None:
    """Draw a small filled pill with white text at the current position."""
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(*rgb)
    pdf.set_text_color(255, 255, 255)
    w = pdf.get_string_width(text) + 6
    pdf.cell(w, 6.5, text, align="C", fill=True)
