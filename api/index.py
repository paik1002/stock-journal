"""
Vercel Python 런타임 진입점.

Vercel은 api/ 디렉터리 안의 파일들을 각각 별도의 서버리스 함수로 만든다.
이 파일은 프로젝트 루트의 app.py에 정의된 Flask(WSGI) 앱 객체를 그대로
다시 내보내기만 한다. 실제 라우팅/로직은 모두 app.py / stock_data.py /
firebase_service.py 에 있다.

vercel.json의 rewrites 설정이 모든 경로("/(.*)")를 이 함수로 보내주기 때문에,
Flask 자체의 라우터가 /, /api/candles, /api/comments 등을 그대로 처리한다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402,F401  (Vercel이 이 'app' 변수를 자동으로 찾는다)
