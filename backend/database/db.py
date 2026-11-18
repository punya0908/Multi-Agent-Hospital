from datetime import datetime, timezone
from sqlalchemy import Boolean, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from backend.config.settings import settings

connect_args = (
    {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


class AppointmentSlotModel(Base):
    __tablename__ = "appointment_slots"

    slot_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    department_id: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    provider_name: Mapped[str] = mapped_column(String(120), nullable=False)
    date: Mapped[str] = mapped_column(String(20), nullable=False)
    start_time: Mapped[str] = mapped_column(String(10), nullable=False)
    end_time: Mapped[str] = mapped_column(String(10), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PatientHistoryModel(Base):
    __tablename__ = "patient_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    consent_given: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    routed_department: Mapped[str] = mapped_column(String(20), nullable=False)
    concern_summary: Mapped[str] = mapped_column(Text, nullable=False)
    routing_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(
        String(40),
        default=lambda: datetime.now(timezone.utc).isoformat(),
        nullable=False,
    )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()