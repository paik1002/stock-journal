"""
국장 1분봉 코멘트 차트 - Flask 백엔드

라우트
------
GET  /                              메인 페이지
GET  /api/candles?ticker=005930     1분봉 캔들 데이터 조회 (네이버 금융 비공식 API)
GET  /api/comments?ticker=005930    해당 종목의 코멘트 목록 조회 (Firestore)
POST /api/comments                  코멘트 작성 (작성 시각 = 현재 시각, 즉 매수/매도 "지금"을 기록)
DELETE /api/comments/<ticker>/<id>  코멘트 삭제

로컬 실행
--------
1) pip install -r requirements.txt --break-system-packages  (필요 시)
2) 프로젝트 루트에 serviceAccountKey.json 파일을 둔다.
3) python app.py
4) http://localhost:5000 접속
"""
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, render_template, request, send_from_directory

from firebase_service import add_comment, delete_comment, get_comments
from stock_data import StockDataError, fetch_minute_candles

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

KST = ZoneInfo("Asia/Seoul")
TICKER_RE = re.compile(r"^\d{6}$")

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
)


def _is_valid_ticker(ticker: str) -> bool:
    return bool(ticker) and bool(TICKER_RE.match(ticker))


# ---------------------------------------------------------------------------
# 페이지
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# 로컬(python app.py) 실행 시 /public 정적 파일을 서빙하기 위한 라우트.
# Vercel에 배포하면 /public 디렉터리는 CDN이 직접 서빙하므로 이 라우트는 호출되지 않는다.
@app.route("/css/<path:filename>")
def public_css(filename):
    return send_from_directory(os.path.join(PUBLIC_DIR, "css"), filename)


@app.route("/js/<path:filename>")
def public_js(filename):
    return send_from_directory(os.path.join(PUBLIC_DIR, "js"), filename)


# ---------------------------------------------------------------------------
# 시세 API
# ---------------------------------------------------------------------------
@app.route("/api/candles")
def api_candles():
    ticker = request.args.get("ticker", "").strip()
    count = request.args.get("count", 300, type=int) or 300
    count = max(10, min(count, 1500))

    if not _is_valid_ticker(ticker):
        return jsonify({"error": "종목코드는 6자리 숫자여야 합니다. 예: 005930"}), 400

    try:
        result = fetch_minute_candles(ticker, count=count)
    except StockDataError as exc:
        return jsonify({"error": str(exc)}), 502
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"시세 데이터를 가져오지 못했습니다: {exc}"}), 502

    return jsonify(result)


# ---------------------------------------------------------------------------
# 코멘트 API (Firestore)
# ---------------------------------------------------------------------------
@app.route("/api/comments", methods=["GET"])
def api_get_comments():
    ticker = request.args.get("ticker", "").strip()
    if not _is_valid_ticker(ticker):
        return jsonify({"error": "종목코드는 6자리 숫자여야 합니다."}), 400

    try:
        comments = get_comments(ticker)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"코멘트를 불러오지 못했습니다: {exc}"}), 502

    return jsonify(comments)


@app.route("/api/comments", methods=["POST"])
def api_add_comment():
    payload = request.get_json(silent=True) or {}
    ticker = (payload.get("ticker") or "").strip()
    comment_type = payload.get("type")
    text = (payload.get("text") or "").strip()

    if not _is_valid_ticker(ticker):
        return jsonify({"error": "종목코드는 6자리 숫자여야 합니다."}), 400
    if comment_type not in ("buy", "sell"):
        return jsonify({"error": "type 값은 'buy' 또는 'sell' 이어야 합니다."}), 400
    if not text:
        return jsonify({"error": "코멘트 내용을 입력해주세요."}), 400
    if len(text) > 500:
        return jsonify({"error": "코멘트는 500자 이하로 작성해주세요."}), 400

    # 코멘트가 붙는 시점 = "글을 작성한 시각"의 분봉(현재 진행 중인 1분봉의 시작 시각)
    now_minute = datetime.now(KST).replace(second=0, microsecond=0)
    candle_time = int(now_minute.timestamp())

    try:
        saved = add_comment(ticker, comment_type, text, candle_time)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"코멘트를 저장하지 못했습니다: {exc}"}), 502

    return jsonify(saved), 201


@app.route("/api/comments/<ticker>/<comment_id>", methods=["DELETE"])
def api_delete_comment(ticker, comment_id):
    if not _is_valid_ticker(ticker):
        return jsonify({"error": "종목코드는 6자리 숫자여야 합니다."}), 400

    try:
        delete_comment(ticker, comment_id)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"코멘트를 삭제하지 못했습니다: {exc}"}), 502

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
