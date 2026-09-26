import os
import uuid
import json
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

import config
from core.database import get_db, Resume

router = APIRouter()

@router.post("/api/resume/upload")
async def upload_resume(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    try:
        # 1. Save the uploaded file
        upload_dir = getattr(config, "UPLOAD_DIR", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        
        safe_filename = f"{uuid.uuid4().hex[:8]}_{file.filename}"
        file_path = os.path.join(upload_dir, safe_filename)
        
        with open(file_path, "wb") as f:
            f.write(await file.read())
            
        # 2. Parse the resume (Placeholder logic)
        parsed_data = {
            "name": "AutoParsed Candidate",
            "email": "candidate@example.com",
            "phone": "+1 555-0199",
            "years_experience": 4,
            "skills": ["Python", "FastAPI", "Playwright", "Web Scraping", "SQLAlchemy"],
            "target_roles": ["Backend Engineer", "Automation Developer", "Python Developer"]
        }
        
        # 3. Save to Database using EXACT column names from database.py
        db_resume = Resume(
            filename=file_path, # We store the path in 'filename' so the orchestrator can find it
            raw_text="Extracted text placeholder...", # Required by database.py (nullable=False)
            extracted_name=parsed_data["name"],
            extracted_email=parsed_data["email"],
            extracted_phone=parsed_data["phone"],
            years_experience=parsed_data["years_experience"],
            extracted_skills=json.dumps(parsed_data["skills"]),
            suggested_roles=json.dumps(parsed_data["target_roles"])
        )
        
        db.add(db_resume)
        await db.commit()
        await db.refresh(db_resume)
        
        # 4. Return exact JSON structure expected by frontend/index.html
        return {
            "resume_id": str(db_resume.id),
            "parsed_data": parsed_data
        }
        
    except Exception as e:
        print(f"❌ Resume upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process resume: {str(e)}")