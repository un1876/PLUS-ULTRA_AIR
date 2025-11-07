# ---------------------------------------------------------------
# File : routes/reservation.py
# Desc : “예약/조회/결제/통합 이력” 관련 BluePrint
#        ✱ **주의**: 원본 로직은 그대로 두고 “가독성 주석”만 추가했습니다.
# ---------------------------------------------------------------

from flask import (
    Blueprint, request, render_template,
    redirect, url_for, flash, session
)
from PLUS_ULTRA_AIR.db.db_config import get_connection          # Oracle 연결
from oracledb          import IntegrityError
from PLUS_ULTRA_AIR.utils.email_sender import send_email_naver   # NAVER SMTP 유틸
from datetime          import datetime

# ---------------------------------------------------------------
# Blueprint 객체 생성
# ---------------------------------------------------------------
reservation_bp = Blueprint('reservation', __name__)


# ===============================================================
# 1. 항공편 검색 폼 (단순 HTML 반환)
# ---------------------------------------------------------------
@reservation_bp.route('/flights', methods=['GET'])
def flights_form():
    return render_template('search.html')


# ===============================================================
# 2. 항공편 검색 실행
#    - 쿼리스트링 파라미터를 읽어 DB 조회 후 결과 페이지로
# ===============================================================
@reservation_bp.route('/search', methods=['GET'])
def search():
    # ────────────────────────────────────────────────────────────
    # 2-1) GET 파라미터 추출
    # ────────────────────────────────────────────────────────────
    dep        = request.args.get('departure')     # 출발 공항
    arr        = request.args.get('arrival')       # 도착 공항
    date_start = request.args.get('date_start')    # 출발 날짜
    date_end   = request.args.get('date_end')      # (선택) 도착 날짜
    cls        = request.args.get('seat_class')    # 좌석 등급
    sort_by    = request.args.get('sort_by', 'price_asc')  # 정렬

    # 필수값 체크
    if not all([dep, arr, date_start, cls]):
        flash("출발·도착 공항, 출발 날짜, 좌석 등급은 필수입니다.", "error")
        return redirect(url_for('reservation.flights_form'))

    # ────────────────────────────────────────────────────────────
    # 2-2) ORDER BY 절 결정
    # ────────────────────────────────────────────────────────────
    if   sort_by == 'price_desc': order_clause = 's.price DESC'
    elif sort_by == 'dep_asc':    order_clause = 'a.departureDateTime ASC'
    elif sort_by == 'dep_desc':   order_clause = 'a.departureDateTime DESC'
    elif sort_by == 'arr_asc':    order_clause = 'a.arrivalDateTime ASC'
    elif sort_by == 'arr_desc':   order_clause = 'a.arrivalDateTime DESC'
    else:                         order_clause = 's.price ASC'

    # ────────────────────────────────────────────────────────────
    # 2-3) WHERE 절 / 바인드 변수 구성
    # ────────────────────────────────────────────────────────────
    where_clauses = [
        "a.departureAirport = :dep",
        "a.arrivalAirport   = :arr",
        "s.seatClass        = :cls",
        # 날짜 비교는 TRUNC 로 시간 제거
        "TRUNC(a.departureDateTime) = TO_DATE(:date_start,'YYYY-MM-DD')"
    ]
    binds = {
        'dep': dep, 'arr': arr, 'cls': cls, 'date_start': date_start
    }

    # 도착 날짜가 있으면 추가 필터
    if date_end:
        where_clauses.append(
            "TRUNC(a.arrivalDateTime) = TO_DATE(:date_end,'YYYY-MM-DD')"
        )
        binds['date_end'] = date_end

    # ────────────────────────────────────────────────────────────
    # 2-4) 항공편 + 좌석 JOIN / 잔여좌석 함수 호출
    #      ‣ GET_REMAINING_SEATS : 남은 좌석을 계산하는 DB 함수
    # ────────────────────────────────────────────────────────────
    sql = f"""
        SELECT
          a.airline,
          a.flightNo,
          TO_CHAR(a.departureDateTime,'YYYY-MM-DD HH24:MI') AS depDT,
          TO_CHAR(a.arrivalDateTime,  'YYYY-MM-DD HH24:MI') AS arrDT,
          a.departureAirport,
          a.arrivalAirport,
          s.seatClass,
          s.price,
          s.no_of_seats AS total_seats,
          GET_REMAINING_SEATS(
              a.flightNo,
              a.departureDateTime,
              s.seatClass
          ) AS remaining_seats
        FROM AIRPLAIN a
        JOIN SEATS s
          ON a.flightNo          = s.flightNo
         AND a.departureDateTime = s.departureDateTime
        WHERE { ' AND '.join(where_clauses) }
        ORDER BY { order_clause }
    """

    # ────────────────────────────────────────────────────────────
    # 2-5) DB 조회 → 파이썬 dict 리스트로 변환
    # ────────────────────────────────────────────────────────────
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(sql, binds)
    rows = cur.fetchall()
    conn.close()

    results = []
    for (
        airline, flightNo, depDT, arrDT,
        depAP, arrAP, seatClass,
        price, total_seats, remaining_seats
    ) in rows:
        results.append({
            "airline":          airline,
            "flightNo":         flightNo,
            "depDT":            depDT,
            "arrDT":            arrDT,
            "departureAirport": depAP,
            "arrivalAirport":   arrAP,
            "seatClass":        seatClass,
            "price":            price,
            "total_seats":      total_seats,
            "remaining_seats":  remaining_seats,
        })

    # 결과 렌더링
    return render_template(
        'searchresult.html',
        results=results,
        departure=dep, arrival=arr,
        date_start=date_start, date_end=date_end,
        seat_class=cls, sort_by=sort_by
    )


