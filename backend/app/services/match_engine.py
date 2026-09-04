"""
backend/app/services/match_engine.py — Phase 6
─────────────────────────────────────────────────────────────────
AI Match Engine. EXTENDS services/matcher.py — does not replace it.
/match (routes/matching.py) still uses matcher.py's TF-IDF flow
completely unchanged. This module is used by the new automatic
notification pipeline (notification_service.py) and can also be
used anywhere a richer, weighted, explainable score is needed.

Reuses internally:
  - compute_match_score()  (matcher.py) for the Skills component
  - check_eligibility()    (matcher.py) is NOT reused directly here
    because it returns a single pass/fail bundle, whereas Phase 6
    needs each criterion (branch/year/cgpa) as an independent
    weighted component with its own explanation line — so those
    three are computed here using the same eligibility dict shape
    matcher.py already reads (min_year / branches / min_cgpa),
    keeping the data contract identical, not duplicated logic.

Weights (sum to 100, tweak freely — nothing else needs to change):
  Skills Match        40%
  Branch Eligibility   15%
  Academic Year        15%
  CGPA                 10%
  Preferred Role        10%
  Preferred Location    5%
  Remote Preference     5%

Explanation is 100% rule-based (no LLM), per Phase 6 requirements.
─────────────────────────────────────────────────────────────────
"""

from app.services.matcher import compute_match_score

# Modular — change these to retune scoring without touching logic below.
WEIGHTS = {
    "skills":   0.40,
    "branch":   0.15,
    "year":     0.15,
    "cgpa":     0.10,
    "role":     0.10,
    "location": 0.05,
    "remote":   0.05,
}


# ── Individual weighted components ──────────────────────────────

def _skills_component(student: dict, opportunity: dict):
    """Returns (score 0-100, matched_skills, missing_skills)."""
    required = opportunity.get("required_skills") or []
    student_skills = student.get("skills") or []
    student_lower = [s.lower() for s in student_skills]

    if not required:
        return 50.0, [], []

    matched = [s for s in required if s.lower() in student_lower]
    missing = [s for s in required if s.lower() not in student_lower]
    score = compute_match_score(student_skills, opportunity)  # reused, unchanged
    return float(score), matched, missing


def _branch_component(student: dict, opportunity: dict):
    """Returns (score, passed: bool, note)."""
    branches = (opportunity.get("eligibility") or {}).get("branches")
    if not branches:
        return 100.0, True, "No branch restriction"
    if student.get("branch") in branches:
        return 100.0, True, f"Eligible branch ({student.get('branch')})"
    return 0.0, False, f"Open to {', '.join(branches)} only"


def _year_component(student: dict, opportunity: dict):
    min_year = (opportunity.get("eligibility") or {}).get("min_year")
    if not min_year:
        return 100.0, True, "No year restriction"
    year = student.get("year") or 0
    if year >= min_year:
        return 100.0, True, f"Eligible year ({year} >= {min_year})"
    return 0.0, False, f"Requires year {min_year}+ (you are year {year})"


def _cgpa_component(student: dict, opportunity: dict):
    min_cgpa = (opportunity.get("eligibility") or {}).get("min_cgpa")
    if not min_cgpa:
        return 100.0, True, "No CGPA requirement"
    cgpa = student.get("cgpa")
    if cgpa is not None and cgpa >= min_cgpa:
        return 100.0, True, f"CGPA {cgpa} meets requirement ({min_cgpa}+)"
    have = cgpa if cgpa is not None else "no CGPA on file"
    return 0.0, False, f"Requires CGPA {min_cgpa}+ (you have {have})"


def _role_component(student: dict, opportunity: dict):
    """
    Preferred Role — 10% weight. `preferred_role` is an optional profile
    field (no UI to set it yet, per Phase 6 scope). NULL/empty means the
    student never expressed a preference: we award a neutral half-credit
    score rather than fabricating a match or penalizing them for missing
    data they were never asked to provide.
    """
    preferred = (student.get("preferred_role") or "").strip().lower()
    if not preferred:
        return 50.0, "No role preference on file — neutral score"
    title = (opportunity.get("title") or "").lower()
    opp_type = (opportunity.get("type") or "").lower()
    if preferred in title or preferred in opp_type:
        return 100.0, f"Matches your preferred role ({student.get('preferred_role')})"
    return 20.0, f"Doesn't closely match your preferred role ({student.get('preferred_role')})"


