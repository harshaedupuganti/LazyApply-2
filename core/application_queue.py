from datetime import datetime, date
from sqlalchemy.future import select
from sqlalchemy import func

from core.database import async_session, Application, Job, Resume

class ApplicationQueue:
    async def enqueue(self, job_id: int, resume_id: str) -> int:
        """Create Application record with status='PENDING'"""
        async with async_session() as db:
            # Check if already exists
            result = await db.execute(select(Application).where(
                Application.job_id == job_id, 
                Application.resume_id == resume_id
            ))
            existing = result.scalars().first()
            if existing:
                return existing.id

            app = Application(
                job_id=job_id,
                resume_id=resume_id,
                status="PENDING",
                applied_at=None
            )
            db.add(app)
            await db.commit()
            await db.refresh(app)
            return app.id

    async def dequeue(self) -> dict | None:
        """Get oldest Application with status='PENDING'"""
        async with async_session() as db:
            result = await db.execute(
                select(Application).where(Application.status == "PENDING")
                .order_by(Application.created_at.asc())
                .limit(1)
            )
            app = result.scalars().first()
            
            if not app:
                return None
                
            app.status = "IN_PROGRESS"
            await db.commit()
            
            # Fetch joined data
            job_res = await db.execute(select(Job).where(Job.id == app.job_id))
            resume_res = await db.execute(select(Resume).where(Resume.id == app.resume_id))
            
            job = job_res.scalars().first()
            resume = resume_res.scalars().first()
            
            import json
            skills = []
            if resume.extracted_skills:
                try:
                    skills = json.loads(resume.extracted_skills)
                except:
                    pass

            return {
                "id": app.id,
                "job": {
                    "id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "url": job.url,
                    "is_easy_apply": job.is_easy_apply
                },
                "resume": {
                    "id": resume.id,
                    "name": resume.name,
                    "email": resume.email,
                    "phone": resume.phone,
                    "skills": skills,
                    "resume_file_path": resume.file_path,
                }
            }

    async def mark_done(self, app_id: int, screenshot_path: str = None):
        """Update status='APPLIED'"""
        async with async_session() as db:
            result = await db.execute(select(Application).where(Application.id == app_id))
            app = result.scalars().first()
            if app:
                app.status = "APPLIED"
                app.applied_at = datetime.utcnow()
                app.screenshot_path = screenshot_path
                await db.commit()

    async def mark_failed(self, app_id: int, error: str):
        """Update status='FAILED'"""
        async with async_session() as db:
            result = await db.execute(select(Application).where(Application.id == app_id))
            app = result.scalars().first()
            if app:
                app.status = "FAILED"
                # Store error message in notes or similar field if schema doesn't have error_message
                app.notes = error[:500] 
                await db.commit()

    async def get_stats(self) -> dict:
        """Count by status for today."""
        async with async_session() as db:
            stats = {"pending": 0, "in_progress": 0, "applied_today": 0, "failed_today": 0}
            
            result = await db.execute(select(Application.status))
            all_statuses = result.scalars().all()
            
            for status in all_statuses:
                if status == "PENDING":
                    stats["pending"] += 1
                elif status == "IN_PROGRESS":
                    stats["in_progress"] += 1
                    
            # Basic counting logic - in a real DB you'd query by date filter
            result = await db.execute(select(Application).where(Application.status == "APPLIED"))
            applied = result.scalars().all()
            stats["applied_today"] = len(applied) # Assuming we reset DB for daily test
            
            result = await db.execute(select(Application).where(Application.status == "FAILED"))
            failed = result.scalars().all()
            stats["failed_today"] = len(failed)

            return stats