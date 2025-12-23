from app import db, app
from datetime import datetime, date
import calendar
from enum import Enum as EnumClass
from flask_login import UserMixin
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship


# ===================== ENUM =====================
class UserRole(EnumClass):
    ADMIN = "ADMIN"
    TRAINER = "TRAINER"
    MEMBER = "MEMBER"


class Gender(EnumClass):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


# ===================== USER =====================
class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(100), nullable=False)
    gender = Column(Enum(Gender), nullable=False)
    day_of_birth = Column(Integer, nullable=True)
    phone = Column(String(20), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.MEMBER)
    avatar = Column(String(100), nullable=True, 
                    default="https://res.cloudinary.com/truongduchoang/image/upload/v1757070658/default_user_fy8beq.jpg")

    created_date = Column(DateTime, default=datetime.now())

    memberships = relationship("Membership", backref="member", lazy=True)
    invoices = relationship("Invoice", backref="member", lazy=True)

    def __str__(self):
        return self.full_name


# ===================== MEMBERSHIP PACKAGE =====================
class MembershipPackage(db.Model):
    __tablename__ = "membership_packages"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    duration_months = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    active = Column(Boolean, default=True)

    memberships = relationship("Membership", backref="package", lazy=True)

    def __str__(self):
        return f"{self.name} ({self.duration_months} tháng)"


# ===================== MEMBERSHIP =====================
class Membership(db.Model):
    __tablename__ = "memberships"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    package_id = Column(Integer, ForeignKey("membership_packages.id"), nullable=False)

    start_date = Column(Date, default=date.today)
    end_date = Column(Date, nullable=False)
    active = Column(Boolean, default=True)

    invoices = relationship("Invoice", backref="membership", lazy=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        package = kwargs.get("package")
        if not package and self.package_id:
            package = MembershipPackage.query.get(self.package_id)
        if not self.start_date:
            self.start_date = date.today()
        if package:
            self.end_date = self._add_months(self.start_date, package.duration_months)

    @staticmethod
    def _add_months(start, months):
        month = start.month - 1 + months
        year = start.year + month // 12
        month = month % 12 + 1
        day = min(start.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)


# ===================== TRAINING PLAN =====================
class TrainingPlan(db.Model):
    __tablename__ = "training_plans"

    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    trainer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(Date, default=date.today)

    member = relationship("User", foreign_keys=[member_id], backref="training_plans_as_member")
    trainer = relationship("User", foreign_keys=[trainer_id], backref="training_plans_as_trainer")
    details = relationship("TrainingDetail", backref="plan", lazy=True)


# ===================== EXERCISE =====================
class Exercise(db.Model):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)

    details = relationship("TrainingDetail", backref="exercise", lazy=True)


# ===================== TRAINING DETAIL =====================
class TrainingDetail(db.Model):
    __tablename__ = "training_details"

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("training_plans.id"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)

    sets = Column(Integer, nullable=False)
    reps = Column(Integer, nullable=False)
    days_of_week = Column(String(50), nullable=False)  # Ví dụ: "2,4,6"


# ===================== INVOICE =====================
class Invoice(db.Model):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    membership_id = Column(Integer, ForeignKey("memberships.id"), nullable=False)

    total_amount = Column(Float, nullable=False)
    created_date = Column(DateTime, default=datetime.now())
    paid = Column(Boolean, default=False)

    payments = relationship("PaymentHistory", backref="invoice", lazy=True)


# ===================== PAYMENT HISTORY =====================
class PaymentHistory(db.Model):
    __tablename__ = "payment_histories"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_date = Column(DateTime, default=datetime.now())
    payment_method = Column(String(50), default="CASH")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
