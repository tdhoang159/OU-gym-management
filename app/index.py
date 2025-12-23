from datetime import datetime, date
import smtplib
from email.mime.text import MIMEText
from functools import wraps
from flask import (
    render_template,
    request,
    redirect,
    flash,
    url_for,
    jsonify,
    abort,
)
from app import app, db, dao, login
from flask_login import login_user, current_user, logout_user, login_required
from app.vnpay import Vnpay
from app.model import UserRole


@app.template_filter("currency_vnd")
def currency_vnd(value):
    if value is None:
        return "0đ"
    try:
        return f"{float(value):,.0f}".replace(",", ".") + "đ"
    except Exception:
        return f"{value}đ"


def get_client_ip(req):
    forwarded = req.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return req.remote_addr or "127.0.0.1"


def send_payment_success_email(invoice):
    cfg = app.config
    required = [
        cfg.get("EMAIL_HOST"),
        cfg.get("EMAIL_USERNAME"),
        cfg.get("EMAIL_PASSWORD"),
        cfg.get("EMAIL_FROM"),
    ]
    if not all(required):
        return

    member = invoice.member
    if not member or not member.email:
        return

    package = invoice.membership.package
    amount = currency_vnd(invoice.total_amount)
    end_date = invoice.membership.end_date.strftime("%d/%m/%Y")

    subject = "Xác nhận thanh toán gói tập OU Gym"
    body = f"""
Xin chào {member.full_name},

Bạn đã thanh toán thành công gói {package.name}.

Thông tin giao dịch:
- Số tiền: {amount}
- Ngày kích hoạt: {invoice.membership.start_date.strftime('%d/%m/%Y')}
- Hết hạn: {end_date}
- Mã hóa đơn: #{invoice.id}

Chúc bạn có trải nghiệm luyện tập hiệu quả cùng OU Gym!
"""
    message = MIMEText(body.strip(), "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = cfg["EMAIL_FROM"]
    message["To"] = member.email

    try:
        server = smtplib.SMTP(cfg["EMAIL_HOST"], cfg.get("EMAIL_PORT", 587))
        if cfg.get("EMAIL_USE_TLS", True):
            server.starttls()
        server.login(cfg["EMAIL_USERNAME"], cfg["EMAIL_PASSWORD"])
        server.sendmail(cfg["EMAIL_FROM"], [member.email], message.as_string())
    except Exception as exc:
        app.logger.error(f"Send mail failed: {exc}")
    finally:
        try:
            server.quit()
        except Exception:
            pass


def trainer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role != UserRole.TRAINER:
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role != UserRole.ADMIN:
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


@app.route("/")
def index():
    return render_template("homepage/index.html")


@app.route("/login", methods=["GET", "POST"])
def login_process():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = dao.auth_user(email=email, password=password)

        if user:
            login_user(user)
            if user.role == UserRole.ADMIN:
                return redirect(url_for("admin_dashboard"))
            if user.role == UserRole.TRAINER:
                return redirect(url_for("trainer_dashboard"))
            return redirect(url_for("dashboard_member"))
        flash("Thông tin đăng nhập không hợp lệ!", "error")
    return render_template("auth/login.html")




@login.user_loader
def get_user(user_id):
    return dao.get_user_by_id(user_id=user_id)







@app.route("/trainer", methods=["GET", "POST"])
@login_required
@trainer_required
def trainer_dashboard():
    trainer = dao.get_trainer_by_user(current_user.id)
    if not trainer:
        abort(403)

    if request.method == "POST":
        member_id = int(request.form.get("member_id"))
        dao.assign_member_to_trainer(member_id, trainer.id)
        flash("Đã gán hội viên cho bạn.", "success")
        return redirect(url_for("trainer_dashboard"))

    active_memberships = dao.get_active_memberships()
    trainer_plans = dao.get_trainer_plans(trainer.id)

    return render_template(
        "trainer/dashboard.html",
        trainer=trainer,
        active_memberships=active_memberships,
        trainer_plans=trainer_plans,
    )


@app.route("/trainer/create-plan", methods=["GET", "POST"])
@login_required
@trainer_required
def trainer_create_plan():
    trainer = dao.get_trainer_by_user(current_user.id)
    if not trainer:
        abort(403)

    trainer_plans = dao.get_trainer_plans(trainer.id)
    selected_plan = None
    selected_details = []
    selected_member = None

    if request.method == "POST":
        member_id = int(request.form.get("member_id"))
        exercise = request.form.get("exercise")
        sets = int(request.form.get("sets"))
        reps = int(request.form.get("reps"))
        days = request.form.get("days")

        _, error = dao.add_training_detail(
            member_id=member_id,
            trainer_id=trainer.id,
            exercise_name=exercise,
            sets=sets,
            reps=reps,
            days_of_week=days,
        )
        if error:
            flash(error, "error")
        else:
            flash("Đã thêm bài tập vào kế hoạch.", "success")
        return redirect(url_for("trainer_create_plan", member_id=member_id))

    selected_member_id = request.args.get("member_id", type=int)
    if selected_member_id:
        selected_plan = dao.get_training_plan_for_member(selected_member_id)
        if selected_plan and selected_plan.trainer_id == trainer.id:
            selected_member = selected_plan.member
            selected_details = dao.get_training_details(selected_plan.id)
        else:
            selected_plan = None

    return render_template(
        "trainer/create_plan.html",
        trainer=trainer,
        members=trainer_plans,
        selected_plan=selected_plan,
        selected_member=selected_member,
        selected_details=selected_details,
    )


@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    current_year = datetime.now().year
    year = request.args.get("year", type=int) or current_year

    membership_data = dao.get_monthly_membership_stats(year)
    revenue_data = dao.get_monthly_revenue_stats(year)

    month_keys = [f"{m:02d}" for m in range(1, 13)]
    chart_labels = [f"Tháng {m}" for m in range(1, 13)]
    membership_chart = [membership_data.get(key, 0) for key in month_keys]
    revenue_chart = [revenue_data.get(key, 0) for key in month_keys]

    total_memberships = sum(membership_chart)
    total_revenue = sum(revenue_chart)
    active_members = dao.count_active_members()

    year_options = list(range(current_year - 4, current_year + 1))
    if year not in year_options:
        year_options.append(year)
        year_options.sort()

    return render_template(
        "admin/overview.html",
        year=year,
        year_options=year_options,
        chart_labels=chart_labels,
        membership_chart=membership_chart,
        revenue_chart=revenue_chart,
        total_memberships=total_memberships,
        total_revenue=total_revenue,
        active_members=active_members,
    )


@app.route("/admin/members/new", methods=["GET", "POST"])
@login_required
@admin_required
def admin_register_member():
    packages = dao.get_membership_packages()
    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        gender = request.form.get("gender")
        password = request.form.get("password")
        package_id = request.form.get("package_id", type=int)
        start_date_raw = request.form.get("start_date")

        if not all([full_name, email, phone, gender, password, package_id]):
            flash("Vui lòng nhập đầy đủ thông tin.", "error")
            return redirect(url_for("admin_register_member"))

        if dao.get_user_by_email(email):
            flash("Email đã tồn tại trong hệ thống.", "error")
            return redirect(url_for("admin_register_member"))

        try:
            user = dao.add_user(
                full_name=full_name,
                gender=gender,
                phone=phone,
                email=email,
                password=password,
            )
            invoice, error = dao.create_invoice_for_package(user.id, package_id)
            if error:
                flash(error, "error")
                return redirect(url_for("admin_register_member"))

            start_date_value = date.today()
            if start_date_raw:
                try:
                    start_date_value = datetime.strptime(start_date_raw, "%Y-%m-%d").date()
                except ValueError:
                    flash("Ngày bắt đầu không hợp lệ, hệ thống dùng ngày hôm nay.", "warning")

            membership = invoice.membership
            membership.start_date = start_date_value
            membership.end_date = membership._add_months(
                membership.start_date, membership.package.duration_months
            )

            dao.mark_invoice_paid(invoice.id, invoice.total_amount, method="OFFLINE")
            flash("Đã tạo hội viên và kích hoạt gói tập.", "success")
            return redirect(url_for("admin_register_member"))
        except Exception as exc:
            db.session.rollback()
            app.logger.error(f"Admin create member error: {exc}")
            flash("Không thể tạo hội viên, vui lòng thử lại.", "error")

    default_start = date.today().strftime("%Y-%m-%d")
    return render_template("admin/register_member.html", packages=packages, default_start=default_start)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/dashboard-member")
@login_required
def dashboard_member():
    packages = dao.get_membership_packages()
    membership = dao.get_active_membership(current_user.id)
    payments = dao.get_payment_history(current_user.id, limit=5)
    plan = dao.get_training_plan_for_member(current_user.id)
    plan_details = dao.get_training_details(plan.id) if plan else []
    return render_template(
        "member/dashboard.html",
        packages=packages,
        membership=membership,
        recent_payments=payments,
        training_plan=plan,
        training_details=plan_details,
    )




@login.user_loader
def get_user(user_id):
    return dao.get_user_by_id(user_id=user_id)


@app.route("/register", methods=["GET", "POST"])
def register_process():
    error_message = None
    if request.method == "POST":
        full_name = request.form.get("fullname")
        email = request.form.get("email")
        phone = request.form.get("phone")
        gender = request.form.get("gender")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        avatar = request.files.get("avatar")

        if password != confirm_password:
            flash("Mật khẩu xác nhận không khớp!", "error")
            return redirect("/register")

        if dao.get_user_by_email(email):
            flash("Email đã được đăng ký bởi tài khoản khác!", "error")
            return redirect("/register")

        try:
            dao.add_user(
                full_name=full_name,
                gender=gender,
                phone=phone,
                email=email,
                password=password,
                avatar=avatar,
            )
            flash("Tạo tài khoản thành công. Vui lòng đăng nhập!", "success")
            return redirect("/login")

        except Exception as ex:
            db.session.rollback()
            error_message = "Hệ thống có lỗi xảy ra, vui lòng thử lại!"
            print(ex)

    return render_template("auth/register.html", errorMessage=error_message)


@app.route("/packages/<int:package_id>/checkout", methods=["POST"])
@login_required
def checkout_package(package_id):
    invoice, error = dao.create_invoice_for_package(current_user.id, package_id)
    if error:
        flash(error, "error")
        return redirect(url_for("dashboard_member"))

    config = app.config
    vnp = Vnpay()
    vnp.add_param("vnp_Version", "2.1.0")
    vnp.add_param("vnp_Command", "pay")
    vnp.add_param("vnp_TmnCode", config["VNPAY_TMN_CODE"])
    vnp.add_param("vnp_Amount", int(invoice.total_amount) * 100)
    vnp.add_param("vnp_CurrCode", "VND")
    vnp.add_param("vnp_TxnRef", str(invoice.id))
    vnp.add_param(
        "vnp_OrderInfo", f"Thanh toán gói {invoice.membership.package.name}"
    )
    vnp.add_param("vnp_OrderType", "billpayment")
    vnp.add_param("vnp_Locale", "vn")
    vnp.add_param("vnp_ReturnUrl", config["VNPAY_RETURN_URL"])
    vnp.add_param("vnp_IpAddr", get_client_ip(request))
    vnp.add_param("vnp_CreateDate", datetime.now().strftime("%Y%m%d%H%M%S"))

    try:
        payment_url = vnp.get_payment_url(
            config["VNPAY_URL"], config["VNPAY_HASH_SECRET"]
        )
    except Exception as exc:
        flash(str(exc), "error")
        return redirect(url_for("dashboard_member"))

    return redirect(payment_url)


@app.route("/payment/vnpay-return")
@login_required
def vnpay_return():
    params = request.args.to_dict()
    if not params:
        flash("Không nhận được tham số phản hồi.", "error")
        return redirect(url_for("dashboard_member"))

    txn_ref = params.get("vnp_TxnRef")
    invoice = dao.get_invoice_by_id(txn_ref)
    if not invoice:
        flash("Không tìm thấy hóa đơn.", "error")
        return redirect(url_for("dashboard_member"))

    vnp = Vnpay()
    vnp.response_data = params
    is_valid = vnp.validate_response(app.config["VNPAY_HASH_SECRET"])

    if is_valid and params.get("vnp_ResponseCode") == "00":
        invoice = dao.mark_invoice_paid(invoice.id, invoice.total_amount, method="VNPAY")
        if invoice:
            send_payment_success_email(invoice)
        flash("Thanh toán thành công. Chúc bạn luyện tập hiệu quả!", "success")
    else:
        flash("Thanh toán thất bại hoặc bị hủy.", "error")

    return redirect(url_for("dashboard_member"))


@app.route("/payment/vnpay-ipn")
def vnpay_ipn():
    params = request.args.to_dict()
    if not params:
        return jsonify({"RspCode": "99", "Message": "Invalid request"})

    vnp = Vnpay()
    vnp.response_data = params
    if not vnp.validate_response(app.config["VNPAY_HASH_SECRET"]):
        return jsonify({"RspCode": "97", "Message": "Invalid signature"})

    txn_ref = params.get("vnp_TxnRef")
    invoice = dao.get_invoice_by_id(txn_ref)
    if not invoice:
        return jsonify({"RspCode": "01", "Message": "Order not found"})

    amount = int(params.get("vnp_Amount", 0))
    if int(invoice.total_amount * 100) != amount:
        return jsonify({"RspCode": "04", "Message": "Invalid amount"})

    if invoice.paid:
        return jsonify({"RspCode": "02", "Message": "Order already confirmed"})

    if params.get("vnp_ResponseCode") == "00":
        invoice = dao.mark_invoice_paid(invoice.id, invoice.total_amount, method="VNPAY")
        if invoice:
            send_payment_success_email(invoice)
        return jsonify({"RspCode": "00", "Message": "Confirm Success"})

    return jsonify({"RspCode": "01", "Message": "Payment failed"})


@app.route("/transactions")
@login_required
def transaction_history():
    payments = dao.get_payment_history(current_user.id)
    return render_template("member/transactions.html", payments=payments)


@app.route("/member/assign-trainer", methods=["GET", "POST"])
@login_required
def assign_trainer():
    if current_user.role != UserRole.MEMBER:
        abort(403)

    trainers = dao.get_trainers()
    current_plan = dao.get_training_plan_for_member(current_user.id)
    current_trainer = current_plan.trainer if current_plan else None

    if request.method == "POST":
        trainer_id = int(request.form.get("trainer_id"))
        try:
            dao.assign_member_to_trainer(current_user.id, trainer_id)
            flash("Đã gán huấn luyện viên cá nhân.", "success")
            return redirect(url_for("dashboard_member"))
        except ValueError as exc:
            flash(str(exc), "error")

    return render_template(
        "member/assign_trainer.html",
        trainers=trainers,
        current_trainer=current_trainer,
    )


if __name__ == "__main__":
    with app.app_context():
        app.run(debug=True, port=5000)
