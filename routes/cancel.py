# routes/cancel.py

from flask import Blueprint, session, flash, redirect, url_for, current_app
from PLUS_ULTRA_AIR.db.db_config import get_connection
from datetime import datetime

# Blueprint 등록: URL prefix "/cancel" 아래에 라우팅
cancel_bp = Blueprint("cancel", __name__, url_prefix="/cancel")

@cancel_bp.route('/<flightNo>/<depDT>/<seatClass>', methods=['POST'])
def cancel_reservation(flightNo, depDT, seatClass):
    """
    예약 취소 처리
    URL 매개변수로 비행기 편번호, 출발일시, 좌석 등급을 받아
    1) 원결제금 조회
    2) 위약금 계산
    3) CANCEL 테이블에 취소 정보 저장
    4) RESERVE 레코드 삭제
    5) SEATS 테이블 좌석 수 복구
    """
    # 로그인된 사용자 cno 가져오기
    cno  = session.get('user_id')
    conn = get_connection()
    cur  = conn.cursor()

    try:
        # 1) depDT (문자열) → datetime 객체 변환
        dep_dt_obj = datetime.strptime(depDT, '%Y-%m-%d %H:%M')

        # 2) 해당 예약의 결제 금액 조회
        cur.execute("""
            SELECT payment
              FROM RESERVE
             WHERE cno              = :cno
               AND flightNo         = :fn
               AND departureDateTime = :dt
               AND seatClass        = :sc
        """, {
            'cno': cno,
            'fn': flightNo,
            'dt': dep_dt_obj,
            'sc': seatClass
        })
        row = cur.fetchone()
        if not row:
            # 예약 정보가 없으면 이력 페이지로 리다이렉트
            flash("취소할 예약을 찾을 수 없습니다.", "error")
            return redirect(url_for('reservation.reservation_history'))
        payment_amount = row[0]

        # 3) 위약금 계산: 출발일과의 차이에 따라 금액 결정
        today     = datetime.now().date()
        depart_on = dep_dt_obj.date()
        days_diff = (depart_on - today).days

        if   days_diff >= 15:
            penalty = 150_000
        elif  4 <= days_diff <= 14:
            penalty = 180_000
        elif  1 <= days_diff <= 3:
            penalty = 250_000
        elif  days_diff == 0:
            # 당일 취소는 전액 위약금
            penalty = payment_amount
        else:
            # 출발 이후 취소 불가
            flash("출발 이후에는 취소할 수 없습니다.", "error")
            return redirect(url_for('reservation.reservation_history'))

        refund_amount = max(payment_amount - penalty, 0)

        # 4) CANCEL 테이블에 취소 내역 삽입
        cur.execute("""
            INSERT INTO CANCEL (
              flightNo,
              departureDateTime,
              seatClass,
              refund,
              cancelDateTime,
              cno
            ) VALUES (
              :fn, :dt, :sc,
              :refund,
              SYSTIMESTAMP,
              :cno
            )
        """, {
            'fn':     flightNo,
            'dt':     dep_dt_obj,
            'sc':     seatClass,
            'refund': refund_amount,
            'cno':    cno,
        })

        # 5) RESERVE 레코드 삭제: 취소된 예약 제거
        cur.execute("""
            DELETE FROM RESERVE
             WHERE cno              = :cno
               AND flightNo         = :fn
               AND departureDateTime = :dt
               AND seatClass        = :sc
        """, {
            'cno': cno,
            'fn': flightNo,
            'dt': dep_dt_obj,
            'sc': seatClass
        })

        # 6) SEATS 테이블 좌석 수 복구: 남은 좌석 +1
        cur.execute("""
            UPDATE SEATS
               SET no_of_seats = no_of_seats + 1
             WHERE flightNo         = :fn
               AND departureDateTime = :dt
               AND seatClass        = :sc
        """, {
            'fn': flightNo,
            'dt': dep_dt_obj,
            'sc': seatClass
        })

        # 트랜잭션 커밋 및 사용자에게 성공 메시지 플래시
        conn.commit()
        flash(
            f"예약이 취소되었습니다. 위약금: {penalty:,}원, "
            f"환불금액: {refund_amount:,}원",
            "success"
        )

    except Exception as e:
        # 예외 발생 시 롤백 및 에러 로깅, 사용자 에러 메시지
        conn.rollback()
        current_app.logger.error("예약 취소 중 예외 발생", exc_info=True)
        flash(f"취소 중 오류가 발생했습니다: {e}", "error")

    finally:
        conn.close()

    # 취소 완료 후 예약 이력 페이지로 리다이렉트
    return redirect(url_for('reservation.reservation_history'))