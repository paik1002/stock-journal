"""
네이버 금융의 비공식(undocumented) 차트 API를 이용해 1분봉 시세를 가져온다.

주의
----
이 엔드포인트는 네이버 금융 웹 차트가 내부적으로 사용하는 공개 데이터로,
공식적으로 문서화되거나 보장되는 API가 아니다. 네이버 쪽 사정으로 응답 형식이
바뀌거나 호출이 차단될 수 있다. 운영 서비스에서 안정적인 실시간 시세가 필요하다면
한국투자증권 OpenAPI, 키움 OpenAPI 등 정식 시세 제공사의 API 사용을 권장한다.
"""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

KST = ZoneInfo("Asia/Seoul")

BASE_URL = "https://fchart.stock.naver.com/sise.nhn"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}

# 응답은 <chartdata symbol="005930" name="삼성전자" ...><item data="20240621093000|71200|71300|71100|71200|123456"/>...
NAME_RE = re.compile(r'<chartdata[^>]*\bname="([^"]*)"', re.IGNORECASE)
ITEM_RE = re.compile(r'<item\s+data="([^"]+)"\s*/?>', re.IGNORECASE)


class StockDataError(Exception):
    """시세 조회 중 발생한 오류를 나타낸다."""


def _parse_datetime_to_epoch(raw: str) -> int:
    raw = raw.strip()
    if len(raw) == 8:  # YYYYMMDD (day/week/month 캔들)
        dt = datetime.strptime(raw, "%Y%m%d")
    elif len(raw) == 12:  # YYYYMMDDHHMM (분봉)
        dt = datetime.strptime(raw, "%Y%m%d%H%M")
    elif len(raw) == 14:  # YYYYMMDDHHMMSS (혹시 초 단위가 오는 경우 대비)
        dt = datetime.strptime(raw, "%Y%m%d%H%M%S")
    else:
        raise ValueError(f"알 수 없는 날짜/시간 형식: {raw!r}")

    dt = dt.replace(tzinfo=KST)
    return int(dt.timestamp())


def fetch_minute_candles(ticker: str, count: int = 300) -> dict:
    """6자리 종목코드의 1분봉 캔들 데이터를 가져온다.

    Returns
    -------
    {
        "ticker": "005930",
        "name": "삼성전자",
        "candles": [
            {"time": 1719276600, "open": ..., "high": ..., "low": ..., "close": ..., "volume": ...},
            ...
        ]
    }
    """
    params = {
        "symbol": ticker,
        "timeframe": "minute",
        "count": count,
        "requestType": 0,
    }

    try:
        resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=6)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise StockDataError(f"네이버 시세 서버에 접속할 수 없습니다: {exc}") from exc

    text = resp.text
    if not text or "<item" not in text:
        raise StockDataError("존재하지 않는 종목코드이거나 거래 데이터가 없습니다.")

    name_match = NAME_RE.search(text)
    stock_name = name_match.group(1) if name_match and name_match.group(1) else ticker

    candles = []
    for raw_item in ITEM_RE.findall(text):
        parts = raw_item.split("|")
        if len(parts) < 6:
            continue
        dt_str, o, h, l, c, v = parts[:6]
        try:
            ts = _parse_datetime_to_epoch(dt_str)
            candles.append(
                {
                    "time": ts,
                    "open": float(o),
                    "high": float(h),
                    "low": float(l),
                    "close": float(c),
                    "volume": float(v),
                }
            )
        except (ValueError, TypeError):
            # 형식이 어긋난 항목은 건너뛴다 (네이버 응답에 빈 항목이 섞이는 경우가 있음)
            continue

    if not candles:
        raise StockDataError("캔들 데이터를 파싱하지 못했습니다. 종목코드를 확인해주세요.")

    candles.sort(key=lambda x: x["time"])
    return {"ticker": ticker, "name": stock_name, "candles": candles}
