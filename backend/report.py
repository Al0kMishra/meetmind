"""
backend/report.py
──────────────────
Generates a beautiful PDF meeting report using reportlab.
Called by the /meetings/{id}/report endpoint.
"""

import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


# ── Pastel color palette ─────────────────────────────────────────
C_LAVENDER  = colors.HexColor("#7c3aed")
C_LAV_LIGHT = colors.HexColor("#ede9fe")
C_LAV_MID   = colors.HexColor("#c4b5fd")
C_MINT      = colors.HexColor("#059669")
C_MINT_L    = colors.HexColor("#d1fae5")
C_PEACH     = colors.HexColor("#ea580c")
C_PEACH_L   = colors.HexColor("#ffedd5")
C_SKY       = colors.HexColor("#0284c7")
C_SKY_L     = colors.HexColor("#e0f2fe")
C_ROSE      = colors.HexColor("#e11d48")
C_ROSE_L    = colors.HexColor("#ffe4e6")
C_LEMON_L   = colors.HexColor("#fefce8")
C_LEMON     = colors.HexColor("#ca8a04")
C_TEXT      = colors.HexColor("#2d1f3d")
C_TEXT2     = colors.HexColor("#6b5577")
C_TEXT3     = colors.HexColor("#9d89a8")
C_BG        = colors.HexColor("#fdf8f6")
C_WHITE     = colors.white
C_BORDER    = colors.HexColor("#e9d5ff")

W, H = A4
MARGIN = 18 * mm


def build_styles():
    return {
        "cover_title": ParagraphStyle(
            "cover_title",
            fontName="Helvetica-Bold",
            fontSize=26,
            textColor=C_LAVENDER,
            leading=32,
            spaceAfter=6,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            fontName="Helvetica",
            fontSize=11,
            textColor=C_TEXT2,
            leading=16,
            spaceAfter=4,
        ),
        "section_heading": ParagraphStyle(
            "section_heading",
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=C_LAVENDER,
            leading=18,
            spaceBefore=16,
            spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=10,
            textColor=C_TEXT,
            leading=16,
            spaceAfter=4,
        ),
        "body_muted": ParagraphStyle(
            "body_muted",
            fontName="Helvetica",
            fontSize=9,
            textColor=C_TEXT2,
            leading=14,
        ),
        "mono": ParagraphStyle(
            "mono",
            fontName="Courier",
            fontSize=9,
            textColor=C_TEXT2,
            leading=14,
        ),
        "action_task": ParagraphStyle(
            "action_task",
            fontName="Helvetica",
            fontSize=10,
            textColor=C_TEXT,
            leading=15,
        ),
        "chip": ParagraphStyle(
            "chip",
            fontName="Helvetica",
            fontSize=8,
            textColor=C_SKY,
            leading=12,
        ),
        "transcript_speaker": ParagraphStyle(
            "transcript_speaker",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=C_LAVENDER,
            leading=13,
        ),
        "transcript_text": ParagraphStyle(
            "transcript_text",
            fontName="Helvetica",
            fontSize=9,
            textColor=C_TEXT,
            leading=14,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName="Helvetica",
            fontSize=8,
            textColor=C_TEXT3,
            alignment=TA_CENTER,
        ),
    }


def fmt_duration(seconds):
    if not seconds:
        return "—"
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}m {s}s" if m > 0 else f"{s}s"


def fmt_time(seconds):
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


