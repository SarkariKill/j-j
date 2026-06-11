# ============================================================
#   agents/mail_agent.py — Send Emails via Gmail SMTP
# ============================================================

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from colorama import Fore, Style
from dotenv import load_dotenv

load_dotenv()

GMAIL_SENDER   = os.getenv("GMAIL_SENDER")
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
COMPANY_NAME   = os.getenv("COMPANY_NAME", "Johnson & Johnson")


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{COMPANY_NAME} HR <{GMAIL_SENDER}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_SENDER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"  {Fore.RED}✘ Mail error: {e}{Style.RESET_ALL}")
        return False


def build_selection_email(candidate: dict, ad_result: dict) -> tuple:
    name          = candidate.get("name", "Candidate")
    role          = candidate.get("applied_role", "the role")
    upn           = ad_result.get("upn") or candidate.get("upn") or "Will be shared separately"
    temp_password = ad_result.get("temp_password") or "Please contact HR for your password"
    matched       = candidate.get("matched_skills_found", [])
    match_pct     = candidate.get("match_percentage", 0)

    subject = f"Congratulations! You have been Selected — {COMPANY_NAME}"

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
      <div style="background-color: #0078d4; padding: 30px; text-align: center;">
        <h1 style="color: white; margin: 0;">🎉 You're Selected!</h1>
        <p style="color: #cce4f7; margin: 8px 0 0;">Welcome to {COMPANY_NAME}</p>
      </div>
      <div style="padding: 30px; background-color: #ffffff;">
        <p style="font-size: 16px;">Dear <strong>{name}</strong>,</p>
        <p>We are thrilled to inform you that you have been <strong>selected</strong> for
        the position of <strong>{role}</strong> at <strong>{COMPANY_NAME}</strong>.</p>
        <p>Your skill profile achieved a <strong>{match_pct}% match</strong> with our requirements.
        Key skills verified: <strong>{', '.join(matched) if matched else 'As evaluated'}</strong>.</p>

        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">
        <h3 style="color: #0078d4;">🔐 Your Portal Credentials</h3>
        <table style="width: 100%; border-collapse: collapse;">
          <tr>
            <td style="padding: 10px; background: #f5f5f5; font-weight: bold; width: 45%;">Login Email (UPN)</td>
            <td style="padding: 10px;">{upn}</td>
          </tr>
          <tr>
            <td style="padding: 10px; background: #f5f5f5; font-weight: bold;">Temporary Password</td>
            <td style="padding: 10px;">{temp_password}</td>
          </tr>
          <tr>
            <td style="padding: 10px; background: #f5f5f5; font-weight: bold;">Role</td>
            <td style="padding: 10px;">Trainee</td>
          </tr>
        </table>
        <p style="color: #d32f2f; font-size: 13px; margin-top: 10px;">
          ⚠ Please change your password on first login.
        </p>

        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">
        <h3 style="color: #0078d4;">📋 Next Steps</h3>
        <ol style="line-height: 1.8;">
          <li>Login to the company portal using the credentials above</li>
          <li>Complete your profile setup</li>
          <li>You will receive an onboarding meeting invite shortly</li>
          <li>Complete the assigned training courses</li>
          <li>Successfully complete training to become a full Employee</li>
        </ol>

        <p style="margin-top: 20px;">We look forward to having you on board!</p>
        <p>Best regards,<br><strong>HR Onboarding Team</strong><br>{COMPANY_NAME}</p>
      </div>
      <div style="background-color: #f5f5f5; padding: 15px; text-align: center;">
        <p style="color: #999; font-size: 12px; margin: 0;">
          This is an automated message from {COMPANY_NAME} Onboarding System.
        </p>
      </div>
    </div>
    """
    return subject, html_body


def build_rejection_email(candidate: dict) -> tuple:
    name      = candidate.get("name", "Candidate")
    role      = candidate.get("applied_role", "the role")
    missing   = candidate.get("missing_skills", [])
    matched   = candidate.get("matched_skills_found", [])
    match_pct = candidate.get("match_percentage", 0)

    subject = f"Application Update — {COMPANY_NAME}"

    missing_list_html = "".join(
        f"<li style='margin: 6px 0; color: #d32f2f;'>❌ <strong>{skill}</strong></li>"
        for skill in missing
    ) if missing else "<li>N/A</li>"

    matched_list_html = "".join(
        f"<li style='margin: 6px 0; color: #2e7d32;'>✅ <strong>{skill}</strong></li>"
        for skill in matched
    ) if matched else "<li>None matched</li>"

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
      <div style="background-color: #455a64; padding: 30px; text-align: center;">
        <h1 style="color: white; margin: 0;">Application Update</h1>
        <p style="color: #cfd8dc; margin: 8px 0 0;">{COMPANY_NAME} — Onboarding Process</p>
      </div>
      <div style="padding: 30px; background-color: #ffffff;">
        <p style="font-size: 16px;">Dear <strong>{name}</strong>,</p>
        <p>Thank you for applying for <strong>{role}</strong> at <strong>{COMPANY_NAME}</strong>.</p>
        <p>After careful evaluation, we regret to inform you that we are unable to move
        forward with your application. Your skill profile achieved a
        <strong>{match_pct}% match</strong> against our requirements (minimum: <strong>60%</strong>).</p>

        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">
        <h3 style="color: #455a64;">📊 Skill Assessment Breakdown</h3>
        <p><strong>Skills Matched:</strong></p>
        <ul style="list-style: none; padding: 0;">{matched_list_html}</ul>
        <p><strong>Skills Missing:</strong></p>
        <ul style="list-style: none; padding: 0;">{missing_list_html}</ul>

        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">
        <h3 style="color: #455a64;">💡 We Encourage You To</h3>
        <ul style="line-height: 1.8;">
          <li>Upskill in the missing technologies listed above</li>
          <li>Re-apply once you have acquired those skills</li>
          <li>Explore free resources: Microsoft Learn, Coursera, YouTube</li>
        </ul>

        <p style="margin-top: 20px;">We wish you the best and hope to see you again!</p>
        <p>Best regards,<br><strong>HR Onboarding Team</strong><br>{COMPANY_NAME}</p>
      </div>
      <div style="background-color: #f5f5f5; padding: 15px; text-align: center;">
        <p style="color: #999; font-size: 12px; margin: 0;">
          This is an automated message from {COMPANY_NAME} Onboarding System.
        </p>
      </div>
    </div>
    """
    return subject, html_body


