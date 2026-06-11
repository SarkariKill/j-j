# ============================================================
#   agents/iam_validation_agent.py — Rule-Based Skill Matching
#   No LLM needed — fast, free, offline, always consistent
# ============================================================

from colorama import Fore, Style

# ── Skill Synonym Map ─────────────────────────────────────────
SKILL_SYNONYMS = {
    "python": "python", "python3": "python", "py": "python",
    "javascript": "javascript", "js": "javascript", "es6": "javascript",
    "react": "react", "reactjs": "react", "react.js": "react",
    "node": "nodejs", "nodejs": "nodejs", "node.js": "nodejs",
    "java": "java", "java8": "java", "java11": "java",
    "docker": "docker", "docker container": "docker",
    "kubernetes": "kubernetes", "k8s": "kubernetes",
    "azure": "azure", "microsoft azure": "azure", "az": "azure",
    "aws": "aws", "amazon web services": "aws",
    "sql": "sql", "mysql": "sql", "postgresql": "sql",
    "postgres": "sql", "mssql": "sql",
    "mongodb": "mongodb", "mongo": "mongodb",
    "machine learning": "ml", "ml": "ml",
    "deep learning": "ml", "dl": "ml",
    "rest apis": "rest", "rest api": "rest", "rest": "rest",
    "restful": "rest", "api": "rest",
    "spring boot": "springboot", "springboot": "springboot", "spring": "springboot",
    "tensorflow": "tensorflow", "tf": "tensorflow",
    "git": "git", "github": "git", "gitlab": "git",
    "linux": "linux", "ubuntu": "linux", "unix": "linux",
}

MATCH_THRESHOLD_PERCENT = 60


def normalize_skill(skill: str) -> str:
    cleaned = skill.lower().strip()
    return SKILL_SYNONYMS.get(cleaned, cleaned)


def run_iam_validation(candidate: dict) -> dict:
    candidate_name   = candidate.get("name", "Unknown")
    candidate_skills = candidate.get("skillset", [])
    required_skills  = candidate.get("company_required_skills", [])
    applied_role     = candidate.get("applied_role", "Unknown Role")

    print(f"\n{Fore.CYAN}🤖 Running IAM Validation for: {candidate_name}{Style.RESET_ALL}")
    print(f"   Applied Role    : {applied_role}")
    print(f"   Candidate Skills: {candidate_skills}")
    print(f"   Required Skills : {required_skills}")

    normalized_candidate = set(normalize_skill(s) for s in candidate_skills)
    normalized_required  = [normalize_skill(s) for s in required_skills]

    matched_skills = []
    missing_skills = []

    for req_skill in normalized_required:
        original = next(
            (s for s in required_skills if normalize_skill(s) == req_skill), req_skill
        )
        if req_skill in normalized_candidate:
            matched_skills.append(original)
        else:
            missing_skills.append(original)

    total            = len(normalized_required)
    match_count      = len(matched_skills)
    match_percentage = round((match_count / total) * 100) if total > 0 else 0
    decision         = "ELIGIBLE" if match_percentage >= MATCH_THRESHOLD_PERCENT else "REJECTED"

    if decision == "ELIGIBLE":
        reasoning = (
            f"Candidate matched {match_count}/{total} required skills "
            f"({match_percentage}%) — meets the {MATCH_THRESHOLD_PERCENT}% threshold."
        )
    else:
        reasoning = (
            f"Candidate matched {match_count}/{total} required skills "
            f"({match_percentage}%) — below the {MATCH_THRESHOLD_PERCENT}% threshold. "
            f"Missing: {', '.join(missing_skills)}."
        )

    color = Fore.GREEN if decision == "ELIGIBLE" else Fore.RED
    icon  = "✅" if decision == "ELIGIBLE" else "❌"

    print(f"\n   {icon} Decision        : {color}{decision}{Style.RESET_ALL}")
    print(f"   📊 Match %        : {match_percentage}%")
    print(f"   ✔  Matched Skills : {matched_skills}")
    print(f"   ✘  Missing Skills : {missing_skills}")
    print(f"   💬 Reasoning      : {reasoning}")

    return {
        "decision"        : decision,
        "match_percentage": match_percentage,
        "matched_skills"  : matched_skills,
        "missing_skills"  : missing_skills,
        "reasoning"       : reasoning,
    }