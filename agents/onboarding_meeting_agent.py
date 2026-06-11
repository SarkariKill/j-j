# ============================================================
#   agents/onboarding_meeting_agent.py — Step 7
#   Send Onboarding Meeting Link + Course Portal Link
# ============================================================

import os
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from colorama import Fore, Style
from dotenv import load_dotenv

load_dotenv()

GMAIL_SENDER      = os.getenv("GMAIL_SENDER")
GMAIL_PASSWORD    = os.getenv("GMAIL_APP_PASSWORD")
COMPANY_NAME      = os.getenv("COMPANY_NAME", "Johnson & Johnson")
MEETING_LINK      = os.getenv("ONBOARDING_MEETING_LINK", "https://meet.google.com/your-meeting-link")
COURSE_PORTAL_URL = os.getenv("COURSE_PORTAL_URL", "http://localhost:8000")
MEETING_DURATION  = 60


def get_meeting_schedule() -> dict:
    meeting_date = datetime.now() + timedelta(days=1)
    while meeting_date.weekday() >= 5:
        meeting_date += timedelta(days=1)
    meeting_date = meeting_date.replace(hour=10, minute=0, second=0, microsecond=0)
    return {
        "date"     : meeting_date.strftime("%A, %B %d, %Y"),
        "time"     : meeting_date.strftime("%I:%M %p"),
        "time_zone": "IST (Indian Standard Time)",
        "duration" : f"{MEETING_DURATION} minutes",
        "datetime" : meeting_date,
    }


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


