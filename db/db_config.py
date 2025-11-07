import oracledb

# Oracle Instant Client 경로 설정: 실제 설치된 경로로 수정해야 함
oracledb.init_oracle_client(lib_dir="/opt/oracle/instantclient")

def get_connection():
    """
    데이터베이스 연결을 생성하여 반환하는 함수
    - DSN(Data Source Name)을 통해 호스트, 포트, 서비스명을 지정
    - 사용자명·비밀번호를 사용해 접속
    """
    # 로컬 호스트의 1521 포트, XE 서비스로 DSN 생성
    dsn = oracledb.makedsn("localhost", 1521, service_name="XE")  # 예: "XE" 또는 "ORCL"
    # 지정된 DSN과 사용자 credentials로 Oracle DB에 연결
    conn = oracledb.connect(
        user="d202102535",      # Oracle 사용자 계정
        password="1876",        # Oracle 사용자 비밀번호
        dsn=dsn                 # 앞서 생성한 DSN
    )
    return conn  # 호출한 쪽에서 이 커넥션을 사용 후 반드시 close() 해야 함