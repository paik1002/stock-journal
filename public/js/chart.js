/**
 * 분봉코멘트 — 프론트엔드 로직
 *
 * - 종목코드를 조회하면 /api/candles 에서 1분봉을 가져와 캔들 차트로 그린다.
 * - 일정 주기로 다시 불러와서 "실시간"처럼 갱신한다 (완전한 웹소켓 스트리밍이
 *   아니라 폴링 방식이다. 네이버의 비공식 차트 API는 푸시 스트림을 제공하지
 *   않기 때문).
 * - /api/comments 로 코멘트를 불러와 차트 위에 매수(▲)/매도(▼) 마커로 표시하고,
 *   화면 오른쪽에 타임라인 목록으로도 보여준다.
 * - 코멘트 작성 시각 = "지금" 이며, 서버가 현재 분(minute)에 맞춰 캔들 시각에
 *   정렬해서 저장한다.
 */

(() => {
  const LWC = window.LightweightCharts;

  const CANDLE_POLL_MS = 10000;
  const COMMENT_POLL_MS = 15000;

  const state = {
    ticker: null,
    candles: [],
    comments: [],
    chart: null,
    candleSeries: null,
    volumeSeries: null,
    seriesMarkers: null,
    candlePollId: null,
    commentPollId: null,
    selectedType: "buy",
  };

  const els = {
    tickerInput: document.getElementById("ticker-input"),
    searchBtn: document.getElementById("search-btn"),
    stockName: document.getElementById("stock-name"),
    stockPrice: document.getElementById("stock-price"),
    stockChange: document.getElementById("stock-change"),
    chartContainer: document.getElementById("chart-container"),
    chartEmpty: document.getElementById("chart-empty"),
    errorBanner: document.getElementById("error-banner"),
    commentForm: document.getElementById("comment-form"),
    commentText: document.getElementById("comment-text"),
    commentSubmit: document.getElementById("comment-submit"),
    typeButtons: Array.from(document.querySelectorAll(".type-btn")),
    commentList: document.getElementById("comment-list"),
    commentEmpty: document.getElementById("comment-empty"),
    quickChips: Array.from(document.querySelectorAll(".chip")),
    lastUpdated: document.getElementById("last-updated"),
  };

  // ------------------------------------------------------------------
  // 차트 초기화
  // ------------------------------------------------------------------
  function initChart() {
    state.chart = LWC.createChart(els.chartContainer, {
      layout: {
        background: { type: "solid", color: "transparent" },
        textColor: "#8590A2",
        fontFamily: "'JetBrains Mono', monospace",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.04)" },
        horzLines: { color: "rgba(255,255,255,0.04)" },
      },
      rightPriceScale: { borderColor: "#1F2530" },
      timeScale: {
        borderColor: "#1F2530",
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: { mode: LWC.CrosshairMode.Normal },
      autoSize: true,
    });

    state.candleSeries = state.chart.addSeries(LWC.CandlestickSeries, {
      upColor: "#2DC97E",
      downColor: "#FF5C72",
      borderVisible: false,
      wickUpColor: "#2DC97E",
      wickDownColor: "#FF5C72",
    });

    state.volumeSeries = state.chart.addSeries(LWC.HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
      color: "rgba(133,144,162,0.45)",
    });
    state.chart.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
    });

    state.seriesMarkers = LWC.createSeriesMarkers(state.candleSeries, []);
  }

  // ------------------------------------------------------------------
  // 렌더링
  // ------------------------------------------------------------------
  function renderCandles() {
    if (!state.candles.length) return;

    state.candleSeries.setData(
      state.candles.map((c) => ({
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    state.volumeSeries.setData(
      state.candles.map((c) => ({
        time: c.time,
        value: c.volume,
        color:
          c.close >= c.open ? "rgba(45,201,126,0.5)" : "rgba(255,92,114,0.5)",
      }))
    );
  }

  // 코멘트의 작성 시각을 실제로 존재하는 분봉 중 가장 가까운 시각에 맞춘다.
  // (코멘트는 "현재 분"에 저장되지만, 그 사이 캔들 목록이 약간 어긋날 수 있어
  //  가장 가까운 캔들에 마커를 붙여 항상 표시되도록 한다.)
  function nearestCandleTime(targetTime) {
    if (!state.candles.length) return targetTime;
    let best = state.candles[0].time;
    let bestDiff = Math.abs(best - targetTime);
    for (const c of state.candles) {
      const diff = Math.abs(c.time - targetTime);
      if (diff < bestDiff) {
        bestDiff = diff;
        best = c.time;
      }
    }
    return best;
  }

  function renderMarkers() {
    const markers = state.comments
      .map((cm) => ({
        time: nearestCandleTime(cm.time),
        position: cm.type === "buy" ? "belowBar" : "aboveBar",
        color: cm.type === "buy" ? "#2DC97E" : "#FF5C72",
        shape: cm.type === "buy" ? "arrowUp" : "arrowDown",
        text: cm.type === "buy" ? "매수" : "매도",
      }))
      .sort((a, b) => a.time - b.time);
    state.seriesMarkers.setMarkers(markers);
  }

  function renderCommentList() {
    els.commentList.innerHTML = "";

    if (!state.comments.length) {
      els.commentEmpty.style.display = "block";
      return;
    }
    els.commentEmpty.style.display = "none";

    const sorted = [...state.comments].sort((a, b) => b.time - a.time);
    for (const cm of sorted) {
      const li = document.createElement("li");
      li.className = `comment-item comment-item--${cm.type}`;

      const head = document.createElement("div");
      head.className = "comment-item__head";

      const tag = document.createElement("span");
      tag.className = `comment-tag comment-tag--${cm.type}`;
      tag.textContent = cm.type === "buy" ? "매수" : "매도";

      const time = document.createElement("span");
      time.className = "comment-time";
      time.textContent = new Date(cm.time * 1000).toLocaleTimeString("ko-KR", {
        hour: "2-digit",
        minute: "2-digit",
      });

      const delBtn = document.createElement("button");
      delBtn.className = "comment-delete";
      delBtn.dataset.id = cm.id;
      delBtn.setAttribute("aria-label", "코멘트 삭제");
      delBtn.textContent = "×";

      head.append(tag, time, delBtn);

      const textEl = document.createElement("p");
      textEl.className = "comment-text";
      textEl.textContent = cm.text;

      li.append(head, textEl);
      els.commentList.appendChild(li);
    }
  }

  function updatePriceHeader() {
    if (!state.candles.length) return;
    const last = state.candles[state.candles.length - 1];
    const first = state.candles[0];
    const diff = last.close - first.open;
    const pct = first.open ? (diff / first.open) * 100 : 0;
    const sign = diff > 0 ? "+" : "";

    els.stockPrice.textContent = `${last.close.toLocaleString("ko-KR")}원`;
    els.stockChange.textContent = `${sign}${diff.toLocaleString(
      "ko-KR"
    )} (${sign}${pct.toFixed(2)}%) · 조회 구간 기준`;
    els.stockChange.classList.toggle("is-up", diff > 0);
    els.stockChange.classList.toggle("is-down", diff < 0);
  }

  // ------------------------------------------------------------------
  // 에러 배너
  // ------------------------------------------------------------------
  function showError(message) {
    els.errorBanner.textContent = message;
    els.errorBanner.style.display = "block";
  }

  function clearError() {
    els.errorBanner.style.display = "none";
    els.errorBanner.textContent = "";
  }

  // ------------------------------------------------------------------
  // API 호출
  // ------------------------------------------------------------------
  async function apiGet(url) {
    const res = await fetch(url);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "요청에 실패했습니다.");
    return data;
  }

  async function fetchCandles(ticker) {
    return apiGet(`/api/candles?ticker=${encodeURIComponent(ticker)}&count=300`);
  }

  async function fetchComments(ticker) {
    return apiGet(`/api/comments?ticker=${encodeURIComponent(ticker)}`);
  }

  async function postComment(ticker, type, text) {
    const res = await fetch("/api/comments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, type, text }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "코멘트 작성에 실패했습니다.");
    return data;
  }

  async function deleteCommentApi(ticker, id) {
    const res = await fetch(
      `/api/comments/${encodeURIComponent(ticker)}/${encodeURIComponent(id)}`,
      { method: "DELETE" }
    );
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || "코멘트 삭제에 실패했습니다.");
    }
  }

  // ------------------------------------------------------------------
  // 메인 플로우
  // ------------------------------------------------------------------
  function stopPolling() {
    if (state.candlePollId) clearInterval(state.candlePollId);
    if (state.commentPollId) clearInterval(state.commentPollId);
    state.candlePollId = null;
    state.commentPollId = null;
  }

  async function refreshCandles() {
    if (!state.ticker) return;
    try {
      const data = await fetchCandles(state.ticker);
      state.candles = data.candles || [];
      renderCandles();
      renderMarkers();
      els.stockName.textContent = data.name || state.ticker;
      updatePriceHeader();
      els.lastUpdated.textContent = `업데이트 ${new Date().toLocaleTimeString(
        "ko-KR"
      )}`;
      els.chartEmpty.style.display = state.candles.length ? "none" : "flex";
      clearError();
    } catch (err) {
      showError(err.message);
    }
  }

  async function refreshComments() {
    if (!state.ticker) return;
    try {
      const data = await fetchComments(state.ticker);
      state.comments = data || [];
      renderMarkers();
      renderCommentList();
    } catch (err) {
      showError(err.message);
    }
  }

  async function loadTicker(rawTicker) {
    const ticker = (rawTicker || "").trim();
    if (!/^\d{6}$/.test(ticker)) {
      showError("종목코드는 6자리 숫자입니다. 예: 005930");
      return;
    }

    stopPolling();
    state.ticker = ticker;
    els.tickerInput.value = ticker;
    clearError();

    await Promise.all([refreshCandles(), refreshComments()]);

    state.candlePollId = setInterval(refreshCandles, CANDLE_POLL_MS);
    state.commentPollId = setInterval(refreshComments, COMMENT_POLL_MS);
  }

  // ------------------------------------------------------------------
  // 이벤트 바인딩
  // ------------------------------------------------------------------
  els.searchBtn.addEventListener("click", () => loadTicker(els.tickerInput.value));
  els.tickerInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") loadTicker(els.tickerInput.value);
  });

  els.quickChips.forEach((chip) => {
    chip.addEventListener("click", () => loadTicker(chip.dataset.ticker));
  });

  els.typeButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      state.selectedType = btn.dataset.type;
      els.typeButtons.forEach((b) => b.classList.toggle("is-active", b === btn));
    });
  });

  els.commentForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!state.ticker) {
      showError("먼저 종목코드를 조회해주세요.");
      return;
    }
    const text = els.commentText.value.trim();
    if (!text) {
      showError("코멘트 내용을 입력해주세요.");
      return;
    }

    els.commentSubmit.disabled = true;
    try {
      await postComment(state.ticker, state.selectedType, text);
      els.commentText.value = "";
      await refreshComments();
      clearError();
    } catch (err) {
      showError(err.message);
    } finally {
      els.commentSubmit.disabled = false;
    }
  });

  els.commentList.addEventListener("click", async (e) => {
    const btn = e.target.closest(".comment-delete");
    if (!btn) return;
    if (!window.confirm("이 코멘트를 삭제할까요?")) return;
    try {
      await deleteCommentApi(state.ticker, btn.dataset.id);
      await refreshComments();
    } catch (err) {
      showError(err.message);
    }
  });

  // ------------------------------------------------------------------
  // 시작
  // ------------------------------------------------------------------
  initChart();
})();