# ===============================================================
# 3. 예약하기 화면 (GET)
#    - 좌석 잔여 여부 체크 후 결제 페이지 렌더
# ===============================================================
@reservation_bp.route('/book', methods=['GET'])
def book():
    flightNo  = request.args.get('flightNo')
    depDT     = request.args.get('depDT')
    seatClass = request.args.get('seatClass')

    if not all([flightNo, depDT, seatClass]):
        flash("잘못된 요청입니다.", "error")
        return redirect(url_for('reservation.flights_form'))

    # ―― 선택한 편/좌석 정보 조회 (가격, 잔여석 등) ――――――――――――――――――
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        /* 선택 편명/좌석 정보를 조회하여
           - 남은 좌석
           - 가격
           - 항공사/출도착 일시·공항
           을 브라우저에 표시 */
        SELECT
          s.no_of_seats,
          s.price,
          a.airline,
          TO_CHAR(a.departureDateTime,'YYYY-MM-DD HH24:MI') AS depChar,
          TO_CHAR(a.arrivalDateTime,  'YYYY-MM-DD HH24:MI') AS arrChar,
          a.departureAirport,
          a.arrivalAirport
        FROM SEATS s
        JOIN AIRPLAIN a
          ON s.flightNo          = a.flightNo
         AND s.departureDateTime = a.departureDateTime
        WHERE s.flightNo = :fn
          AND TO_CHAR(s.departureDateTime,'YYYY-MM-DD HH24:MI') = :dt
          AND s.seatClass = :sc
    """, { 'fn': flightNo, 'dt': depDT, 'sc': seatClass })
    row = cur.fetchone()
    conn.close()

    # 조회 결과 및 잔여석 체크
    if not row or row[0] < 1:
        flash("남은 좌석이 없습니다.", "error")

    remaining, price, airline, depChar, arrChar, depAP, arrAP = row

    # ―― 로그인 유저 이름 가져오기 (없으면 ‘손님’) ――――――――――――――――――――
    user_id   = session.get('user_id')
    user_name = "손님"
    if user_id:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            "SELECT name FROM CUSTOMER WHERE cno = :cno",
            { 'cno': user_id }
        )
        u = cur.fetchone()
        conn.close()
        if u:
            user_name = u[0]

    # 결제 페이지 렌더
    return render_template(
        'pay.html',
        flightNo=flightNo,
        depDT=depChar, arrDT=arrChar,
        depAP=depAP,  arrAP=arrAP,
        airline=airline,
        seatClass=seatClass,
        remaining=remaining,
        price=price,
        user_name=user_name
    )


# ===============================================================
# 4. 결제 처리 (POST)
#    - RESERVE insert / SEATS 좌석수 차감
# ===============================================================
@reservation_bp.route('/pay', methods=['POST'])
def pay():
    # --- [A] 로그인 여부 확인 ------------------------------------
    cno = session.get('user_id')
    if not cno:
        flash("로그인이 필요합니다.", "error")
        return redirect(url_for('auth.login'))

    # --- [B] 폼 데이터 읽기 --------------------------------------
    flightNo   = request.form['flightNo']
    depDT      = request.form['departureDateTime']      # 문자열 형태
    seatClass  = request.form['seatClass']
    paymentAmt = int(request.form['paymentAmount'])

    # --- [C] 좌석 잔여 & 기본 정보 재검증 ------------------------
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            /* 남은 좌석, 출발/도착 공항·도착시간 등 확인 */
            SELECT
              s.no_of_seats,
              a.departureAirport,
              a.arrivalAirport,
              a.arrivalDateTime
            FROM SEATS s
            JOIN AIRPLAIN a
              ON s.flightNo          = a.flightNo
             AND s.departureDateTime = a.departureDateTime
            WHERE s.flightNo         = :fn
              AND s.departureDateTime = TO_TIMESTAMP(:dt,'YYYY-MM-DD HH24:MI')
              AND s.seatClass         = :sc
        """, { 'fn': flightNo, 'dt': depDT, 'sc': seatClass })
        row = cur.fetchone()
        if not row:
            flash("해당 좌석 정보를 찾을 수 없습니다.", "error")
            return redirect(url_for('reservation.flights_form'))

        remaining, depAP, arrAP, arrDT_obj = row
        if remaining <= 0:
            flash("남은 좌석이 없습니다.", "error")
            return redirect(url_for('reservation.flights_form'))

        # --- [D] 항공사명 조회 -----------------------------------
        cur.execute("""
            SELECT airline
              FROM AIRPLAIN
             WHERE flightNo         = :fn
               AND departureDateTime = TO_TIMESTAMP(:dt,'YYYY-MM-DD HH24:MI')
        """, { 'fn': flightNo, 'dt': depDT })
        airline = cur.fetchone()[0]

        # --- [E] 사용자 이름 조회 --------------------------------
        cur.execute("SELECT name FROM CUSTOMER WHERE cno = :cno", { 'cno': cno })
        user_name = cur.fetchone()[0]

        # --- [F] 예약번호(임시) 생성 ------------------------------
        reserve_no = datetime.now().strftime("%Y%m%d%H%M%S")

        # --- [G] RESERVE 테이블 INSERT ---------------------------
        cur.execute("""
            /* 예약 테이블에 새 레코드 삽입  */
            INSERT INTO RESERVE (
              flightNo, departureDateTime,
              seatClass, payment,
              reserveDateTime, cno
            ) VALUES (
              :fn,
              TO_TIMESTAMP(:dt,'YYYY-MM-DD HH24:MI'),
              :sc,
              :pay,
              SYSTIMESTAMP,
              :cno
            )
        """, {
            'fn': flightNo, 'dt': depDT,
            'sc': seatClass, 'pay': paymentAmt, 'cno': cno
        })

        # --- [H] SEATS 테이블 좌석수 -1 --------------------------
        cur.execute("""
            UPDATE SEATS
               SET no_of_seats = no_of_seats - 1
             WHERE flightNo          = :fn
               AND departureDateTime = TO_TIMESTAMP(:dt,'YYYY-MM-DD HH24:MI')
               AND seatClass         = :sc
        """, { 'fn': flightNo, 'dt': depDT, 'sc': seatClass })

        conn.commit()

    except IntegrityError:
        # UNIQUE 제약 등 충돌 → 이미 예약 존재
        conn.rollback()
        flash("이미 같은 예약이 존재합니다.", "warning")

    except Exception as e:
        # 기타 예외
        conn.rollback()
        flash(f"결제 중 오류가 발생했습니다: {e}", "error")
        return redirect(url_for('reservation.flights_form'))

    finally:
        conn.close()

    # --- [I] 결제 완료 페이지로 -------------------------------
    flash("결제가 완료되었습니다!", "success")
    return render_template(
        'pay.html',
        airline=airline,
        flightNo=flightNo,
        depAP=depAP, arrAP=arrAP,
        depDT=depDT,
        arrDT=arrDT_obj.strftime('%Y-%m-%d %H:%M'),
        seatClass=seatClass,
        remaining=remaining-1,
        price=paymentAmt,
        user_name=user_name,
        show_email_popup=True    # 팝업 트리거
    )


