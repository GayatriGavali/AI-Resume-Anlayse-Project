from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from db import Base


class User(Base):

    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True
    )

    name = Column(
        String(100),
        nullable=False
    )

    email = Column(
        String(150),
        unique=True,
        nullable=False
    )

    password = Column(
        String(255),
        nullable=False
    )

    reports = relationship(
        "Reports",
        back_populates="user",
        cascade="all, delete-orphan"
    )


class Reports(Base):

    __tablename__ = "reports"

    id = Column(
        Integer,
        primary_key=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    resume_text = Column(
        Text,
        nullable=True
    )

    job_role = Column(
        String(150),
        nullable=True
    )

    result = Column(
        Text,
        nullable=True
    )

    user = relationship(
        "User",
        back_populates="reports"
    )