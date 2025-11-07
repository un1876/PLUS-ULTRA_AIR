# ---------------------------------------------------------------------------
# File : app.py
# Desc : CNU-AIR Flask 애플리케이션의 엔트리포인트
#        - BluePrint 로 분리해 둔 각 모듈(auth / reservation / cancel / statistics)
#          을 등록하고, 전역 라우트(홈, 마이페이지 등)를 정의한다.
# ---------------------------------------------------------------------------

from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)

# --- Blueprint 모듈 ---------------------------------------------------------
from .routes.auth        import auth_bp
from .routes.reservation import reservation_bp
from .routes.cancel      import cancel_bp
from .routes.statistics  import statistics_bp

# (선택) 데이터베이스 연결 함수 – 여기서는 불러오기만 (app 레벨에서 사용 X)
# from TP.db import get_connection


# ---------------------------------------------------------------------------
# 1) Flask 애플리케이션 인스턴스 생성
#    - template_folder 에서 HTML 템플릿을 찾는다.
# ---------------------------------------------------------------------------
app = Flask(__name__, template_folder="templates")

# 세션을 사용하기 위해 **반드시** 필요한 시크릿키
# - 개발 단계에서는 하드코딩, 배포 시 환경변수로 치환 권장
app.secret_key = "spidy_u_n"


# ---------------------------------------------------------------------------
# 2) Blueprint 등록
#    - 각 기능 영역을 routes/* 모듈로 분리해 두었고,
#      여기서 한 번에 app 에 등록한다.
# ---------------------------------------------------------------------------
app.register_blueprint(auth_bp)         # 로그인 / 로그아웃
app.register_blueprint(reservation_bp)  # 항공편 조회·예약·결제
app.register_blueprint(statistics_bp)   # 관리자 통계
app.register_blueprint(cancel_bp)       # 예약 취소


# ---------------------------------------------------------------------------
# 3) 전역(범용) 라우트 정의
# ---------------------------------------------------------------------------

# ────────────────────────────────────────────────────────────────────────────
# 홈(메인) – 로그인 전 방문 시 보여주는 일반 홈페이지
# GET /
# ────────────────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def home():
    return render_template("homepage.html")


# 예시용: 로그인 완료 홈으로 바로 보내고 싶을 때 사용하던 라우트(주석 처리)
# @app.route("/", methods=["GET"])
# def login_home():
#     return render_template("login_complete_homepage.html")


# ────────────────────────────────────────────────────────────────────────────
# 마이페이지(회원 정보 수정/삭제) – 단순 템플릿 렌더
# GET /my_page
# ────────────────────────────────────────────────────────────────────────────
@app.route('/my_page')
def my_page():
    return render_template('my_page.html')


# 🛈 ‘이력 조회’ 서브메뉴 – HTML 템플릿만 보여 줌
@app.route('/my_page_2')
def my_page_2():
    return render_template('my_page_2.html')


# 🛈 항공편 검색폼만 바로 보고 싶을 때
@app.route('/search')
def search():
    return render_template('search.html')


# ────────────────────────────────────────────────────────────────────────────
# 대시보드 예시: 로그인 확인 후, 로그인 완료 홈으로 라우팅
# GET /dashboard
# ────────────────────────────────────────────────────────────────────────────
@app.route("/dashboard")
def dashboard():
    # 로그인 안 했으면 로그인 페이지로
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    # 로그인 돼 있으면 개인 환영 페이지로
    return render_template(
        "login_complete_homepage.html",
        user=session["user_id"]
    )


# ────────────────────────────────────────────────────────────────────────────
# 관리자 로그인 폼
# GET /admin_login
# ────────────────────────────────────────────────────────────────────────────
@app.route("/admin_login")
def admin_login():
    return render_template("adminlogin.html")


# 관리자 통계 대시보드(템플릿만)
@app.route("/admin_statistics")
def admin_statistics():
    return render_template("admin_statistics.html")


# ---------------------------------------------------------------------------
# 4) 애플리케이션 실행 (개발용)
#    - host 0.0.0.0 : 외부 접속 허용
#    - debug=True  : 코드 수정 시 자동 재시작
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5006, debug=True)