# ===============================================================
# 5. 예약 내역 조회
#    - mode: all / upcoming / range
# ===============================================================
@reservation_bp.route('/history')
def reservation_history():
    cno        = session.get('user_id')
    mode       = request.args.get('mode', 'all')
    start_date = request.args.get('start_date')
    end_date   = request.args.get('end_date')

    # — SQL : 예약 + 항공편 조인 후 필터링 ―――――――――――――――――――――
    sql = """
        SELECT
          r.flightNo,
          TO_CHAR(a.departureDateTime,'YYYY-MM-DD HH24:MI') AS depDT,
          TO_CHAR(a.arrivalDateTime,  'YYYY-MM-DD HH24:MI') AS arrDT,
          a.departureAirport AS depAP,
          a.arrivalAirport   AS arrAP,
          r.seatClass,
          r.payment,
          TO_CHAR(r.reserveDateTime,'YYYY-MM-DD HH24:MI') AS reserveDT
        FROM RESERVE r
        JOIN AIRPLAIN a
          ON r.flightNo          = a.flightNo
         AND r.departureDateTime = a.departureDateTime
        WHERE r.cno = :cno
    """
    binds = { 'cno': cno }

    # ── 모드별 조건 추가 ───────────────────────────────────────
    if mode == 'upcoming':
        # *출발 예정*만
        sql += " AND a.departureDateTime > SYSTIMESTAMP"
    elif mode == 'range' and start_date and end_date:
        # 기간 조회 (양쪽 날짜 모두 내부 포함)
        sql += """
          AND a.departureDateTime BETWEEN
                TO_TIMESTAMP(:start_ts,'YYYY-MM-DD"T"HH24:MI')
            AND TO_TIMESTAMP(:end_ts,  'YYYY-MM-DD"T"HH24:MI')
          AND a.arrivalDateTime   BETWEEN
                TO_TIMESTAMP(:start_ts,'YYYY-MM-DD"T"HH24:MI')
            AND TO_TIMESTAMP(:end_ts,  'YYYY-MM-DD"T"HH24:MI')
        """
        binds['start_ts'] = start_date
        binds['end_ts']   = end_date

    sql += " ORDER BY a.departureDateTime"

    # ―― 실행/결과 렌더 ――――――――――――――――――――――――――――――――――――
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(sql, binds)
    reservations = cur.fetchall()
    conn.close()

    return render_template(
        'reservation_history.html',
        reservations=reservations,
        mode=mode, start_date=start_date, end_date=end_date
    )