def send_all_notifications(
    eligible_candidates : list,
    rejected_candidates : list,
    ad_results          : list,
) -> dict:
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"  STEP 5 — Sending Emails via Gmail SMTP")
    print(f"{'='*60}{Style.RESET_ALL}")

    sent_count   = 0
    failed_count = 0

    # Build lookup: candidate_id → AD result
    ad_lookup = {r["candidate_id"]: r for r in ad_results}

    # ── Selection Emails ──────────────────────────────────────
    print(f"\n  {Fore.GREEN}📧 Sending Selection Emails...{Style.RESET_ALL}")
    for candidate in eligible_candidates:
        cid     = candidate["id"]
        ad_info = ad_lookup.get(cid, {})

        subject, html_body = build_selection_email(candidate, ad_info)
        success            = send_email(candidate["email"], subject, html_body)

        if success:
            sent_count += 1
            print(f"  {Fore.GREEN}✔ Selection mail sent → {candidate['name']} ({candidate['email']}){Style.RESET_ALL}")
        else:
            failed_count += 1
            print(f"  {Fore.RED}✘ Failed → {candidate['name']} ({candidate['email']}){Style.RESET_ALL}")

    # ── Rejection Emails ──────────────────────────────────────
    print(f"\n  {Fore.RED}📧 Sending Rejection Emails...{Style.RESET_ALL}")
    for candidate in rejected_candidates:
        subject, html_body = build_rejection_email(candidate)
        success            = send_email(candidate["email"], subject, html_body)

        if success:
            sent_count += 1
            print(f"  {Fore.GREEN}✔ Rejection mail sent → {candidate['name']} ({candidate['email']}){Style.RESET_ALL}")
        else:
            failed_count += 1
            print(f"  {Fore.RED}✘ Failed → {candidate['name']} ({candidate['email']}){Style.RESET_ALL}")

    print(f"\n  📬 Total Sent   : {sent_count}")
    print(f"  ❌ Total Failed : {failed_count}")

    return {"sent": sent_count, "failed": failed_count}