def build_meeting_email(candidate: dict, schedule: dict, attendees: list) -> tuple:
    name         = candidate.get("name", "Candidate")
    role         = candidate.get("applied_role", "Trainee")
    upn          = candidate.get("upn", "")
    candidate_id = candidate.get("id", "")
    match_pct    = candidate.get("match_percentage", 0)

    # Unique course link for this candidate
    course_link  = f"{COURSE_PORTAL_URL}/course/{candidate_id}"

    subject = f"📅 Onboarding Meeting + Course Access — {COMPANY_NAME}"

    attendees_html = "".join(
        f"<li style='margin: 4px 0;'>👤 {a}</li>"
        for a in attendees
    )

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 620px; margin: auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">

      <!-- Header -->
      <div style="background: linear-gradient(135deg, #0078d4, #005a9e); padding: 30px; text-align: center;">
        <h1 style="color: white; margin: 0; font-size: 24px;">📅 Onboarding Meeting</h1>
        <p style="color: #cce4f7; margin: 8px 0 0; font-size: 14px;">
          Welcome to {COMPANY_NAME} — Your journey begins!
        </p>
      </div>

      <div style="padding: 30px; background-color: #ffffff;">
        <p style="font-size: 16px;">Dear <strong>{name}</strong>,</p>
        <p>Congratulations on being selected as a <strong>{role} Trainee</strong> at
        <strong>{COMPANY_NAME}</strong>!</p>

        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">

        <!-- Meeting Details -->
        <div style="background: #f0f7ff; border-left: 4px solid #0078d4; border-radius: 4px; padding: 20px; margin-bottom: 20px;">
          <h3 style="color: #0078d4; margin: 0 0 15px;">📋 Meeting Details</h3>
          <table style="width: 100%; border-collapse: collapse;">
            <tr>
              <td style="padding: 8px 0; font-weight: bold; color: #555; width: 35%;">📅 Date</td>
              <td style="padding: 8px 0;">{schedule['date']}</td>
            </tr>
            <tr>
              <td style="padding: 8px 0; font-weight: bold; color: #555;">⏰ Time</td>
              <td style="padding: 8px 0;">{schedule['time']} {schedule['time_zone']}</td>
            </tr>
            <tr>
              <td style="padding: 8px 0; font-weight: bold; color: #555;">⏱ Duration</td>
              <td style="padding: 8px 0;">{schedule['duration']}</td>
            </tr>
            <tr>
              <td style="padding: 8px 0; font-weight: bold; color: #555;">🔗 Meeting Link</td>
              <td style="padding: 8px 0;">
                <a href="{MEETING_LINK}" style="color: #0078d4; font-weight: bold;">Click to Join Meeting</a>
              </td>
            </tr>
          </table>
        </div>

        <!-- Join Meeting Button -->
        <div style="text-align: center; margin-bottom: 24px;">
          <a href="{MEETING_LINK}"
             style="background-color: #0078d4; color: white; padding: 14px 35px;
                    text-decoration: none; border-radius: 6px; font-size: 16px;
                    font-weight: bold; display: inline-block;">
            🎥 Join Onboarding Meeting
          </a>
        </div>

        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">

        <!-- Course Access Section -->
        <div style="background: #f0fff4; border-left: 4px solid #28a745; border-radius: 4px; padding: 20px; margin-bottom: 20px;">
          <h3 style="color: #28a745; margin: 0 0 12px;">🎓 Your Training Course</h3>
          <p style="margin: 0 0 12px; color: #444;">
            After the meeting, you must complete the assigned training course.
            Your <strong>personal course link</strong> is below — it is unique to you only.
          </p>
          <table style="width: 100%; border-collapse: collapse;">
            <tr>
              <td style="padding: 8px 0; font-weight: bold; color: #555; width: 35%;">🔗 Your Course Link</td>
              <td style="padding: 8px 0;">
                <a href="{course_link}" style="color: #28a745; font-weight: bold; word-break: break-all;">{course_link}</a>
              </td>
            </tr>
            <tr>
              <td style="padding: 8px 0; font-weight: bold; color: #555;">⏰ Deadline</td>
              <td style="padding: 8px 0;">60 minutes from when you first open the link</td>
            </tr>
            <tr>
              <td style="padding: 8px 0; font-weight: bold; color: #555;">✅ Requirement</td>
              <td style="padding: 8px 0;">Watch at least <strong>90%</strong> of the video</td>
            </tr>
            <tr>
              <td style="padding: 8px 0; font-weight: bold; color: #555;">⚠ Important</td>
              <td style="padding: 8px 0; color: #d32f2f;">Skipping is not allowed — system tracks actual watch time</td>
            </tr>
          </table>
        </div>

        <!-- Course Button -->
        <div style="text-align: center; margin-bottom: 24px;">
          <a href="{course_link}"
             style="background: linear-gradient(135deg, #28a745, #20c997); color: white;
                    padding: 14px 35px; text-decoration: none; border-radius: 6px;
                    font-size: 16px; font-weight: bold; display: inline-block;">
            🎓 Open My Training Course
          </a>
        </div>

        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">

        <!-- Fellow Trainees -->
        <h3 style="color: #0078d4;">👥 Fellow Trainees</h3>
        <ul style="list-style: none; padding: 0; background: #f9f9f9; border-radius: 4px; padding: 15px;">
          {attendees_html}
        </ul>

        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">

        <!-- Agenda -->
        <h3 style="color: #0078d4;">📌 Meeting Agenda</h3>
        <ol style="line-height: 2; color: #444;">
          <li>Welcome & Introduction to {COMPANY_NAME}</li>
          <li>Overview of your Training Program</li>
          <li>Portal Access & Tools Walkthrough</li>
          <li>Training Schedule & Course Details</li>
          <li>Expectations & Evaluation Criteria</li>
          <li>Q&A Session</li>
        </ol>

        <!-- Portal Login Reminder -->
        <div style="background: #fff8e1; border-left: 4px solid #ffc107; border-radius: 4px; padding: 15px; margin-top: 20px;">
          <h4 style="margin: 0 0 8px; color: #856404;">⚠ Portal Login Reminder</h4>
          <p style="margin: 0; font-size: 14px; color: #856404;">
            Your UPN: <strong>{upn if upn else 'shared in selection email'}</strong><br>
            Please login before the meeting and change your temporary password.
          </p>
        </div>

        <p style="margin-top: 20px;">Looking forward to meeting you!</p>
        <p>Best regards,<br><strong>HR Onboarding Team</strong><br>{COMPANY_NAME}</p>
      </div>

      <!-- Footer -->
      <div style="background-color: #f5f5f5; padding: 15px; text-align: center;">
        <p style="color: #999; font-size: 12px; margin: 0;">
          This is an automated message from {COMPANY_NAME} Onboarding System.
        </p>
      </div>
    </div>
    """
    return subject, html_body


def send_onboarding_meeting_invites(eligible_candidates: list, ad_results: list) -> dict:
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"  STEP 7 — Sending Onboarding Meeting + Course Invites")
    print(f"{'='*60}{Style.RESET_ALL}")

    if not eligible_candidates:
        print(f"  {Fore.YELLOW}⚠ No eligible candidates.{Style.RESET_ALL}")
        return {"sent": 0, "failed": 0}

    schedule  = get_meeting_schedule()
    attendees = [c.get("name") for c in eligible_candidates]
    ad_lookup = {r["candidate_id"]: r for r in ad_results}

    print(f"\n  📅 Meeting: {schedule['date']} at {schedule['time']}")
    print(f"  🔗 Meeting Link: {MEETING_LINK}")
    print(f"  🎓 Course Portal: {COURSE_PORTAL_URL}")

    sent_count   = 0
    failed_count = 0

    print(f"\n  {Fore.CYAN}📧 Sending Meeting + Course Invites...{Style.RESET_ALL}")

    for candidate in eligible_candidates:
        ad_info          = ad_lookup.get(candidate["id"], {})
        enriched         = {
            **candidate,
            "upn": ad_info.get("upn", candidate.get("upn", "")),
        }

        subject, html_body = build_meeting_email(enriched, schedule, attendees)
        success            = send_email(candidate["email"], subject, html_body)

        if success:
            sent_count += 1
            course_link = f"{COURSE_PORTAL_URL}/course/{candidate['id']}"
            print(f"  {Fore.GREEN}✔ Invite sent → {candidate['name']}{Style.RESET_ALL}")
            print(f"     Course Link: {course_link}")
        else:
            failed_count += 1
            print(f"  {Fore.RED}✘ Failed → {candidate['name']}{Style.RESET_ALL}")

    print(f"\n  📬 Total Sent   : {sent_count}")
    print(f"  ❌ Total Failed : {failed_count}")

    return {
        "sent"        : sent_count,
        "failed"      : failed_count,
        "meeting_date": schedule["date"],
        "meeting_time": schedule["time"],
        "meeting_link": MEETING_LINK,
    }