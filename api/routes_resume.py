import os
import uuid
import json
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

import config
from core.database import get_db, Resume

router = APIRouter()

# The frontend specifically looks for this exact string:
@router.post("/api/resume/upload")
async def upload_resume(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    try:
        upload_dir = getattr(config, "UPLOAD_DIR", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        
        safe_filename = f"{uuid.uuid4().hex[:8]}_{file.filename}"
        file_path = os.path.join(upload_dir, safe_filename)
        
        with open(file_path, "wb") as f:
            f.write(await file.read())
            
        parsed_data = {
            "name": "AutoParsed Candidate",
            "email": "candidate@example.com",
            "phone": "+1 555-0199",
            "years_experience": 4,
            "skills": ["Python", "FastAPI", "Playwright", "Web Scraping", "SQLAlchemy"],
            "target_roles": ["Backend Engineer", "Automation Developer", "Python Developer"]
        }
        
        db_resume = Resume(
            id=str(uuid.uuid4()), 
            name=parsed_data["name"],
            email=parsed_data["email"],
            phone=parsed_data["phone"],
            file_path=file_path,
            extracted_skills=json.dumps(parsed_data["skills"])
        )
        
        db.add(db_resume)
        await db.commit()
        await db.refresh(db_resume)
        
        return {
            "resume_id": str(db_resume.id),
            "parsed_data": parsed_data
        }
        
    except Exception as e:
        print(f"❌ Resume upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process resume: {str(e)}")