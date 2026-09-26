import json
import core.gemini_client as gemini_module

class SkillExtractor:
    async def analyze_job_fit(self, resume_skills: list[str], job_description: str) -> dict:
        """
        Returns: {match_score: int, recommendation: str, matched_skills: list, missing_skills: list}
        recommendation is one of: STRONG_APPLY / APPLY / REVIEW / SKIP
        """
        
        # TIER 1 — Local keyword matching (no Gemini, instant)
        jd_lower = job_description.lower()
        matched_skills = []
        missing_skills = []
        
        for skill in resume_skills:
            if skill.lower() in jd_lower:
                matched_skills.append(skill)
            else:
                missing_skills.append(skill)
                
        quick_score = int((len(matched_skills) / max(len(resume_skills), 1)) * 100)
        
        tier1_result = {
            "match_score": quick_score,
            "recommendation": "",
            "matched_skills": matched_skills,
            "missing_skills": missing_skills
        }
        
        if quick_score >= 65:
            tier1_result["recommendation"] = "STRONG_APPLY"
            return tier1_result
            
        if quick_score < 20:
            tier1_result["recommendation"] = "SKIP"
            return tier1_result
            
        # TIER 2 — Gemini for the 20-65 range (nuanced analysis)
        if gemini_module.gemini:
            safe_skills = resume_skills[:15] if resume_skills else ["None provided"]
            prompt = f"""Analyze job fit. 
Candidate skills: {', '.join(safe_skills)}
Job description (first 500 chars): {job_description[:500]}

Return JSON with:
- match_score: integer 0-100
- recommendation: one of STRONG_APPLY, APPLY, REVIEW, SKIP
- matched_skills: array of skills that match
- missing_skills: array of important skills the candidate lacks
"""
            try:
                response = await gemini_module.gemini.generate(
                    prompt=prompt, 
                    json_mode=True, 
                    max_tokens=400
                )
                if response:
                    data = json.loads(response)
                    # Validate keys exist
                    return {
                        "match_score": int(data.get("match_score", quick_score)),
                        "recommendation": data.get("recommendation", "REVIEW"),
                        "matched_skills": data.get("matched_skills", matched_skills),
                        "missing_skills": data.get("missing_skills", missing_skills)
                    }
            except Exception as e:
                print(f"SkillExtractor Gemini fallback triggered due to error: {e}")
                
        # Fallback if Gemini fails or is not initialized
        tier1_result["recommendation"] = "REVIEW"
        return tier1_result