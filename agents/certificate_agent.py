# ============================================================
#   agents/certificate_agent.py — Step 10
#   Generate PDF Certificate + Send via Gmail
# ============================================================

import os
import io
import smtplib
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from colorama import Fore, Style
from dotenv import load_dotenv

load_dotenv()

GMAIL_SENDER   = os.getenv("GMAIL_SENDER")
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
COMPANY_NAME   = os.getenv("COMPANY_NAME", "Johnson & Johnson")


def generate_certificate_pdf(candidate: dict) -> bytes:
    """
    Generates a professional PDF certificate using reportlab.
    Returns PDF as bytes.
    """
    try:
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch, cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.platypus import Table, TableStyle
    except ImportError:
        raise ImportError("reportlab not installed. Run: pip install reportlab")

    name          = candidate.get("name", "Trainee")
    role          = candidate.get("applied_role", "Software Engineer")
    completed_at  = candidate.get("course_completed_at", datetime.datetime.utcnow().isoformat() + "Z")
    watch_pct     = candidate.get("watch_percentage", 100)

    # Parse date
    try:
        dt           = datetime.datetime.fromisoformat(completed_at.replace("Z", ""))
        date_str     = dt.strftime("%B %d, %Y")
    except Exception:
        date_str     = datetime.datetime.now().strftime("%B %d, %Y")

    # Certificate ID
    cert_id = f"CERT-{candidate.get('id', 'XXX').upper()}-{dt.strftime('%Y%m%d')}"

    # ── Build PDF in memory ───────────────────────────────────
    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(
        buffer,
        pagesize    = landscape(A4),
        rightMargin = 1.5 * cm,
        leftMargin  = 1.5 * cm,
        topMargin   = 1.5 * cm,
        bottomMargin= 1.5 * cm,
    )

    # ── Color Palette ─────────────────────────────────────────
    DARK_BLUE  = colors.HexColor("#0078d4")
    NAVY       = colors.HexColor("#003d6b")
    GOLD       = colors.HexColor("#c9a227")
    LIGHT_BLUE = colors.HexColor("#e8f4fd")
    DARK_GRAY  = colors.HexColor("#333333")
    MID_GRAY   = colors.HexColor("#666666")

    # ── Styles ────────────────────────────────────────────────
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "Title",
        parent    = styles["Normal"],
        fontSize  = 38,
        fontName  = "Helvetica-Bold",
        textColor = NAVY,
        alignment = TA_CENTER,
        spaceAfter= 4,
    )

    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent    = styles["Normal"],
        fontSize  = 13,
        fontName  = "Helvetica",
        textColor = DARK_BLUE,
        alignment = TA_CENTER,
        spaceAfter= 2,
    )

    label_style = ParagraphStyle(
        "Label",
        parent    = styles["Normal"],
        fontSize  = 12,
        fontName  = "Helvetica",
        textColor = MID_GRAY,
        alignment = TA_CENTER,
    )

    name_style = ParagraphStyle(
        "Name",
        parent    = styles["Normal"],
        fontSize  = 36,
        fontName  = "Helvetica-BoldOblique",
        textColor = DARK_BLUE,
        alignment = TA_CENTER,
        spaceAfter= 4,
    )

    course_style = ParagraphStyle(
        "Course",
        parent    = styles["Normal"],
        fontSize  = 16,
        fontName  = "Helvetica-Bold",
        textColor = NAVY,
        alignment = TA_CENTER,
    )

    small_style = ParagraphStyle(
        "Small",
        parent    = styles["Normal"],
        fontSize  = 10,
        fontName  = "Helvetica",
        textColor = MID_GRAY,
        alignment = TA_CENTER,
    )

    footer_style = ParagraphStyle(
        "Footer",
        parent    = styles["Normal"],
        fontSize  = 9,
        fontName  = "Helvetica",
        textColor = MID_GRAY,
        alignment = TA_CENTER,
    )

    # ── Build Content ─────────────────────────────────────────
    story = []

    # Top gold line
    story.append(HRFlowable(width="100%", thickness=4, color=GOLD, spaceAfter=12))

    # Company name
    story.append(Paragraph(COMPANY_NAME.upper(), ParagraphStyle(
        "CompanyName",
        parent    = styles["Normal"],
        fontSize  = 14,
        fontName  = "Helvetica-Bold",
        textColor = GOLD,
        alignment = TA_CENTER,
        spaceAfter= 2,
    )))

    # Certificate title
    story.append(Paragraph("Certificate of Completion", title_style))
    story.append(Spacer(1, 0.1 * inch))

    # Thin blue line
    story.append(HRFlowable(width="60%", thickness=1, color=DARK_BLUE, spaceAfter=12))

    # Presented to
    story.append(Paragraph("This is to certify that", label_style))
    story.append(Spacer(1, 0.08 * inch))

    # Candidate name (big)
    story.append(Paragraph(name, name_style))

    # Underline for name
    story.append(HRFlowable(width="50%", thickness=1, color=GOLD, spaceAfter=10))

    # Has successfully completed
    story.append(Paragraph("has successfully completed the", label_style))
    story.append(Spacer(1, 0.06 * inch))

    # Course name
    story.append(Paragraph(f"{COMPANY_NAME} Onboarding Training Program", course_style))
    story.append(Spacer(1, 0.04 * inch))
    story.append(Paragraph(f"for the role of <b>{role}</b>", subtitle_style))
    story.append(Spacer(1, 0.1 * inch))

    # Stats table
    stats_data = [
        ["📅 Completion Date", "🎯 Watch Score", "✅ Status", "🏢 Department"],
        [date_str, f"{watch_pct:.1f}%", "PASSED", role],
    ]

    stats_table = Table(stats_data, colWidths=[2.5*inch, 2*inch, 1.8*inch, 2.5*inch])
    stats_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), DARK_BLUE),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0), 10),
        ("BACKGROUND",   (0, 1), (-1, 1), LIGHT_BLUE),
        ("FONTNAME",     (0, 1), (-1, 1), "Helvetica"),
        ("FONTSIZE",     (0, 1), (-1, 1), 11),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[LIGHT_BLUE]),
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.white),
        ("ROWHEIGHT",    (0, 0), (-1, -1), 28),
        ("ROUNDEDCORNERS", [4]),
    ]))

    story.append(stats_table)
    story.append(Spacer(1, 0.15 * inch))

    # Signatures row
    sig_data = [[
        Paragraph("________________________<br/><b>HR Manager</b><br/><font size=9 color=grey>Human Resources</font>", ParagraphStyle("sig", parent=styles["Normal"], alignment=TA_CENTER, fontSize=11)),
        Paragraph(f"<font color='#c9a227' size=28>★</font>", ParagraphStyle("star", parent=styles["Normal"], alignment=TA_CENTER, fontSize=28)),
        Paragraph("________________________<br/><b>Training Head</b><br/><font size=9 color=grey>Learning & Development</font>", ParagraphStyle("sig2", parent=styles["Normal"], alignment=TA_CENTER, fontSize=11)),
    ]]

    sig_table = Table(sig_data, colWidths=[3*inch, 1.5*inch, 3*inch])
    sig_table.setStyle(TableStyle([
        ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 0.1 * inch))

    # Certificate ID footer
    story.append(Paragraph(f"Certificate ID: {cert_id}", small_style))
    story.append(Spacer(1, 0.06 * inch))

    # Bottom gold line
    story.append(HRFlowable(width="100%", thickness=4, color=GOLD, spaceBefore=6))
    story.append(Paragraph(
        f"{COMPANY_NAME} · Onboarding Automation System · {date_str}",
        footer_style
    ))

    # Build PDF
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes


def send_certificate_email(candidate: dict) -> bool:
    """
    Generates PDF certificate and sends it via Gmail with HTML email.
    """
    name     = candidate.get("name", "Candidate")
    email    = candidate.get("email", "")
    role     = candidate.get("applied_role", "Trainee")
    watch_pct= candidate.get("watch_percentage", 100)

    if not email:
        print(f"  {Fore.RED}✘ No email found for {name}{Style.RESET_ALL}")
        return False

    print(f"\n  📜 Generating certificate for: {name}")

    # ── Generate PDF ──────────────────────────────────────────
    try:
        pdf_bytes = generate_certificate_pdf(candidate)
        print(f"  {Fore.GREEN}✔ PDF generated ({len(pdf_bytes)} bytes){Style.RESET_ALL}")
    except Exception as e:
        print(f"  {Fore.RED}✘ PDF generation failed: {e}{Style.RESET_ALL}")
        return False

    # ── Build Email ───────────────────────────────────────────
    subject = f"🏆 Your Completion Certificate — {COMPANY_NAME}"

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">

      <div style="background: linear-gradient(135deg, #0078d4, #003d6b); padding: 30px; text-align: center;">
        <div style="font-size: 60px; margin-bottom: 10px;">🏆</div>
        <h1 style="color: white; margin: 0;">Congratulations!</h1>
        <p style="color: #cce4f7; margin: 8px 0 0;">Course Successfully Completed</p>
      </div>

      <div style="padding: 30px; background-color: #ffffff;">
        <p style="font-size: 16px;">Dear <strong>{name}</strong>,</p>

        <p>We are proud to inform you that you have <strong>successfully completed</strong>
        the <strong>{COMPANY_NAME} Onboarding Training Program</strong> for the role of
        <strong>{role}</strong>.</p>

        <div style="background: #f0f7ff; border-left: 4px solid #0078d4; border-radius: 4px; padding: 20px; margin: 20px 0;">
          <h3 style="color: #0078d4; margin: 0 0 12px;">📊 Your Achievement</h3>
          <table style="width:100%; border-collapse:collapse;">
            <tr>
              <td style="padding:8px 0; font-weight:bold; color:#555; width:50%;">Course Completed</td>
              <td style="padding:8px 0;">{COMPANY_NAME} Onboarding Program</td>
            </tr>
            <tr>
              <td style="padding:8px 0; font-weight:bold; color:#555;">Video Watch Score</td>
              <td style="padding:8px 0;"><strong style="color:#28a745;">{watch_pct:.1f}%</strong></td>
            </tr>
            <tr>
              <td style="padding:8px 0; font-weight:bold; color:#555;">Status</td>
              <td style="padding:8px 0;"><strong style="color:#28a745;">✅ PASSED</strong></td>
            </tr>
            <tr>
              <td style="padding:8px 0; font-weight:bold; color:#555;">Role</td>
              <td style="padding:8px 0;">{role}</td>
            </tr>
          </table>
        </div>

        <p>📎 Your <strong>official certificate</strong> is attached to this email as a PDF.
        Please save it for your records.</p>

        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">

        <h3 style="color: #0078d4;">🚀 What Happens Next</h3>
        <ol style="line-height: 2; color: #444;">
          <li>Your profile will be upgraded from <strong>Trainee → Employee</strong></li>
          <li>Your RBAC role will be upgraded from <strong>Learner → Contributor</strong></li>
          <li>You will receive <strong>additional portal access</strong></li>
          <li>Your <strong>JIRA account</strong> will be provisioned shortly</li>
        </ol>

        <p style="margin-top: 20px;">Welcome to the team! 🎉</p>
        <p>Best regards,<br><strong>HR Onboarding Team</strong><br>{COMPANY_NAME}</p>
      </div>

      <div style="background: linear-gradient(135deg, #c9a227, #a07820); padding: 15px; text-align: center;">
        <p style="color: white; font-size: 13px; margin: 0; font-weight: bold;">
          🌟 {COMPANY_NAME} — Onboarding Automation System
        </p>
      </div>
    </div>
    """

    # ── Send Email with PDF attachment ────────────────────────
    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"]    = f"{COMPANY_NAME} HR <{GMAIL_SENDER}>"
        msg["To"]      = email

        # HTML body
        msg.attach(MIMEText(html_body, "html"))

        # PDF attachment
        pdf_part = MIMEBase("application", "pdf")
        pdf_part.set_payload(pdf_bytes)
        encoders.encode_base64(pdf_part)
        safe_name = name.replace(" ", "_")
        pdf_part.add_header(
            "Content-Disposition",
            f'attachment; filename="{safe_name}_Certificate.pdf"'
        )
        msg.attach(pdf_part)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_SENDER, email, msg.as_string())

        print(f"  {Fore.GREEN}✔ Certificate email sent → {name} ({email}){Style.RESET_ALL}")
        return True

    except Exception as e:
        print(f"  {Fore.RED}✘ Email send failed: {e}{Style.RESET_ALL}")
        return False


def process_completed_trainees(completed_candidates: list, container) -> list:
    """
    Main Step 10 function:
    Generates and sends certificate to all COURSE_COMPLETED candidates.
    """
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"  STEP 10 — Generating & Sending Certificates")
    print(f"{'='*60}{Style.RESET_ALL}")

    if not completed_candidates:
        print(f"  {Fore.YELLOW}⚠ No completed candidates.{Style.RESET_ALL}")
        return []

    results = []

    for candidate in completed_candidates:
        name = candidate.get("name", "Unknown")
        cid  = candidate["id"]

        success = send_certificate_email(candidate)

        # if success:
        #     from cosmos_client import update_candidate_status
        #     update_candidate_status(
        #         container    = container,
        #         candidate_id = cid,
        #         new_status   = "CERTIFICATE_SENT",
        #         extra_fields = {
        #             "certificate_sent"   : True,
        #             "certificate_sent_at": datetime.datetime.utcnow().isoformat() + "Z",
        #         }
        #     )

        # results.append({
        #     "candidate_id"   : cid,
        #     "name"           : name,
        #     "certificate_sent": success,
        # })
        if success:
            from cosmos_client import update_candidate_status

            update_candidate_status(
                container    = container,
                candidate_id = cid,
                new_status   = "EMPLOYEE",
                extra_fields = {
                    "certificate_sent"   : True,
                    "certificate_sent_at": datetime.datetime.utcnow().isoformat() + "Z",

                    # RBAC upgrade after certificate
                    "rbac_role"          : "Contributor",
                    "rbac_status"        : "PROMOTED_TO_CONTRIBUTOR",
                    "promotion_status"   : "PROMOTED",
                    "promoted_at"        : datetime.datetime.utcnow().isoformat() + "Z",
                }
            )

            print(f"  ✔ {name} promoted: Learner → Contributor")  
            
            from cosmos_client import update_candidate_status

            update_candidate_status(
                container    = container,
                candidate_id = cid,
                new_status   = "EMPLOYEE",
                extra_fields = {
                    "certificate_sent"   : True,
                    "certificate_sent_at": datetime.datetime.utcnow().isoformat() + "Z",

                    "rbac_role"          : "Contributor",
                    "rbac_status"        : "PROMOTED_TO_CONTRIBUTOR",
                    "promotion_status"   : "PROMOTED",
                    "promoted_at"        : datetime.datetime.utcnow().isoformat() + "Z",

                    # Jira access request
                    "jira_access_status"      : "REQUESTED",
                    "jira_access_requested_at": datetime.datetime.utcnow().isoformat() + "Z",
                    "jira_access_granted_at"  : None,
                    "jira_access_rejected_at" : None,
                }
            )

            print(f"  ✔ {name} promoted: Learner → Contributor")
            print(f"  🎫 Jira access request created for {name}") 

    sent   = sum(1 for r in results if r["certificate_sent"])
    failed = sum(1 for r in results if not r["certificate_sent"])
    print(f"\n  ✅ Certificates Sent : {sent}")
    print(f"  ❌ Failed            : {failed}")

    return results