# ===============================================================
# 6. 취소 내역 조회  (구조 동일)
# ===============================================================
@reservation_bp.route('/cancel_history', methods=['GET'])
def cancel_history():
    cno = session.get('user_id')
    if not cno:
        flash("로그인이 필요합니다.", "error")
        return redirect(url_for('auth.login'))

    mode       = request.args.get('mode', 'all')
    start_date = request.args.get('start_date')
    end_date   = request.args.get('end_date')

    # ―――― 취소 + 항공편 조인 쿼리 ――――――――――――――――――――――――
    sql = """
        SELECT
          c.flightNo,
          TO_CHAR(a.departureDateTime,'YYYY-MM-DD HH24:MI') AS depDT,
          TO_CHAR(a.arrivalDateTime,  'YYYY-MM-DD HH24:MI') AS arrDT,
          a.departureAirport AS depAP,
          a.arrivalAirport   AS arrAP,
          c.seatClass,
          c.refund           AS refundAmount,
          TO_CHAR(c.cancelDateTime,'YYYY-MM-DD HH24:MI') AS cancelDT
        FROM CANCEL c
        JOIN AIRPLAIN a
          ON c.flightNo          = a.flightNo
         AND c.departureDateTime = a.departureDateTime
        WHERE c.cno = :cno
    """
    binds = { 'cno': cno }

    # 모드 조건
    if mode == 'upcoming':
        sql += " AND c.cancelDateTime > SYSTIMESTAMP"
    elif mode == 'range' and start_date and end_date:
        sql += """
          AND a.departureDateTime BETWEEN
                TO_TIMESTAMP(:start_ts,'YYYY-MM-DD"T"HH24:MI')
            AND TO_TIMESTAMP(:end_ts,  'YYYY-MM-DD"T"HH24:MI')
          AND a.arrivalDateTime   BETWEEN
                TO_TIMESTAMP(:start_ts,'YYYY-MM-DD"T"HH24:MI')
            AND TO_TIMESTAMP(:end_ts,  'YYYY-MM-DD"T"HH24:MI')
        """
        binds['start_ts'] = start_date
        binds['end_ts']   = end_date

    sql += " ORDER BY c.cancelDateTime DESC"

    # 실행
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(sql, binds)
    cancels = cur.fetchall()
    conn.close()

    # 렌더링
    return render_template(
        'cancel_history.html',
        cancels=cancels,
        mode=mode, start_date=start_date, end_date=end_date
    )


