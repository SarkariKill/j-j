# ============================================================
#   course_portal/app.py — FastAPI Backend for Course Tracking
# ============================================================

import os
import sys
import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from colorama import Fore, Style

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cosmos_client import get_container, update_candidate_status

# Load .env from parent directory
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

app = FastAPI(title="Course Tracking Portal")

COURSE_DEADLINE_MINUTES    = int(os.getenv("COURSE_DEADLINE_MINUTES", "60"))
COURSE_VIDEO_DURATION_SECS = int(os.getenv("COURSE_VIDEO_DURATION_SECONDS", "300"))
YOUTUBE_VIDEO_ID           = os.getenv("YOUTUBE_VIDEO_ID", "")

# ── Template path — works from any directory ──────────────────
TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "course.html")


# ── Request Models ────────────────────────────────────────────
class ProgressUpdate(BaseModel):
    candidate_id     : str
    watched_seconds  : int
    watch_percentage : float


class CompletionRequest(BaseModel):
    candidate_id     : str
    watched_seconds  : int
    watch_percentage : float


# ── Routes ────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html><body style="font-family:Arial; text-align:center; padding:50px; background:#f0f4f8;">
        <h1 style="color:#0078d4;">🎓 Course Portal is Running!</h1>
        <p style="margin:20px 0;">Access your course using your candidate ID:</p>
        <p><a href="/course/candidate_001" style="color:#0078d4;">/course/candidate_001</a></p>
        <p><a href="/course/candidate_003" style="color:#0078d4;">/course/candidate_003</a></p>
        <p><a href="/course/candidate_004" style="color:#0078d4;">/course/candidate_004</a></p>
        <br>
        <p><a href="/admin" style="color:#0078d4; font-weight:bold;">📊 Admin Dashboard</a></p>
    </body></html>
    """


@app.get("/course/{candidate_id}", response_class=HTMLResponse)
async def course_page(candidate_id: str):
    """Serves the course watching page for a candidate."""
    try:
        container = get_container()
        item      = container.read_item(item=candidate_id, partition_key=candidate_id)
    except Exception as e:
        return HTMLResponse(content=f"""
        <html><body style="font-family:Arial; text-align:center; padding:50px; background:#fff3f3;">
            <h1 style="color:#c62828;">❌ Candidate Not Found</h1>
            <p>ID <strong>{candidate_id}</strong> not found in database.</p>
            <p style="color:#888; font-size:13px;">Error: {str(e)}</p>
            <p><a href="/">← Back to Home</a></p>
        </body></html>
        """, status_code=404)

    # Already completed
    if item.get("course_status") == "COMPLETED":
        return HTMLResponse(content=f"""
        <html><body style="font-family:Arial; text-align:center; padding:50px; background:#f0fff0;">
            <h1 style="color:#28a745;">🎉 Course Already Completed!</h1>
            <p>Hi <strong>{item.get('name')}</strong>, you have already completed this course.</p>
            <p>Your certificate will be sent to your email shortly.</p>
        </body></html>
        """)

    # Check if eligible (must have RBAC_ASSIGNED, AD_PROVISIONED or MEETING_INVITED status)
    allowed_statuses = ["RBAC_ASSIGNED", "AD_PROVISIONED", "MEETING_INVITED", "IN_TRAINING", "ELIGIBLE"]
    if item.get("status") not in allowed_statuses:
        return HTMLResponse(content=f"""
        <html><body style="font-family:Arial; text-align:center; padding:50px; background:#fff3f3;">
            <h1 style="color:#c62828;">⛔ Access Denied</h1>
            <p>Hi <strong>{item.get('name')}</strong>, you are not authorized to access this course.</p>
            <p>Current Status: <strong>{item.get('status', 'Unknown')}</strong></p>
        </body></html>
        """, status_code=403)

    # Set course start time on first visit
    if not item.get("course_start_time"):
        update_candidate_status(
            container    = container,
            candidate_id = candidate_id,
            new_status   = "IN_TRAINING",
            extra_fields = {
                "course_status"    : "IN_PROGRESS",
                "course_start_time": datetime.datetime.utcnow().isoformat() + "Z",
                "watch_percentage" : 0,
                "watched_seconds"  : 0,
            }
        )

    # Load and inject variables into HTML template
    try:
        with open(TEMPLATE_PATH, "r") as f:
            html = f.read()
    except FileNotFoundError:
        return HTMLResponse(content=f"""
        <html><body style="font-family:Arial; text-align:center; padding:50px;">
            <h1>❌ Template Error</h1>
            <p>course.html not found at: {TEMPLATE_PATH}</p>
        </body></html>
        """, status_code=500)

    html = html.replace("{{CANDIDATE_ID}}",            candidate_id)
    html = html.replace("{{CANDIDATE_NAME}}",          item.get("name", "Trainee"))
    html = html.replace("{{APPLIED_ROLE}}",            item.get("applied_role", "Trainee"))
    html = html.replace("{{YOUTUBE_VIDEO_ID}}",        YOUTUBE_VIDEO_ID)
    html = html.replace("{{VIDEO_DURATION_SECONDS}}", str(COURSE_VIDEO_DURATION_SECS))
    html = html.replace("{{DEADLINE_MINUTES}}",       str(COURSE_DEADLINE_MINUTES))

    return HTMLResponse(content=html)


@app.post("/api/update-progress")
async def update_progress(data: ProgressUpdate):
    """Called every 30 seconds by frontend to save watch progress."""
    try:
        container = get_container()
        item      = container.read_item(item=data.candidate_id, partition_key=data.candidate_id)

        if item.get("course_status") == "COMPLETED":
            return {"status": "already_completed"}

        item["watch_percentage"] = round(data.watch_percentage, 2)
        item["watched_seconds"]  = data.watched_seconds
        item["last_progress_at"] = datetime.datetime.utcnow().isoformat() + "Z"
        container.replace_item(item=data.candidate_id, body=item)

        return {
            "status"          : "updated",
            "watch_percentage": data.watch_percentage,
            "watched_seconds" : data.watched_seconds,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/complete-course")
async def complete_course(data: CompletionRequest):
    """Called when user clicks Mark Complete."""
    try:
        container = get_container()
        item      = container.read_item(item=data.candidate_id, partition_key=data.candidate_id)

        # Server-side anti-cheat check
        if data.watch_percentage < 90.0:
            raise HTTPException(
                status_code=400,
                detail=f"Must watch at least 90% of video. Current: {data.watch_percentage:.1f}%"
            )

        # Deadline check
        start_time = item.get("course_start_time")
        if start_time:
            start_dt    = datetime.datetime.fromisoformat(start_time.replace("Z", ""))
            elapsed_min = (datetime.datetime.utcnow() - start_dt).total_seconds() / 60
            if elapsed_min > COURSE_DEADLINE_MINUTES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Deadline exceeded. Elapsed: {elapsed_min:.1f} mins"
                )

        update_candidate_status(
            container    = container,
            candidate_id = data.candidate_id,
            new_status   = "COURSE_COMPLETED",
            extra_fields = {
                "course_status"      : "COMPLETED",
                "watch_percentage"   : data.watch_percentage,
                "watched_seconds"    : data.watched_seconds,
                "course_completed_at": datetime.datetime.utcnow().isoformat() + "Z",
            }
        )

        print(f"{Fore.GREEN}✔ Course completed: {item.get('name')} ({data.candidate_id}){Style.RESET_ALL}")
        return {"status": "completed", "message": "Course marked as complete!"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status/{candidate_id}")
async def get_status(candidate_id: str):
    try:
        container = get_container()
        item      = container.read_item(item=candidate_id, partition_key=candidate_id)
        return {
            "candidate_id"    : candidate_id,
            "name"            : item.get("name"),
            "course_status"   : item.get("course_status", "NOT_STARTED"),
            "watch_percentage": item.get("watch_percentage", 0),
            "watched_seconds" : item.get("watched_seconds", 0),
            "status"          : item.get("status"),
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# @app.get("/admin", response_class=HTMLResponse)
# async def admin_dashboard():
#     try:
#         container = get_container()
#         items     = list(container.query_items(
#             query="SELECT c.id, c.name, c.email, c.status, c.course_status, c.watch_percentage, c.course_start_time, c.course_completed_at FROM c",
#             enable_cross_partition_query=True
#         ))

#         rows = ""
#         for item in items:
#             course_status = item.get("course_status", "NOT_STARTED")
#             watch_pct     = item.get("watch_percentage", 0)
#             pipeline_status = item.get("status", "")

#             if course_status == "COMPLETED":
#                 badge = '<span style="background:#4caf50;color:white;padding:4px 10px;border-radius:12px;font-size:12px;">✅ COMPLETED</span>'
#             elif course_status == "IN_PROGRESS":
#                 badge = '<span style="background:#ff9800;color:white;padding:4px 10px;border-radius:12px;font-size:12px;">⏳ IN PROGRESS</span>'
#             elif course_status == "FAILED":
#                 badge = '<span style="background:#f44336;color:white;padding:4px 10px;border-radius:12px;font-size:12px;">❌ FAILED</span>'
#             else:
#                 badge = '<span style="background:#9e9e9e;color:white;padding:4px 10px;border-radius:12px;font-size:12px;">⬜ NOT STARTED</span>'

#             bar_color = "#4caf50" if watch_pct >= 90 else "#0078d4"

#             rows += f"""
#             <tr>
#                 <td style="padding:12px;border-bottom:1px solid #eee;">{item.get('name','—')}</td>
#                 <td style="padding:12px;border-bottom:1px solid #eee;font-size:13px;color:#666;">{item.get('email','—')}</td>
#                 <td style="padding:12px;border-bottom:1px solid #eee;">{badge}</td>
#                 <td style="padding:12px;border-bottom:1px solid #eee;">
#                     <div style="background:#eee;border-radius:4px;height:18px;width:160px;display:inline-block;vertical-align:middle;">
#                         <div style="background:{bar_color};height:18px;border-radius:4px;width:{min(watch_pct,100):.1f}%;"></div>
#                     </div>
#                     <span style="margin-left:8px;font-size:13px;">{watch_pct:.1f}%</span>
#                 </td>
#                 <td style="padding:12px;border-bottom:1px solid #eee;">
#                     <a href="/course/{item.get('id')}" style="color:#0078d4;font-size:13px;">Open Course</a>
#                 </td>
#                 <td style="padding:12px;border-bottom:1px solid #eee;font-size:12px;color:#888;">{pipeline_status}</td>
#             </tr>
#             """