def generate_report(meeting: dict, utterances: list, intelligence: list) -> bytes:
    """
    Generate a full PDF meeting report.
    Returns raw PDF bytes.
    """
    buf    = io.BytesIO()
    styles = build_styles()

    doc = SimpleDocTemplate(
        buf,
        pagesize      = A4,
        leftMargin    = MARGIN,
        rightMargin   = MARGIN,
        topMargin     = MARGIN,
        bottomMargin  = MARGIN,
        title         = meeting.get("title", "Meeting Report"),
        author        = "MeetMind",
    )

    story = []
    content_width = W - 2 * MARGIN

    # Get final intelligence
    final_intel = next((i for i in reversed(intelligence) if i.get("is_final")), None)
    if not final_intel and intelligence:
        final_intel = intelligence[-1]

    # ── Cover / Header ───────────────────────────────────────────
    # Top color bar
    story.append(Table(
        [[""]],
        colWidths=[content_width],
        rowHeights=[6],
        style=TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), C_LAVENDER),
            ("LINEABOVE",  (0,0), (-1,-1), 0, C_LAVENDER),
        ])
    ))
    story.append(Spacer(1, 10))

    # Logo text + title
    story.append(Paragraph("🧠 MeetMind", ParagraphStyle(
        "brand", fontName="Helvetica-Bold", fontSize=11,
        textColor=C_LAV_MID, spaceAfter=12,
    )))
    story.append(Paragraph(meeting.get("title", "Meeting Report"), styles["cover_title"]))

    # Meta row
    started = datetime.fromtimestamp(meeting.get("started_at", 0)).strftime("%d %b %Y, %H:%M")
    duration = fmt_duration(meeting.get("duration_s"))
    word_count = meeting.get("word_count", 0)
    utterance_count = len(utterances)

    meta_data = [[
        Paragraph(f"<b>Date</b><br/>{started}",        styles["body_muted"]),
        Paragraph(f"<b>Duration</b><br/>{duration}",    styles["body_muted"]),
        Paragraph(f"<b>Words</b><br/>{word_count:,}",   styles["body_muted"]),
        Paragraph(f"<b>Utterances</b><br/>{utterance_count}", styles["body_muted"]),
    ]]
    col_w = content_width / 4
    meta_table = Table(meta_data, colWidths=[col_w]*4)
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), C_LAV_LIGHT),
        ("ROUNDEDCORNERS", (0,0), (-1,-1), 8),
        ("TOPPADDING",    (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ("LEFTPADDING",   (0,0), (-1,-1), 14),
        ("RIGHTPADDING",  (0,0), (-1,-1), 14),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER))

    # ── Summary ──────────────────────────────────────────────────
    if final_intel and final_intel.get("summary"):
        story.append(Spacer(1, 6))
        story.append(Paragraph("Meeting Summary", styles["section_heading"]))

        summary_table = Table(
            [[Paragraph(final_intel["summary"], styles["body"])]],
            colWidths=[content_width],
        )
        summary_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), C_MINT_L),
            ("LEFTPADDING",   (0,0), (-1,-1), 14),
            ("RIGHTPADDING",  (0,0), (-1,-1), 14),
            ("TOPPADDING",    (0,0), (-1,-1), 12),
            ("BOTTOMPADDING", (0,0), (-1,-1), 12),
            ("LINEABOVE",     (0,0), (-1,-1), 3, C_MINT),
        ]))
        story.append(summary_table)

    # ── Action Items ─────────────────────────────────────────────
    if final_intel and final_intel.get("action_items"):
        story.append(Spacer(1, 6))
        story.append(Paragraph("Action Items", styles["section_heading"]))

        for i, item in enumerate(final_intel["action_items"]):
            task  = item.get("task", "")
            owner = item.get("owner", "Unassigned")
            dl    = item.get("deadline", "")

            owner_text = f"👤 {owner}"
            dl_text    = f"  📅 {dl}" if dl else ""

            row = [[
                Paragraph(f"{i+1}.", ParagraphStyle("num",fontName="Helvetica-Bold",
                    fontSize=10,textColor=C_LAVENDER,leading=15)),
                Paragraph(task, styles["action_task"]),
                Paragraph(f"{owner_text}{dl_text}", styles["body_muted"]),
            ]]
            t = Table(row, colWidths=[10*mm, content_width-10*mm-40*mm, 40*mm])
            t.setStyle(TableStyle([
                ("BACKGROUND",    (0,0), (-1,-1), C_WHITE),
                ("LINEABOVE",     (0,0), (-1,-1), 1 if i==0 else 0, C_BORDER),
                ("LINEBELOW",     (0,0), (-1,-1), 1, C_BORDER),
                ("LEFTPADDING",   (0,0), (-1,-1), 10),
                ("RIGHTPADDING",  (0,0), (-1,-1), 10),
                ("TOPPADDING",    (0,0), (-1,-1), 10),
                ("BOTTOMPADDING", (0,0), (-1,-1), 10),
                ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ]))
            story.append(KeepTogether(t))

    # ── Decisions ────────────────────────────────────────────────
    if final_intel and final_intel.get("decisions"):
        story.append(Spacer(1, 6))
        story.append(Paragraph("Decisions Made", styles["section_heading"]))
        for d in final_intel["decisions"]:
            row = Table(
                [[Paragraph("✅", styles["body"]), Paragraph(d, styles["body"])]],
                colWidths=[8*mm, content_width-8*mm],
            )
            row.setStyle(TableStyle([
                ("BACKGROUND",    (0,0), (-1,-1), C_MINT_L),
                ("LEFTPADDING",   (0,0), (-1,-1), 10),
                ("TOPPADDING",    (0,0), (-1,-1), 8),
                ("BOTTOMPADDING", (0,0), (-1,-1), 8),
                ("LINEBELOW",     (0,0), (-1,-1), 1, colors.HexColor("#bbf7d0")),
                ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ]))
            story.append(row)

    # ── Open Questions ───────────────────────────────────────────
    if final_intel and final_intel.get("open_questions"):
        story.append(Spacer(1, 6))
        story.append(Paragraph("Open Questions", styles["section_heading"]))
        for q in final_intel["open_questions"]:
            row = Table(
                [[Paragraph("❓", styles["body"]), Paragraph(q, styles["body"])]],
                colWidths=[8*mm, content_width-8*mm],
            )
            row.setStyle(TableStyle([
                ("BACKGROUND",    (0,0), (-1,-1), C_LEMON_L),
                ("LEFTPADDING",   (0,0), (-1,-1), 10),
                ("TOPPADDING",    (0,0), (-1,-1), 8),
                ("BOTTOMPADDING", (0,0), (-1,-1), 8),
                ("LINEBELOW",     (0,0), (-1,-1), 1, colors.HexColor("#fef08a")),
                ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ]))
            story.append(row)

    # ── Full Transcript ──────────────────────────────────────────
    if utterances:
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER))
        story.append(Paragraph("Full Transcript", styles["section_heading"]))

        SPEAKER_COLORS = [C_LAVENDER, C_MINT, C_PEACH, C_SKY, C_ROSE, C_LEMON]
        speaker_color_map = {}
        color_idx = 0

        for utt in utterances:
            spk = utt.get("speaker", "SPEAKER_00")
            if spk not in speaker_color_map:
                speaker_color_map[spk] = SPEAKER_COLORS[color_idx % len(SPEAKER_COLORS)]
                color_idx += 1
            spk_color = speaker_color_map[spk]

            time_str = fmt_time(utt.get("start_s", 0))
            label    = spk.replace("SPEAKER_", "S")

            spk_style = ParagraphStyle(
                f"spk_{spk}", fontName="Helvetica-Bold",
                fontSize=9, textColor=spk_color, leading=13,
            )

            row = Table(
                [[
                    Paragraph(time_str, styles["mono"]),
                    Paragraph(label,    spk_style),
                    Paragraph(utt.get("text", ""), styles["transcript_text"]),
                ]],
                colWidths=[12*mm, 18*mm, content_width-30*mm],
            )
            row.setStyle(TableStyle([
                ("LEFTPADDING",   (0,0), (-1,-1), 6),
                ("RIGHTPADDING",  (0,0), (-1,-1), 6),
                ("TOPPADDING",    (0,0), (-1,-1), 4),
                ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                ("LINEBELOW",     (0,0), (-1,-1), 0.5, colors.HexColor("#f3e8ff")),
                ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ]))
            story.append(row)

    # ── Footer ───────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER))
    story.append(Spacer(1, 8))
    generated = datetime.now().strftime("%d %b %Y at %H:%M")
    story.append(Paragraph(
        f"Generated by MeetMind on {generated}",
        styles["footer"],
    ))

    doc.build(story)
    return buf.getvalue()