# ===============================================================
# 7. 항공권 이메일 발송
# ===============================================================
@reservation_bp.route('/send_ticket_email', methods=['POST'])
def send_ticket_email():
    # 세션에 저장된 이메일(로그인 시 set)
    user_email = session.get('user_email')

    # 폼 hidden 값 가져오기
    reserve_no = request.form.get('reserve_no')
    flightNo   = request.form.get('flightNo')
    depDT      = request.form.get('depDT')
    arrDT      = request.form.get('arrDT')
    seatClass  = request.form.get('seatClass')
    payment    = request.form.get('paymentAmount')

    # 메일 제목/본문 구성
    subject = "CNU-AIR 예약확인서"
    content = (
        f"안녕하세요 {session.get('user_name','고객님')}님,\n\n"
        f"예약번호: {reserve_no}\n"
        f"항공편: {flightNo}\n"
        f"출발: {depDT} / 도착: {arrDT}\n"
        f"좌석: {seatClass}\n"
        f"결제금액: {payment}원\n\n"
        "즐거운 여행 되십시오."
    )

    # NAVER SMTP → send_email_naver 함수 호출
    if send_email_naver(to_email=user_email, subject=subject, content=content):
        flash("항공권 이메일 전송이 완료되었습니다!", "success")
    else:
        flash("이메일 전송에 실패했습니다. 나중에 다시 시도해 주세요.", "error")

    # 다시 예약 상세 화면으로
    return redirect(url_for(
        'reservation.book',
        flightNo=flightNo,
        depDT=depDT,
        seatClass=seatClass
    ))


# ===============================================================
# 8. 통합(예약+취소) 이력 조회
# ===============================================================
@reservation_bp.route('/integrated_history')
def integrated_history():
    # 1) 로그인 확인
    cno = session.get('user_id')
    if not cno:
        flash("로그인이 필요합니다.", "error")
        return redirect(url_for('auth.login'))

    conn = get_connection()
    cur  = conn.cursor()
    try:
        # 2) 예약 목록
        cur.execute("""
            SELECT flightNo, departureDateTime, seatClass,
                   payment, reserveDateTime
              FROM RESERVE
             WHERE cno = :cno
          ORDER BY departureDateTime
        """, { 'cno': cno })
        reservations = cur.fetchall()

        # 3) 취소 목록
        cur.execute("""
            SELECT flightNo, departureDateTime, seatClass,
                   refund, cancelDateTime
              FROM CANCEL
             WHERE cno = :cno
          ORDER BY cancelDateTime
        """, { 'cno': cno })
        cancels = cur.fetchall()

    finally:
        conn.close()

    # 4) 템플릿 전달
    return render_template(
        'integrated_history.html',
        reservations=reservations,
        cancels=cancels
    )