from app.model import (
    User,
    Gender,
    UserRole,
    MembershipPackage,
    Membership,
    Invoice,
    PaymentHistory,
    TrainingPlan,
    TrainingDetail,
    Exercise,
)
from app import app, db
import hashlib
import cloudinary.uploader
from datetime import date
from sqlalchemy import func


def add_user(full_name, gender, phone, email, password, avatar=None):
    password = str(hashlib.md5(password.encode("utf-8")).hexdigest())

    user = User(
        full_name=full_name,
        gender=Gender[gender],
        phone=phone,
        email=email,
        password=password
    )

    if avatar:
        res = cloudinary.uploader.upload(avatar)
        user.avatar = res.get("secure_url")

    db.session.add(user)
    db.session.commit()
    return user

def get_user_by_email(email):
    return User.query.filter_by(email=email).first()

def get_user_by_id(user_id):
    return User.query.get(user_id)

def auth_user(email, password):
    password = str(hashlib.md5(password.encode("utf-8")).hexdigest())

    return User.query.filter(User.email.__eq__(email), 
                             User.password.__eq__(password)).first()


# ===================== MEMBERSHIP PACKAGE =====================
DEFAULT_PACKAGES = [
    {"name": "GÓI 1 THÁNG", "duration_months": 1, "price": 500000},
    {"name": "GÓI 3 THÁNG", "duration_months": 3, "price": 1200000},
    {"name": "GÓI 6 THÁNG", "duration_months": 6, "price": 2000000},
    {"name": "GÓI 12 THÁNG", "duration_months": 12, "price": 3500000},
]


def ensure_default_packages():
    if MembershipPackage.query.count() == 0:
        for data in DEFAULT_PACKAGES:
            db.session.add(MembershipPackage(**data))
        db.session.commit()


def get_membership_packages():
    ensure_default_packages()
    return (
        MembershipPackage.query.filter_by(active=True)
        .order_by(MembershipPackage.duration_months.asc())
        .all()
    )


def get_package_by_id(package_id):
    return MembershipPackage.query.filter_by(id=package_id, active=True).first()


def get_active_membership(user_id):
    return (
        Membership.query.filter(
            Membership.user_id == user_id,
            Membership.active.is_(True),
            Membership.end_date >= date.today(),
        )
        .order_by(Membership.end_date.desc())
        .first()
    )


def create_invoice_for_package(user_id, package_id):
    package = get_package_by_id(package_id)
    if not package:
        return None, "Gói tập không tồn tại hoặc đã bị vô hiệu hóa."

    active_membership = get_active_membership(user_id)
    if active_membership:
        return (
            None,
            f"Bạn đang có gói {active_membership.package.name} hiệu lực đến "
            f"{active_membership.end_date.strftime('%d/%m/%Y')}. Vui lòng gia hạn sau khi hết hạn.",
        )

    membership = Membership(user_id=user_id, package_id=package_id, active=False)
    invoice = Invoice(
        member_id=user_id,
        membership=membership,
        total_amount=package.price,
        paid=False,
    )
    db.session.add(membership)
    db.session.add(invoice)
    db.session.commit()
    return invoice, None


def get_invoice_by_id(invoice_id):
    return Invoice.query.get(invoice_id)


def mark_invoice_paid(invoice_id, amount, method="VNPAY"):
    invoice = get_invoice_by_id(invoice_id)
    if not invoice or invoice.paid:
        return invoice

    invoice.paid = True
    invoice.membership.active = True
    payment = PaymentHistory(
        invoice_id=invoice.id, amount=amount, payment_method=method.upper()
    )
    db.session.add(payment)
    db.session.commit()
    return invoice


def get_payment_history(user_id, limit=None):
    query = (
        PaymentHistory.query.join(Invoice, PaymentHistory.invoice_id == Invoice.id)
        .filter(Invoice.member_id == user_id)
        .order_by(PaymentHistory.payment_date.desc())
    )
    if limit:
        query = query.limit(limit)
    return query.all()