def _location_component(student: dict, opportunity: dict):
    """Preferred Location — 5% weight. Same neutral-default policy as role."""
    preferred = (student.get("preferred_location") or "").strip().lower()
    opp_location = (opportunity.get("location") or "").strip().lower()
    if not preferred:
        return 50.0, "No location preference on file — neutral score"
    if not opp_location:
        return 50.0, "Opportunity location not specified — neutral score"
    if preferred in opp_location or opp_location in preferred:
        return 100.0, f"Matches your preferred location ({student.get('preferred_location')})"
    return 20.0, f"Different location ({opportunity.get('location')})"


def _remote_component(student: dict, opportunity: dict):
    """Remote Preference — 5% weight. Same neutral-default policy."""
    pref = (student.get("remote_preference") or "").strip().lower()
    opp_location = (opportunity.get("location") or "").strip().lower()
    is_remote_opp = "remote" in opp_location

    if not pref:
        return 50.0, "No remote preference on file — neutral score"
    if pref == "remote" and is_remote_opp:
        return 100.0, "Remote — matches your preference"
    if pref == "onsite" and not is_remote_opp:
        return 100.0, "On-site — matches your preference"
    if pref == "hybrid":
        return 80.0, "Hybrid preference — partial match"
    return 30.0, "Doesn't match your remote preference"


# ── Public API ────────────────────────────────────────────────────

def evaluate_match(student: dict, opportunity: dict) -> dict:
    """
    Compare ONE student with ONE opportunity.

    student: dict with at least — skills (list), branch, year, cgpa,
             and optionally preferred_role, preferred_location,
             remote_preference (any/all may be None).
    opportunity: dict shape from OpportunityTable.to_dict() (same shape
                 matcher.py already consumes).

    Returns:
      {
        "score": int (0-100, weighted),
        "eligible": bool,               # branch + year + cgpa all pass
        "matched_skills": [...],
        "missing_skills": [...],
        "explanation": {
            "matched": [ "✔ ...", ... ],
            "issues":  [ "✘ ...", ... ],
            "missing_skills": [...],
        },
        "breakdown": { "skills": .., "branch": .., ... },  # per-component 0-100
      }
    """
    skills_score, matched_skills, missing_skills = _skills_component(student, opportunity)
    branch_score, branch_ok, branch_note = _branch_component(student, opportunity)
    year_score, year_ok, year_note = _year_component(student, opportunity)
    cgpa_score, cgpa_ok, cgpa_note = _cgpa_component(student, opportunity)
    role_score, _role_note = _role_component(student, opportunity)
    location_score, _location_note = _location_component(student, opportunity)
    remote_score, _remote_note = _remote_component(student, opportunity)

    total = (
        skills_score * WEIGHTS["skills"]
        + branch_score * WEIGHTS["branch"]
        + year_score * WEIGHTS["year"]
        + cgpa_score * WEIGHTS["cgpa"]
        + role_score * WEIGHTS["role"]
        + location_score * WEIGHTS["location"]
        + remote_score * WEIGHTS["remote"]
    )
    total = round(total)

    eligible = branch_ok and year_ok and cgpa_ok

    matched_lines = []
    if matched_skills:
        if len(matched_skills) <= 5:
            matched_lines.append(f"✔ {', '.join(matched_skills)} matches")
        else:
            matched_lines.append(f"✔ {len(matched_skills)} required skills match")
    if branch_ok:
        matched_lines.append(f"✔ {branch_note}")
    if year_ok:
        matched_lines.append(f"✔ {year_note}")
    if cgpa_ok and (opportunity.get("eligibility") or {}).get("min_cgpa"):
        matched_lines.append(f"✔ {cgpa_note}")

    issue_lines = []
    if not branch_ok:
        issue_lines.append(f"✘ {branch_note}")
    if not year_ok:
        issue_lines.append(f"✘ {year_note}")
    if not cgpa_ok:
        issue_lines.append(f"✘ {cgpa_note}")

    return {
        "score": total,
        "eligible": eligible,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "explanation": {
            "matched": matched_lines,
            "issues": issue_lines,
            "missing_skills": missing_skills,
        },
        "breakdown": {
            "skills":   round(skills_score),
            "branch":   round(branch_score),
            "year":     round(year_score),
            "cgpa":     round(cgpa_score),
            "role":     round(role_score),
            "location": round(location_score),
            "remote":   round(remote_score),
        },
    }