#         return f"""
#         <!DOCTYPE html>
#         <html>
#         <head>
#             <title>Admin Dashboard</title>
#             <meta http-equiv="refresh" content="30">
#             <style>
#                 body {{ font-family: Arial, sans-serif; padding: 30px; background: #f5f5f5; margin: 0; }}
#                 h1 {{ color: #0078d4; margin-bottom: 5px; }}
#                 .subtitle {{ color: #888; font-size: 13px; margin-bottom: 24px; }}
#                 table {{ width: 100%; background: white; border-radius: 10px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); border-collapse: collapse; }}
#                 th {{ background: #0078d4; color: white; padding: 14px 12px; text-align: left; font-size: 14px; }}
#                 th:first-child {{ border-radius: 10px 0 0 0; }}
#                 th:last-child  {{ border-radius: 0 10px 0 0; }}
#                 tr:hover td {{ background: #f8f9fa; }}
#             </style>
#         </head>
#         <body>
#             <h1>🎓 Course Monitor Dashboard</h1>
#             <div class="subtitle">Auto-refreshes every 30 seconds · {len(items)} total candidates</div>
#             <table>
#                 <thead>
#                     <tr>
#                         <th>Name</th>
#                         <th>Email</th>
#                         <th>Course Status</th>
#                         <th>Watch Progress</th>
#                         <th>Course Link</th>
#                         <th>Pipeline Status</th>
#                     </tr>
#                 </thead>
#                 <tbody>{rows}</tbody>
#             </table>
#         </body>
#         </html>
#         """
#     except Exception as e:
#         return HTMLResponse(content=f"<html><body><h2>Error: {str(e)}</h2></body></html>")

