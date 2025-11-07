# File: routes/statistics.py

from flask import Blueprint, render_template, request
from PLUS_ULTRA_AIR.db.db_config import get_connection

# 관리자 통계 기능을 위한 Blueprint 설정
statistics_bp = Blueprint(
    'statistics',
    __name__,
    url_prefix='/admin_statistics'  # URL 접두사 지정
)

@statistics_bp.route('/', methods=['GET'])
def admin_statistics():
    """
    GET /admin_statistics
    - 쿼리스트링 'tab' 파라미터를 읽어 활성 탭을 결정함 (기본값: 'group')
    - DB 연결 후 GROUP ROLLUP과 WINDOW RANK 두 가지 통계 쿼리를 실행함
    - 조회된 결과를 각각 딕셔너리 리스트로 변환하여 템플릿에 전달함
    """
    # 1) 탭 정보 가져오기 (group 또는 window)
    active_tab = request.args.get('tab', 'group')

    # 2) DB 연결
    conn = get_connection()
    cur  = conn.cursor()

    # 3) GROUP ROLLUP 쿼리: 항공사·좌석등급별 가격 합계를 구함
    cur.execute("""
        SELECT
          CASE GROUPING(A.airline)
            WHEN 1 THEN '모든 항공사' ELSE A.airline END    AS airline,
          CASE GROUPING(S.seatClass)
            WHEN 1 THEN '모든 좌석 등급' ELSE S.seatClass END AS seat_class,
          SUM(S.price)                                     AS total_price
        FROM AIRPLAIN A
        JOIN SEATS S 
          ON A.flightNo           = S.flightNo
         AND A.departureDateTime  = S.departureDateTime
        JOIN RESERVE R 
          ON S.flightNo           = R.flightNo
         AND S.departureDateTime  = R.departureDateTime
         AND S.seatClass          = R.seatClass
        JOIN CUSTOMER C 
          ON R.cno = C.cno
        GROUP BY ROLLUP(A.airline, S.seatClass)
        ORDER BY A.airline NULLS LAST, S.seatClass NULLS LAST
    """)
    # 결과를 리스트 내의 딕셔너리로 변환
    rollup = [
        {"airline": r[0], "seat_class": r[1], "total_price": r[2]}
        for r in cur.fetchall()
    ]

    # 4) WINDOW RANK 쿼리: 항공사별로 가격 순위를 계산함
    cur.execute("""
        SELECT
          C.name       AS customer_name,
          A.airline    AS airline,
          S.seatClass  AS seat_class,
          S.price      AS price,
          RANK() OVER (
            PARTITION BY A.airline
            ORDER BY S.price DESC
          )            AS price_rank
        FROM RESERVE R
        JOIN CUSTOMER C 
          ON R.cno = C.cno
        JOIN SEATS S 
          ON R.flightNo           = S.flightNo
         AND R.departureDateTime  = S.departureDateTime
         AND S.seatClass          = R.seatClass
        JOIN AIRPLAIN A 
          ON S.flightNo           = A.flightNo
         AND S.departureDateTime  = A.departureDateTime
    """)
    # 결과를 리스트 내의 딕셔너리로 변환
    window = [
        {
            "customer_name": r[0],
            "airline":       r[1],
            "seat_class":    r[2],
            "price":         r[3],
            "price_rank":    r[4],
        }
        for r in cur.fetchall()
    ]

    # 5) DB 연결 종료
    conn.close()

    # 6) 템플릿 렌더링: 활성 탭과 두 통계 결과를 전달함
    return render_template(
        'admin_statistics.html',
        active_tab  = active_tab,
        group_stats = rollup,
        rank_stats  = window
    )