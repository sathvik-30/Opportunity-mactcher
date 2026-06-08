from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def compute_match_score(student_skills: list, opportunity: dict) -> int:
    required_skills = opportunity.get("required_skills", [])
    
    # if opportunity needs no specific skills, base score is 50
    if not required_skills:
        return 50
    
    # convert skill lists to strings for TF-IDF
    student_text = " ".join(student_skills).lower()
    required_text = " ".join(required_skills).lower()
    
    # vectorize and compute similarity
    vectorizer = TfidfVectorizer()
    try:
        matrix = vectorizer.fit_transform([student_text, required_text])
        score = cosine_similarity(matrix[0], matrix[1])[0][0]
        return round(score * 100)
    except:
        return 0

def check_eligibility(student: dict, opportunity: dict) -> dict:
    eligibility = opportunity.get("eligibility", {})
    issues = []
    passed = []

    # check year
    min_year = eligibility.get("min_year")
    if min_year and student["year"] < min_year:
        issues.append(f"Requires {min_year}nd year or above")
    else:
        passed.append("Academic year ✓")

    # check branch
    branches = eligibility.get("branches")
    if branches and student["branch"] not in branches:
        issues.append(f"Open to {', '.join(branches)} only")
    else:
        passed.append("Branch eligible ✓")

    # check cgpa
    min_cgpa = eligibility.get("min_cgpa")
    if min_cgpa:
        if not student.get("cgpa") or student["cgpa"] < min_cgpa:
            issues.append(f"Requires minimum CGPA of {min_cgpa}")
        else:
            passed.append(f"CGPA {student['cgpa']} meets requirement ✓")

    return {
        "eligible": len(issues) == 0,
        "passed": passed,
        "issues": issues
    }

def match_student_to_opportunities(student: dict, opportunities: list) -> list:
    results = []

    for opp in opportunities:
        score = compute_match_score(student["skills"], opp)
        eligibility = check_eligibility(student, opp)

        results.append({
            "opportunity": opp,
            "match_score": score,
            "eligibility": eligibility,
            "recommended": score >= 50 and eligibility["eligible"]
        })

    # sort by match score descending
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results