@app.get("/api/admin/candidates")
async def admin_candidates_api():
    container = get_container()

    items = list(container.query_items(
        query="SELECT * FROM c",
        enable_cross_partition_query=True
    ))

    candidates = []

    for item in items:
        status = item.get("status", "UNKNOWN")
        course_status = item.get("course_status", "NOT_STARTED")
        watch_percentage = item.get("watch_percentage", 0)

        candidates.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "email": item.get("email"),
            "phone": item.get("phone"),
            "applied_role": item.get("applied_role"),

            "pipeline_status": status,
            "validation_result": item.get("validation_result", "PENDING"),
            "match_percentage": item.get("match_percentage", 0),
            "missing_skills": item.get("missing_skills", []),

            "ad_status": item.get("ad_status", "NOT_CREATED"),
            "upn": item.get("upn", "—"),

            "rbac_role": item.get("rbac_role", "—"),
            "rbac_status": item.get("rbac_status", "NOT_ASSIGNED"),

            "meeting_date": item.get("meeting_date", "—"),
            "meeting_time": item.get("meeting_time", "—"),
            "meeting_link": item.get("meeting_link", "—"),

            "course_status": course_status,
            "watch_percentage": watch_percentage,
            "watched_seconds": item.get("watched_seconds", 0),
            "course_start_time": item.get("course_start_time", "—"),
            "course_completed_at": item.get("course_completed_at", "—"),

            "certificate_sent": item.get("certificate_sent", False),
            "certificate_sent_at": item.get("certificate_sent_at", "—"),

            "promotion_status": item.get("promotion_status", "—"),
            "promoted_at": item.get("promoted_at", "—"),
        })

    return {
        "total": len(candidates),
        "candidates": candidates
    }


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Live Pipeline Dashboard</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f4f7fb;
            margin: 0;
            padding: 24px;
        }

        h1 {
            color: #0f172a;
            margin-bottom: 5px;
        }

        .subtitle {
            color: #64748b;
            margin-bottom: 20px;
        }

        .stats {
            display: flex;
            gap: 14px;
            margin-bottom: 22px;
            flex-wrap: wrap;
        }

        .card {
            background: white;
            padding: 16px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            min-width: 160px;
        }

        .card h2 {
            margin: 0;
            font-size: 26px;
            color: #2563eb;
        }

        .card p {
            margin: 4px 0 0;
            color: #64748b;
            font-size: 13px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        }

        th {
            background: #2563eb;
            color: white;
            padding: 12px;
            text-align: left;
            font-size: 13px;
        }

        td {
            padding: 12px;
            border-bottom: 1px solid #e5e7eb;
            font-size: 13px;
            vertical-align: top;
        }

        tr:hover td {
            background: #f8fafc;
        }

        .badge {
            padding: 5px 9px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: bold;
            display: inline-block;
        }

        .green { background: #dcfce7; color: #166534; }
        .blue { background: #dbeafe; color: #1d4ed8; }
        .orange { background: #ffedd5; color: #c2410c; }
        .red { background: #fee2e2; color: #b91c1c; }
        .gray { background: #e5e7eb; color: #374151; }
        .purple { background: #ede9fe; color: #6d28d9; }

        .progress-wrap {
            width: 140px;
            height: 14px;
            background: #e5e7eb;
            border-radius: 999px;
            overflow: hidden;
            margin-top: 5px;
        }

        .progress-bar {
            height: 100%;
            background: #22c55e;
        }

        .small {
            color: #64748b;
            font-size: 12px;
            margin-top: 4px;
        }

        a {
            color: #2563eb;
            text-decoration: none;
            font-weight: bold;
        }
    </style>
</head>
<body>

    <h1>🚀 Admin Live Pipeline Dashboard</h1>
    <div class="subtitle">
        Auto refresh every 5 seconds · Last updated: <span id="lastUpdated">Loading...</span>
    </div>

    <div class="stats">
        <div class="card">
            <h2 id="total">0</h2>
            <p>Total Candidates</p>
        </div>
        <div class="card">
            <h2 id="inPipeline">0</h2>
            <p>In Pipeline</p>
        </div>
        <div class="card">
            <h2 id="training">0</h2>
            <p>In Training</p>
        </div>
        <div class="card">
            <h2 id="completed">0</h2>
            <p>Course Completed</p>
        </div>
        <div class="card">
            <h2 id="certificates">0</h2>
            <p>Certificates Sent</p>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Candidate</th>
                <th>Pipeline Step</th>
                <th>Validation</th>
                <th>Azure AD</th>
                <th>RBAC</th>
                <th>Meeting</th>
                <th>Course Progress</th>
                <th>Certificate</th>
                <th>Promotion</th>
                <th>Links</th>
            </tr>
        </thead>
        <tbody id="candidateRows">
            <tr>
                <td colspan="10">Loading...</td>
            </tr>
        </tbody>
    </table>

<script>
function badge(text, type) {
    return `<span class="badge ${type}">${text}</span>`;
}

function statusColor(status) {
    if (!status) return "gray";

    if (
        status.includes("CERTIFICATE") ||
        status.includes("COMPLETED") ||
        status.includes("EMPLOYEE") ||
        status.includes("ASSIGNED") ||
        status.includes("CREATED") ||
        status.includes("INVITED")
    ) return "green";

    if (
        status.includes("PENDING") ||
        status.includes("PROVISIONED") ||
        status.includes("TRAINING")
    ) return "blue";

    if (
        status.includes("FAILED") ||
        status.includes("REJECTED") ||
        status.includes("REMOVED")
    ) return "red";

    return "orange";
}

async function loadDashboard() {
    try {
        const res = await fetch("/api/admin/candidates");
        const data = await res.json();

        const candidates = data.candidates || [];

        document.getElementById("total").innerText = candidates.length;
        document.getElementById("inPipeline").innerText = candidates.filter(c =>
            !["CERTIFICATE_SENT", "EMPLOYEE", "REJECTED", "REMOVED"].includes(c.pipeline_status)
        ).length;
        document.getElementById("training").innerText = candidates.filter(c =>
            c.course_status === "IN_PROGRESS"
        ).length;
        document.getElementById("completed").innerText = candidates.filter(c =>
            c.course_status === "COMPLETED"
        ).length;
        document.getElementById("certificates").innerText = candidates.filter(c =>
            c.certificate_sent === true
        ).length;

        document.getElementById("lastUpdated").innerText = new Date().toLocaleTimeString();

        let rows = "";

        candidates.forEach(c => {
            const progress = Number(c.watch_percentage || 0).toFixed(1);

            rows += `
                <tr>
                    <td>
                        <strong>${c.name}</strong>
                        <div class="small">${c.email}</div>
                        <div class="small">${c.id}</div>
                    </td>

                    <td>
                        ${badge(c.pipeline_status, statusColor(c.pipeline_status))}
                    </td>

                    <td>
                        ${badge(c.validation_result, statusColor(c.validation_result))}
                        <div class="small">Match: ${c.match_percentage}%</div>
                        <div class="small">Missing: ${(c.missing_skills || []).join(", ") || "None"}</div>
                    </td>

                    <td>
                        ${badge(c.ad_status, statusColor(c.ad_status))}
                        <div class="small">${c.upn}</div>
                    </td>

                    <td>
                        ${badge(c.rbac_status, statusColor(c.rbac_status))}
                        <div class="small">Role: ${c.rbac_role}</div>
                    </td>

                    <td>
                        <div>${c.meeting_date}</div>
                        <div class="small">${c.meeting_time}</div>
                        <div class="small">${c.meeting_link !== "—" ? "Meeting Generated" : "No Meeting Yet"}</div>
                    </td>

                    <td>
                        ${badge(c.course_status, statusColor(c.course_status))}
                        <div class="progress-wrap">
                            <div class="progress-bar" style="width:${progress}%"></div>
                        </div>
                        <div class="small">${progress}% watched</div>
                        <div class="small">${c.watched_seconds || 0} sec watched</div>
                    </td>

                    <td>
                        ${c.certificate_sent
                            ? badge("CERTIFICATE SENT", "green")
                            : badge("NOT SENT", "gray")}
                        <div class="small">${c.certificate_sent_at}</div>
                    </td>

                    <td>
                        ${badge(c.promotion_status, statusColor(c.promotion_status))}
                        <div class="small">${c.promoted_at}</div>
                    </td>

                    <td>
                        <a href="/course/${c.id}" target="_blank">Open Course</a>
                    </td>
                </tr>
            `;
        });

        document.getElementById("candidateRows").innerHTML = rows || `
            <tr><td colspan="10">No candidates found.</td></tr>
        `;

    } catch (err) {
        document.getElementById("candidateRows").innerHTML = `
            <tr><td colspan="10">Error loading dashboard: ${err}</td></tr>
        `;
    }
}

loadDashboard();
setInterval(loadDashboard, 5000);
</script>

</body>
</html>
    """