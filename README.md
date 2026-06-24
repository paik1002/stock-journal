# 분봉코멘트 — 국장 1분봉 코멘트 차트

종목코드(티커)를 입력하면 1분봉 캔들 차트를 보여주고, 매수/매도 시점에 코멘트를
남기면 해당 분봉 위에 마커로 표시되는 트레이딩 노트 웹앱입니다.

스택: **Firebase(Firestore) · Vercel · Python · Flask · HTML · CSS · GitHub**

---

## 1. 동작 방식 요약

- **시세**: 네이버 금융이 차트를 그릴 때 내부적으로 쓰는 비공식 API
  (`fchart.stock.naver.com`)에서 1분봉을 가져옵니다. 공식 API가 아니므로
  형식이 바뀌거나 일시적으로 막힐 수 있습니다. 또한 실제 틱 단위 실시간이
  아니라 **10초 간격 폴링**으로 갱신되는 "준 실시간"입니다.
- **코멘트**: Firestore에 `tickers/{종목코드}/comments/{문서ID}` 구조로
  저장됩니다. 작성 시점의 **현재 시각(분 단위)**이 자동으로 캔들 시각에
  맞춰 저장되고, 차트의 해당 분봉 위에 매수(▲ 초록) / 매도(▼ 빨강) 마커로
  표시됩니다.
- 모든 Firestore 접근은 **서버(Flask)** 쪽에서 `serviceAccountKey.json`을
  이용한 Firebase Admin SDK로만 이루어집니다. 브라우저는 Firebase에 직접
  접속하지 않고 우리 Flask API(`/api/...`)만 호출합니다.

## 2. 폴더 구조

```
kr-stock-comment-chart/
├── api/
│   └── index.py          # Vercel 진입점 (app.py를 그대로 불러옴)
├── app.py                 # Flask 앱 (로컬 실행: python app.py)
├── stock_data.py           # 네이버 비공식 차트 API 클라이언트
├── firebase_service.py     # Firestore 코멘트 CRUD (Admin SDK)
├── templates/
│   └── index.html
├── public/                 # 정적 파일 (Vercel이 CDN으로 직접 서빙)
│   ├── css/style.css
│   └── js/chart.js
├── requirements.txt
├── vercel.json
├── .python-version
├── .gitignore
├── .vercelignore
├── serviceAccountKey.example.json   # 키 파일 형식 예시 (진짜 키 아님)
└── README.md
```

## 3. Firebase 준비물 (딱 이것만 하면 됩니다)

1. Firebase 콘솔에서 프로젝트를 생성합니다.
2. **Firestore Database**를 한 번 만듭니다 (네이티브 모드, 기본 설정 그대로
   "다음 → 만들기"만 누르면 됩니다). 보안 규칙이나 색인은 손댈 필요가
   없습니다 — 이 앱은 서버에서 Admin SDK로만 접근하기 때문에 클라이언트
   보안 규칙이 적용되지 않고, 코멘트도 종목별 서브컬렉션으로 나뉘어 있어
   복합 색인이 필요 없습니다.
3. **프로젝트 설정 → 서비스 계정 → "새 비공개 키 생성"**으로 키 파일을
   내려받습니다.
4. 받은 파일 이름을 `serviceAccountKey.json`으로 바꿔서, `app.py`와 같은
   위치(프로젝트 루트)에 둡니다.

Authentication, Hosting, Storage, Cloud Functions 등 다른 Firebase 제품은
전혀 사용하지 않습니다.

## 4. 로컬 실행

```bash
pip install -r requirements.txt          # 막히면: pip install -r requirements.txt --break-system-packages
# serviceAccountKey.json 을 프로젝트 루트에 둔 뒤
python app.py
```

브라우저에서 http://localhost:5000 접속.

## 5. GitHub에 올리기

`.gitignore`에 `serviceAccountKey.json`이 이미 제외되어 있으므로, 실제 키
파일은 절대 커밋되지 않습니다. 평소처럼 커밋/푸시하면 됩니다.

```bash
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

## 6. Vercel 배포

이 프로젝트는 Vercel의 **Python 런타임 zero-config 방식**을 사용합니다
(`api/index.py`가 Flask `app` 객체를 그대로 내보내고, `vercel.json`의
`rewrites`가 모든 경로를 그쪽으로 보냅니다). 별도의 `builds` 설정은 필요
없습니다.

`serviceAccountKey.json`은 GitHub에는 올라가지 않으므로, **GitHub 연동
방식(Vercel 대시보드에서 Import)으로 배포하면 그 파일이 없어 Firestore
호출이 실패**합니다. 가장 간단한 해결책은 Vercel CLI로 **로컬 폴더를 직접
배포**하는 것입니다 — 이러면 `serviceAccountKey.json`이 로컬에만 있어도
배포물에 함께 포함됩니다 (`.vercelignore`가 이 파일을 굳이 제외하지 않도록
이미 설정해 두었습니다).

```bash
npm install -g vercel     # 처음 한 번만
vercel login
cd kr-stock-comment-chart
vercel --prod
```

배포 중 프로젝트 이름 등을 물으면 기본값으로 진행하면 됩니다. 코드를
수정한 뒤 다시 배포할 때도 같은 디렉터리에서 `vercel --prod`만 실행하면
됩니다 (이때도 로컬의 `serviceAccountKey.json`이 함께 올라갑니다).

> 참고: GitHub 저장소는 "코드 보관/이력 관리" 용도로 그대로 쓰고, 실제
> 배포만 CLI로 하는 방식입니다. Firebase 쪽에 아무것도 더 추가하지 않고도
> 동작하도록 한 절충안입니다.

## 7. 한계 / 참고

- 네이버 비공식 API는 언제든 바뀌거나 막힐 수 있습니다. 운영 서비스로
  쓰려면 한국투자증권 OpenAPI, 키움 OpenAPI 등 정식 시세 제공사 API로
  교체하는 것을 권장합니다.
- 차트는 [TradingView Lightweight Charts™](https://www.tradingview.com/lightweight-charts/)
  (무료/오픈소스)를 사용하며, 라이선스 조건에 따라 차트 위에 TradingView
  출처 로고가 기본으로 표시됩니다.
- 이 앱이 제공하는 가격/등락 정보는 투자 판단의 근거가 아닙니다.
