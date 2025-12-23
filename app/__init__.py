from flask import Flask
from urllib.parse import quote
from flask_sqlalchemy import SQLAlchemy
import cloudinary
from flask_login import LoginManager
import os

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root:%s@localhost/ougymdb?charset=utf8mb4" % quote('Admin@123')
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True

app.secret_key = "asjdahjsdaskdjahsdjlsdfjdsd"

# ============== VNPAY CONFIG ==============
app.config["VNPAY_TMN_CODE"] = "KMGAKEW9"
app.config["VNPAY_HASH_SECRET"] = "KMJYDQ929Y6E0EV5QFCCKAI35T7NI2NK"
app.config["VNPAY_URL"] = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
app.config["VNPAY_RETURN_URL"] = "http://localhost:5000/payment/vnpay-return"

# ============== SMTP CONFIG ==============
app.config["EMAIL_HOST"] = "smtp.gmail.com"
app.config["EMAIL_PORT"] = 587
app.config["EMAIL_USERNAME"] = "tantiennguyen2404@gmail.com"
app.config["EMAIL_PASSWORD"] = "lcdd pdcq wolx rjvq"
app.config["EMAIL_USE_TLS"] = True
app.config["EMAIL_FROM"] = "OU GYM"

cloudinary.config(cloud_name='truongduchoang',
                  api_key='248579782829654',
                  api_secret='sxkpzv4-ePJKtM6PFD6ZUi6FHxE')

login = LoginManager(app=app)
login.login_view = "login_process"

db = SQLAlchemy(app=app)
