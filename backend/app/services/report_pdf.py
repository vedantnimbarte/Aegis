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

    def header(self) -> None:
        content = self.w - self.l_margin - self.r_margin
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*_ACCENT)
        self.cell(content / 2, 8, "AEGIS", align="L")
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


def build_report_pdf(report: "ScanReport", repo_name: str) -> bytes:
    """Render ``report`` to PDF bytes. ``repo_name`` titles the document."""
    pdf = _ReportPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_title(f"Aegis Report - {repo_name}")
    pdf.alias_nb_pages()
    pdf.add_page()

    _title_block(pdf, report, repo_name)
    _summary_block(pdf, report)
    _findings(pdf, report)

    return bytes(pdf.output())


def _content_width(pdf: FPDF) -> float:
    return pdf.w - pdf.l_margin - pdf.r_margin


def _title_block(pdf: _ReportPDF, report: "ScanReport", repo_name: str) -> None:
    scan = report.scan
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(0, 9, _s(repo_name), **_NL)
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
    else:
        pdf.set_text_color(*_MUTED)
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(0, 6, "No vulnerabilities were found.", **_NL)
        pdf.ln(2)


def _findings(pdf: _ReportPDF, report: "ScanReport") -> None:
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
        _finding(pdf, i, v)


def _finding(pdf: _ReportPDF, index: int, v: Any) -> None:
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
    _labeled_code(pdf, "Proof of concept", getattr(v, "poc_code", None))
    _labeled_body(pdf, "Remediation", getattr(v, "remediation", None))

    pdf.ln(1)
    pdf.set_draw_color(*_RULE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())


def _labeled_body(pdf: _ReportPDF, label: str, text: Any) -> None:
    text = _s(text)
    if not text.strip():
        return
    pdf.ln(1.5)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*_ACCENT)
    pdf.cell(0, 5, label.upper(), **_NL)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(0, 5, text, **_NL)


def _labeled_code(pdf: _ReportPDF, label: str, text: Any) -> None:
    text = _s(text)
    if not text.strip():
        return
    pdf.ln(1.5)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*_ACCENT)
    pdf.cell(0, 5, label.upper(), **_NL)
    pdf.set_font("Courier", "", 8.5)
    pdf.set_text_color(*_INK)
    pdf.set_fill_color(*_CODE_BG)
    pdf.multi_cell(_content_width(pdf), 4.6, text, border=0, fill=True, **_NL)


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
