from datetime import datetime

from ..extensions import db


class StudyGroup(db.Model):
    __tablename__ = "study_groups"

    id = db.Column(db.Integer, primary_key=True)
    group_number = db.Column(db.String(32), unique=True, nullable=False)
    course = db.Column(db.Integer, nullable=False, default=1)
    participation_status = db.Column(db.String(3), nullable=False, default="no")
    planned_term = db.Column(db.String(32), nullable=True)
    current_testing = db.Column(db.Boolean, nullable=False, default=False)

    selected_disciplines = db.relationship(
        "GroupDisciplineSelection",
        back_populates="group",
        cascade="all, delete-orphan",
    )
    tests = db.relationship(
        "KnowledgeTest",
        back_populates="group",
        cascade="all, delete-orphan",
    )
    reports = db.relationship(
        "Report",
        back_populates="group",
        cascade="all, delete-orphan",
    )


class Discipline(db.Model):
    __tablename__ = "disciplines"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False)
    department = db.Column(db.String(160), nullable=False, default="ФИТ")

    selected_groups = db.relationship(
        "GroupDisciplineSelection",
        back_populates="discipline",
        cascade="all, delete-orphan",
    )
    tests = db.relationship("KnowledgeTest", back_populates="discipline")
    reports = db.relationship("Report", back_populates="discipline")


class GroupDisciplineSelection(db.Model):
    __tablename__ = "group_discipline_selections"
    __table_args__ = (
        db.UniqueConstraint("group_id", "discipline_id", name="uq_group_discipline"),
    )

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("study_groups.id"), nullable=False)
    discipline_id = db.Column(db.Integer, db.ForeignKey("disciplines.id"), nullable=False)
    selected_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    group = db.relationship("StudyGroup", back_populates="selected_disciplines")
    discipline = db.relationship("Discipline", back_populates="selected_groups")


class KnowledgeTest(db.Model):
    __tablename__ = "knowledge_tests"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("study_groups.id"), nullable=False)
    discipline_id = db.Column(db.Integer, db.ForeignKey("disciplines.id"), nullable=False)
    teacher_name = db.Column(db.String(160), nullable=False)
    profile = db.Column(db.String(160), nullable=False)
    scheduled_date = db.Column(db.Date, nullable=False)
    scheduled_time = db.Column(db.Time, nullable=False)
    agreement_status = db.Column(db.String(64), nullable=False, default="Согласовано")

    group = db.relationship("StudyGroup", back_populates="tests")
    discipline = db.relationship("Discipline", back_populates="tests")


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("study_groups.id"), nullable=False)
    discipline_id = db.Column(db.Integer, db.ForeignKey("disciplines.id"), nullable=False)
    status = db.Column(db.String(64), nullable=False, default="отчёт составлен")
    file_path = db.Column(db.String(500), nullable=True)
    original_filename = db.Column(db.String(255), nullable=True)
    upload_locked = db.Column(db.Boolean, nullable=False, default=False)
    uploaded_at = db.Column(db.DateTime, nullable=True)
    lpr_comment = db.Column(db.Text, nullable=True)

    group = db.relationship("StudyGroup", back_populates="reports")
    discipline = db.relationship("Discipline", back_populates="reports")


class ExpertResponsibility(db.Model):
    __tablename__ = "expert_responsibilities"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(160), nullable=False)
    position = db.Column(db.String(160), nullable=False)
    indicator = db.Column(db.String(220), nullable=False)
    access_open = db.Column(db.Boolean, nullable=False, default=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
