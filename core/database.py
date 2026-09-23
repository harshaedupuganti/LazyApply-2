import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from config import DATABASE_URL

Base = declarative_base()

# Async engine for aiosqlite
engine = create_async_engine(DATABASE_URL, echo=False)

# Async session factory
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

def generate_uuid():
    return str(uuid.uuid4())

def get_utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String, nullable=True)
    url = Column(String, unique=True, nullable=False)
    platform = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="NEW")
    match_score = Column(Integer, default=0)
    is_easy_apply = Column(Boolean, default=False)
    ats_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=get_utcnow)
    applied_at = Column(DateTime, nullable=True)

class Resume(Base):
    __tablename__ = "resumes"

    id = Column(String, primary_key=True, default=generate_uuid)
    filename = Column(String, nullable=False)
    raw_text = Column(Text, nullable=False)
    extracted_name = Column(String, nullable=True)
    extracted_email = Column(String, nullable=True)
    extracted_phone = Column(String, nullable=True)
    extracted_skills = Column(Text, nullable=True)  # Stored as JSON string
    suggested_roles = Column(Text, nullable=True)   # Stored as JSON string
    years_experience = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=get_utcnow)

class Application(Base):
    __tablename__ = "applications"

    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    resume_id = Column(String, ForeignKey("resumes.id"), nullable=False)
    cover_letter = Column(Text, nullable=True)
    form_data = Column(Text, nullable=True)         # Stored as JSON string
    status = Column(String, default="PENDING")
    error_message = Column(Text, nullable=True)
    screenshot_path = Column(String, nullable=True)
    applied_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=get_utcnow)


async def init_db():
    """Create all tables in the database asynchronously."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """Dependency that yields an async database session."""
    async with async_session() as session:
        yield session