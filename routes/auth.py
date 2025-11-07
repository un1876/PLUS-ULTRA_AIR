# routes/auth.py

from flask import Blueprint, request, render_template, redirect, session, flash, url_for
from ..db.db_config import get_connection
from PLUS_ULTRA_AIR.utils.email_sender import send_email_naver  # 이메일 발송 유틸 (옵션)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        # 로그인 페이지 표시
        return render_template("general_login.html")

    # POST 요청 처리: 폼에서 입력된 사용자 ID, 비밀번호 획득
    user_id = request.form.get("cno")
    password = request.form.get("passwd")

    # DB 연결 및 사용자 인증 정보 조회
    conn = get_connection()
    cursor = conn.cursor()

    # SQL 질의: CUSTOMER 테이블에서 입력된 ID 및 비밀번호와 일치하는 레코드 검색
    # -> 인증된 사용자의 cno, 이름, 이메일을 가져옴
    cursor.execute(
        """
        SELECT cno, name, email
          FROM CUSTOMER
         WHERE cno    = :id
           AND passwd = :pw
        """,
        {"id": user_id, "pw": password}
    )
    user = cursor.fetchone()  # 결과 한 건 조회
    conn.close()

    if user:
        # 인증 성공 시 세션에 사용자 정보 저장
        session["user_id"]    = user[0]
        session["user_name"]  = user[1]
        session["user_email"] = user[2]
        # 로그인 완료 페이지로 리다이렉트
        return redirect(url_for("auth.login_complete_homepage"))
    else:
        # 인증 실패 시 메시지 플래시 및 로그인 페이지로 이동
        flash("아이디 또는 비밀번호가 일치하지 않습니다.", "error")
        return redirect(url_for("auth.login"))

@auth_bp.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        # 관리자 로그인 페이지 표시
        return render_template("adminlogin.html")

    # POST 요청 처리: 관리자 ID, 비밀번호 획득
    user_id = request.form.get("cno")
    password = request.form.get("passwd")

    conn = get_connection()
    cursor = conn.cursor()

    # SQL 질의: 일반 로그인과 동일하게 CUSTOMER 테이블에서 관리자 계정 확인
    cursor.execute(
        """
        SELECT cno, name, email
          FROM CUSTOMER
         WHERE cno    = :id
           AND passwd = :pw
        """,
        {"id": user_id, "pw": password}
    )
    user = cursor.fetchone()
    conn.close()

    if user:
        # 인증 성공 시 세션에 관리자 정보 저장
        session["user_id"]    = user[0]
        session["user_name"]  = user[1]
        session["user_email"] = user[2]
        # 관리자 대시보드로 리다이렉트
        return redirect(url_for("auth.admin_login_complete_homepage"))
    else:
        flash("아이디 또는 비밀번호가 일치하지 않습니다.", "error")
        return redirect(url_for("auth.admin_login"))

@auth_bp.route("/logout")
def logout():
    # 로그아웃: 세션 초기화 후 홈 페이지로 이동
    session.clear()
    return redirect(url_for("home"))

@auth_bp.route('/login_complete_homepage')
def login_complete_homepage():
    # 로그인 완료 후 사용자에게 환영 화면 보여주기
    user_id   = session.get('user_id')
    user_name = session.get('user_name')
    if not user_id:
        # 비로그인 상태면 로그인 페이지로 리다이렉트
        return redirect(url_for('auth.login'))

    return render_template(
        'login_complete_homepage.html',
        user_id=user_id,
        user_name=user_name
    )

@auth_bp.route('/admin_login_complete_homepage')
def admin_login_complete_homepage():
    # 관리자 로그인 완료 후 대시보드 화면 표시
    user_id   = session.get('user_id')
    user_name = session.get('user_name')
    if not user_id:
        return redirect(url_for('auth.admin_login'))

    return render_template(
        'admin_homepage.html',
        user_id=user_id,
        user_name=user_name
    )