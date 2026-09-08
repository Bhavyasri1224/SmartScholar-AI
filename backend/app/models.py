from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base


# ============================================================
# USER
# ============================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# STUDENT PROFILE
# ============================================================

class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True
    )

    full_name = Column(String, nullable=False)
    date_of_birth = Column(String)
    phone = Column(String)
    gender = Column(String)
    category = Column(String)
    state = Column(String)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# OFFICER PROFILE
# ============================================================

class OfficerProfile(Base):
    __tablename__ = "officer_profiles"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True
    )

    full_name = Column(String, nullable=False)
    designation = Column(String)
    institute_name = Column(String)
    state = Column(String)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# APPLICATION
# ============================================================

class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)

    student_profile_id = Column(
        Integer,
        ForeignKey("student_profiles.id"),
        nullable=False,
        index=True
    )

    # Link application to scholarship scheme
    scheme_id = Column(
        Integer,
        ForeignKey("schemes.id"),
        nullable=True,
        index=True
    )

    # Link application to institute
    institute_id = Column(
        Integer,
        ForeignKey("institutes.id"),
        nullable=True,
        index=True
    )

    application_number = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    scheme_name = Column(String)
    college_name = Column(String)

    board = Column(String)
    class_12_year = Column(Integer)
    stream = Column(String)
    marks_percentage = Column(String)

    course_name = Column(String)
    course_type = Column(String)
    admission_year = Column(Integer)

    annual_family_income = Column(String)

    other_scholarship = Column(String)

    regular_course = Column(String)
    is_diploma = Column(String)
    drop_after_class_12 = Column(String)

    status = Column(
        String,
        nullable=False,
        default="DRAFT",
        index=True
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# DOCUMENT
# ============================================================

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    application_id = Column(
        Integer,
        ForeignKey("applications.id"),
        nullable=False,
        index=True
    )

    document_type = Column(String, nullable=False)

    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)

    mime_type = Column(String)
    file_size = Column(Integer)
    page_count = Column(Integer)

    ocr_status = Column(
        String,
        default="PENDING"
    )

    classification_status = Column(
        String,
        default="PENDING"
    )

    uploaded_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )


# ============================================================
# EXTRACTED FIELD
# ============================================================

class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id = Column(Integer, primary_key=True, index=True)

    document_id = Column(
        Integer,
        ForeignKey("documents.id"),
        nullable=False,
        index=True
    )

    field_name = Column(String, nullable=False)
    field_value = Column(Text)

    confidence = Column(String)
    page_number = Column(Integer)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )


# ============================================================
# AI FINDING
# ============================================================

class AIFinding(Base):
    __tablename__ = "ai_findings"

    id = Column(Integer, primary_key=True, index=True)

    application_id = Column(
        Integer,
        ForeignKey("applications.id"),
        nullable=False,
        index=True
    )

    finding_type = Column(String)
    severity = Column(String)

    title = Column(String)
    description = Column(Text)

    # Evidence reference
    source_document_id = Column(
        Integer,
        ForeignKey("documents.id"),
        nullable=True
    )

    source_page = Column(Integer)

    expected_value = Column(Text)
    observed_value = Column(Text)

    confidence = Column(String)

    status = Column(
        String,
        default="OPEN"
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )


# ============================================================
# AI SUMMARY
# ============================================================

class AISummary(Base):
    __tablename__ = "ai_summaries"

    id = Column(Integer, primary_key=True, index=True)

    application_id = Column(
        Integer,
        ForeignKey("applications.id"),
        nullable=False,
        index=True
    )

    summary_text = Column(Text)

    eligibility_result = Column(String)
    risk_level = Column(String)

    key_issues = Column(Text)
    evidence_summary = Column(Text)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )


# ============================================================
# VERIFICATION ACTION
# ============================================================

class VerificationAction(Base):
    __tablename__ = "verification_actions"

    id = Column(Integer, primary_key=True, index=True)

    application_id = Column(
        Integer,
        ForeignKey("applications.id"),
        nullable=False,
        index=True
    )

    officer_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    level = Column(String)
    action = Column(String)
    remarks = Column(Text)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )


# ============================================================
# NOTIFICATION
# ============================================================

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    application_id = Column(
        Integer,
        ForeignKey("applications.id"),
        nullable=True,
        index=True
    )

    notification_type = Column(String)
    title = Column(String)
    message = Column(Text)

    is_read = Column(
        String(10),
        default="false"
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )


# ============================================================
# SCHEME
# ============================================================

class Scheme(Base):
    __tablename__ = "schemes"

    id = Column(Integer, primary_key=True, index=True)

    scheme_name = Column(
        String,
        nullable=False
    )

    scheme_code = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    description = Column(Text)

    eligibility_rules = Column(Text)

    is_active = Column(
        String(10),
        default="true"
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )


# ============================================================
# INSTITUTE
# ============================================================

class Institute(Base):
    __tablename__ = "institutes"

    id = Column(Integer, primary_key=True, index=True)

    institute_name = Column(
        String,
        nullable=False
    )

    institute_code = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    district = Column(String)
    state = Column(String)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )


# ============================================================
# AUDIT LOG
# ============================================================

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True
    )

    action = Column(String)
    entity_type = Column(String)
    entity_id = Column(Integer)

    details = Column(Text)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

