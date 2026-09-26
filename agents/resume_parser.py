import os
import re
import json
import pdfplumber
import PyPDF2
from docx import Document
import core.gemini_client as gemini_module

class ResumeParser:
    async def parse(self, file_path: str) -> dict:
        """
        Parse a resume PDF or DOCX and return structured data.
        Returns a dict with keys: raw_text, name, email, phone, 
        linkedin_url, github_url, years_experience, skills, suggested_roles
        """
        
        # STEP 1: Extract raw text based on file extension
        ext = file_path.lower().split('.')[-1]
        text = ""
        
        if ext == "pdf":
            try:
                with pdfplumber.open(file_path) as pdf:
                    text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            except Exception as e:
                print(f"pdfplumber failed: {e}")
                
            if len(text.strip()) < 100:
                try:
                    reader = PyPDF2.PdfReader(file_path)
                    text = "\n".join(page.extract_text() or "" for page in reader.pages)
                except Exception as e:
                    print(f"PyPDF2 fallback failed: {e}")
                    
        elif ext == "docx":
            try:
                doc = Document(file_path)
                text = "\n".join(p.text for p in doc.paragraphs)
            except Exception as e:
                print(f"python-docx failed: {e}")
        else:
            raise ValueError("Unsupported file type. Use PDF or DOCX.")

        # STEP 2: Extract structured fields using REGEX ONLY
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        email = email_match.group(0) if email_match else None
        
        phone_match = re.search(r'(\+?91[\s-]?)?[6-9]\d{9}', text)
        phone = phone_match.group(0) if phone_match else None
        
        linkedin_match = re.search(r'linkedin\.com/in/[\w-]+', text, re.IGNORECASE)
        linkedin = linkedin_match.group(0) if linkedin_match else None
        
        github_match = re.search(r'github\.com/[\w-]+', text, re.IGNORECASE)
        github = github_match.group(0) if github_match else None

        base_data = {
            "raw_text": text,
            "email": email,
            "phone": phone,
            "linkedin_url": linkedin,
            "github_url": github,
            "name": None,
            "years_experience": 0,
            "skills": [],
            "suggested_roles": []
        }

        # STEP 3: Call Gemini for deeper extraction
        if gemini_module.gemini:
            prompt = f"""Extract information from this resume text. Return ONLY a JSON object with these exact keys:
- name: full name of the candidate (string)
- years_experience: total years of work experience (integer, 0 if fresher)
- skills: array of technical and soft skills found (max 20 items)
- suggested_roles: array of 10 job titles this person could apply for based on their experience

Resume text:
{text[:3000]}"""
            
            try:
                response = await gemini_module.gemini.generate(
                    prompt=prompt, 
                    json_mode=True, 
                    max_tokens=800
                )
                if response:
                    gemini_data = json.loads(response)
                    # Merge with regex, giving regex priority for email/phone if we extracted it via LLM
                    base_data["name"] = gemini_data.get("name")
                    base_data["years_experience"] = gemini_data.get("years_experience", 0)
                    base_data["skills"] = gemini_data.get("skills", [])
                    base_data["suggested_roles"] = gemini_data.get("suggested_roles", [])
            except Exception as e:
                print(f"Gemini resume extraction failed: {e}")

        # STEP 4: Return the complete dict
        return base_data