# ===================== TRAINING HELPERS =====================
def get_trainers():
    return User.query.filter_by(role=UserRole.TRAINER).all()


def get_training_plan_for_member(member_id):
    return (
        TrainingPlan.query.filter_by(member_id=member_id)
        .order_by(TrainingPlan.start_date.desc())
        .first()
    )


def get_trainer_by_user(user_id):
    user = get_user_by_id(user_id)
    if user and user.role == UserRole.TRAINER:
        return user
    return None


def get_active_memberships():
    return (
        Membership.query.filter(
            Membership.active.is_(True), Membership.end_date >= date.today()
        )
        .order_by(Membership.end_date.desc())
        .all()
    )


def assign_member_to_trainer(member_id, trainer_id):
    trainer = get_user_by_id(trainer_id)
    if not trainer or trainer.role != UserRole.TRAINER:
        raise ValueError("Trainer không hợp lệ")

    plan = TrainingPlan.query.filter_by(member_id=member_id).first()
    if plan:
        plan.trainer_id = trainer_id
    else:
        plan = TrainingPlan(member_id=member_id, trainer_id=trainer_id)
        db.session.add(plan)
    db.session.commit()
    return plan


def create_training_plan(member_id, trainer_id):
    plan = TrainingPlan.query.filter_by(member_id=member_id).first()
    if plan:
        return plan
    plan = TrainingPlan(member_id=member_id, trainer_id=trainer_id)
    db.session.add(plan)
    db.session.commit()
    return plan


def _get_or_create_exercise(name):
    exercise = Exercise.query.filter(func.lower(Exercise.name) == name.lower()).first()
    if not exercise:
        exercise = Exercise(name=name)
        db.session.add(exercise)
        db.session.commit()
    return exercise


def get_trainer_plans(trainer_id):
    return TrainingPlan.query.filter_by(trainer_id=trainer_id).order_by(TrainingPlan.start_date.desc()).all()


def add_training_detail(member_id, trainer_id, exercise_name, sets, reps, days_of_week):
    plan = TrainingPlan.query.filter_by(member_id=member_id, trainer_id=trainer_id).first()
    if not plan:
        return None, "Hội viên này chưa được gán cho bạn."
    exercise = _get_or_create_exercise(exercise_name)
    detail = TrainingDetail(
        plan_id=plan.id,
        exercise_id=exercise.id,
        sets=sets,
        reps=reps,
        days_of_week=days_of_week,
    )
    db.session.add(detail)
    db.session.commit()
    return detail, None


def get_training_details(plan_id):
    return (
        TrainingDetail.query.filter_by(plan_id=plan_id)
        .join(Exercise)
        .order_by(TrainingDetail.id.asc())
        .all()
    )


# ===================== ADMIN STATS =====================
def count_active_members():
    return (
        db.session.query(func.count(Membership.id))
        .filter(Membership.active.is_(True), Membership.end_date >= date.today())
        .scalar()
        or 0
    )


def get_monthly_membership_stats(year):
    str_year = str(year)
    data = (
        db.session.query(
            func.date_format(Membership.start_date, "%m").label("month"),
            func.count(Membership.id),
        )
        .filter(func.date_format(Membership.start_date, "%Y") == str_year)
        .group_by("month")
        .order_by("month")
        .all()
    )
    return {row[0]: row[1] for row in data}


def get_monthly_revenue_stats(year):
    str_year = str(year)
    data = (
        db.session.query(
            func.date_format(Invoice.created_date, "%m").label("month"),
            func.coalesce(func.sum(Invoice.total_amount), 0),
        )
        .filter(func.date_format(Invoice.created_date, "%Y") == str_year, Invoice.paid.is_(True))
        .group_by("month")
        .order_by("month")
        .all()
    )
    return {row[0]: float(row[1] or 0) for row in data}
