import os
import sqlite3
from functools import wraps

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "app.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = "please-change-this-secret-key"


class LoginForm(FlaskForm):
    username = StringField("帳號", validators=[DataRequired("帳號必填")])
    password = PasswordField("密碼", validators=[DataRequired("密碼必填")])
    submit = SubmitField("登入")


class CustomerForm(FlaskForm):
    cid = StringField(
        "客戶編號",
        validators=[
            DataRequired("客戶編號必填"),
            Length(3, 10, message="客戶編號長度需為 3~10 字元"),
        ],
    )
    cname = StringField("客戶姓名", validators=[DataRequired("姓名必填")])
    email = StringField(
        "電子郵件",
        validators=[
            DataRequired("Email 必填"),
            Email("請輸入有效的 Email 格式"),
        ],
    )
    phone = StringField(
        "聯絡電話",
        validators=[
            DataRequired("電話必填"),
            Length(10, 10, message="電話必須為 10 碼"),
        ],
    )
    address = StringField("地址")
    submit = SubmitField("儲存")


class DeleteForm(FlaskForm):
    submit = SubmitField("刪除")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customer (
                cid TEXT PRIMARY KEY,
                cname TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT NOT NULL,
                address TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            flash("請先登入")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapper


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "username" in session:
        return redirect(url_for("customer_list"))

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        if username == "admin" and password == "admin123":
            session["username"] = username
            flash("登入成功")
            return redirect(url_for("customer_list"))

        flash("帳號或密碼錯誤")

    return render_template("login.html", form=form)


@app.route("/logout")
def logout():
    session.clear()
    flash("已登出")
    return redirect(url_for("login"))


@app.route("/customers")
@login_required
def customer_list():
    conn = get_db_connection()
    try:
        customers = conn.execute(
            "SELECT cid, cname, email, phone, address FROM customer ORDER BY cid"
        ).fetchall()
    finally:
        conn.close()

    delete_form = DeleteForm()
    return render_template(
        "customers.html",
        customers=customers,
        delete_form=delete_form,
    )


@app.route("/customer/add", methods=["GET", "POST"])
@login_required
def customer_add():
    form = CustomerForm()

    if form.validate_on_submit():
        conn = get_db_connection()
        try:
            conn.execute(
                """
                INSERT INTO customer (cid, cname, email, phone, address)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    form.cid.data,
                    form.cname.data,
                    form.email.data,
                    form.phone.data,
                    form.address.data,
                ),
            )
            conn.commit()
            flash("新增成功")
            return redirect(url_for("customer_list"))
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("客戶編號或 Email 已存在")
        finally:
            conn.close()

    return render_template(
        "customer_form.html",
        form=form,
        title="新增客戶",
        is_edit=False,
    )


@app.route("/customer/<cid>/edit", methods=["GET", "POST"])
@login_required
def customer_edit(cid):
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT cid, cname, email, phone, address FROM customer WHERE cid = ?",
            (cid,),
        ).fetchone()

        if row is None:
            return render_template("error.html", message="找不到指定的客戶"), 404

        form = CustomerForm()

        if request.method == "GET":
            form.cid.data = row["cid"]
            form.cname.data = row["cname"]
            form.email.data = row["email"]
            form.phone.data = row["phone"]
            form.address.data = row["address"]

        if form.validate_on_submit():
            try:
                conn.execute(
                    """
                    UPDATE customer
                    SET cname = ?, email = ?, phone = ?, address = ?
                    WHERE cid = ?
                    """,
                    (
                        form.cname.data,
                        form.email.data,
                        form.phone.data,
                        form.address.data,
                        cid,
                    ),
                )
                conn.commit()
                flash("更新成功")
                return redirect(url_for("customer_list"))
            except sqlite3.IntegrityError:
                conn.rollback()
                flash("Email 已被其他客戶使用")

    finally:
        conn.close()

    return render_template(
        "customer_form.html",
        form=form,
        title="編輯客戶",
        is_edit=True,
    )


@app.route("/customer/<cid>/delete", methods=["POST"])
@login_required
def customer_delete(cid):
    form = DeleteForm()
    if not form.validate_on_submit():
        flash("刪除失敗：CSRF 驗證未通過")
        return redirect(url_for("customer_list"))

    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM customer WHERE cid = ?", (cid,))
        conn.commit()
        flash("刪除成功")
    finally:
        conn.close()

    return redirect(url_for("customer_list"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
