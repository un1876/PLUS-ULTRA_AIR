import smtplib
from email.mime.text import MIMEText


# ---------------------------------------------------------------------------
# 함수: send_email_naver
#  - NAVER SMTP 서버를 통해 텍스트 이메일을 전송한다.
#  - 성공 시 True, 실패 시 False 를 반환한다.
#  - **실서비스에서는 하드코딩된 비밀번호 대신 환경변수 / Secrets Manager 사용 권장**
# ---------------------------------------------------------------------------
def send_email_naver(to_email, subject, content):
    # 1) SMTP 서버 정보(NAVER 고정)
    smtp_server = "smtp.naver.com"
    smtp_port = 465  # SSL 포트

    # 2) 발신 계정 정보
    user = "ehddjs1101@naver.com"
    password = "SVB9KUV5UXDP"  # ⚠️ 실제 배포 시에는 코드에 직접 노출 X

    # 3) MIME 메시지 객체 생성 (UTF-8 인코딩)
    msg = MIMEText(content, _charset="utf-8")
    msg["Subject"] = subject  # 메일 제목
    msg["From"] = user  # 발신자
    msg["To"] = to_email  # 수신자

    try:
        # 4) NAVER SMTP 서버에 SSL 로 연결 후 로그인
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(user, password)

        # 5) 메일 발송
        server.sendmail(user, to_email, msg.as_string())
        server.quit()
        return True  # 성공 여부 반환
    except Exception as e:
        # 6) 오류 발생 시 로그 출력 후 False 반환
        print("❌ 이메일 전송 실패:", e)
        return False