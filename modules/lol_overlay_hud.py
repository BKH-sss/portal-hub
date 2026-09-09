"""
lol_overlay_hud.py
=============================================================================
🖥️ JARVIS / SKADI: 롤(LoL) 실시간 인게임 반투명 플로팅 올인원 오버레이 HUD
=============================================================================
- 역할:
    1. 싱글 모니터 및 듀얼 모니터 게이머를 위한 초경량 반투명 HUD 제공 (/overlay)
    2. 🎴 3개 증강 카드 상단 실시간 티어(OP/S/A/B/C) & 순위 오버레이 (/overlay/augments)
    3. 🔒 롤 포커스 연동 모드: 사용자가 롤 게임/클라이언트를 조작 중일 때만 자동 표시, 다른 작업 시 부드럽게 자동 숨김
    4. 🗺️ 전술 레이더: 0.3ms 미니맵 캡처 & 갱킹 ETA 속도 벡터 카운트다운
    5. ⚡ 적 스펠 트래커: 5인 점멸/텔포 원클릭 쿨타임 추적 및 만료 15초 전 예고
    6. 🐉 오브젝트 타이머: 용, 바론, 유충, 전령 실시간 카운트다운
    7. 💰 경제 & 지표: 팀 골드 격차 (+2.4k Gold Lead) & 분당 CS(CS/min) 실시간 게이지
    8. 🎲 칼바람 증강체: 아수라장 199종 증강체 1순위 추천 팝업
=============================================================================
"""

import os
import sys
import subprocess
from typing import Dict, Any, Optional

try:
    from modules._safe_router import (
        APIRouter, HTTPException, Response, HTMLResponse, FileResponse,
        JSONResponse, Request, WebSocket, WebSocketDisconnect, FastAPI,
        CORSMiddleware, BaseModel, Field
    )
except ImportError:
    try:
        from _safe_router import (
            APIRouter, HTTPException, Response, HTMLResponse, FileResponse,
            JSONResponse, Request, WebSocket, WebSocketDisconnect, FastAPI,
            CORSMiddleware, BaseModel, Field
        )
    except ImportError:
        pass

# =============================================================================
# 🚀 1. FastAPI APIRouter
# =============================================================================
router = APIRouter(tags=["LoL Floating Overlay HUD"])


# =============================================================================
# 🎴 2. 3개 증강 카드 상단 전용 실시간 티어 오버레이 HTML (/overlay/augments)
# =============================================================================
AUGMENT_OVERLAY_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>JARVIS LoL Real-Time Augment Tier Overlay</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; user-select: none; }
        body {
            background: transparent;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Malgun Gothic", sans-serif;
            color: #fff;
            overflow: hidden;
            width: 100vw;
            height: 100vh;
            position: relative;
        }

        /* 상단 플로팅 컨트롤 바 */
        .top-ctrl-bar {
            position: fixed;
            top: 12px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(10, 15, 26, 0.94);
            border: 1px solid rgba(0, 229, 255, 0.55);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.85), 0 0 22px rgba(0, 229, 255, 0.35);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-radius: 30px;
            padding: 6px 18px;
            display: flex;
            align-items: center;
            gap: 12px;
            z-index: 10000;
            transition: all 0.3s ease;
        }

        .brand-title {
            font-size: 12px;
            font-weight: 900;
            color: #00e5ff;
            display: flex;
            align-items: center;
            gap: 6px;
            letter-spacing: 0.5px;
        }

        .ctrl-btn {
            background: rgba(0, 229, 255, 0.15);
            border: 1px solid rgba(0, 229, 255, 0.4);
            color: #00e5ff;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 16px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 5px;
            transition: all 0.2s;
        }

        .ctrl-btn:hover {
            background: #00e5ff;
            color: #050811;
            box-shadow: 0 0 14px rgba(0, 229, 255, 0.6);
            transform: scale(1.04);
        }

        .ctrl-btn.active {
            background: rgba(0, 255, 136, 0.25);
            border-color: #00ff88;
            color: #00ff88;
        }

        .champ-badge {
            background: rgba(255, 215, 0, 0.18);
            border: 1px solid rgba(255, 215, 0, 0.55);
            color: #ffd700;
            font-size: 11px;
            font-weight: 800;
            padding: 4px 12px;
            border-radius: 16px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 5px;
        }

        .champ-badge:hover {
            background: #ffd700;
            color: #050811;
            box-shadow: 0 0 12px rgba(255, 215, 0, 0.6);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #00ff88;
            box-shadow: 0 0 8px #00ff88;
            animation: pulse-dot 1.5s infinite alternate;
        }

        @keyframes pulse-dot {
            from { opacity: 0.6; }
            to { opacity: 1; }
        }

        /* 3개 증강 카드 상단 배치 컨테이너 */
        .augment-cards-container {
            position: absolute;
            top: var(--top-pos, 8.5vh);
            left: 0;
            width: 100vw;
            display: flex;
            justify-content: space-evenly;
            align-items: flex-start;
            padding: 0 2vw;
            pointer-events: none;
            transition: top 0.2s ease, opacity 0.3s ease;
        }

        .card-slot {
            width: 28vw;
            max-width: 400px;
            min-width: 290px;
            pointer-events: auto;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 6px;
            animation: fadeInCard 0.4s ease forwards;
        }

        @keyframes fadeInCard {
            from { opacity: 0; transform: translateY(-12px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* 티어 뱃지 카드 박스 */
        .tier-card {
            width: 100%;
            background: rgba(10, 15, 26, 0.95);
            backdrop-filter: blur(18px);
            -webkit-backdrop-filter: blur(18px);
            border-radius: 14px;
            padding: 14px;
            display: flex;
            flex-direction: column;
            gap: 9px;
            position: relative;
            box-shadow: 0 12px 36px rgba(0, 0, 0, 0.85);
        }

        /* 👑 OP / 0티어 스타일 */
        .tier-card.tier-op {
            border: 2px solid #ffd700;
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.9), 0 0 32px rgba(255, 215, 0, 0.6);
            animation: pulse-op 1.5s infinite alternate;
        }

        @keyframes pulse-op {
            from { box-shadow: 0 0 15px rgba(255, 215, 0, 0.4); border-color: rgba(255, 215, 0, 0.7); }
            to { box-shadow: 0 0 35px rgba(255, 215, 0, 0.9); border-color: #ffd700; }
        }

        /* ⭐ S티어 스타일 */
        .tier-card.tier-s {
            border: 2px solid #00e5ff;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8), 0 0 24px rgba(0, 229, 255, 0.5);
        }

        /* 🥇 A티어 스타일 */
        .tier-card.tier-a {
            border: 1.5px solid #00ff88;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.7), 0 0 18px rgba(0, 255, 136, 0.4);
        }

        /* 🥈 B티어 스타일 */
        .tier-card.tier-b {
            border: 1px solid rgba(139, 148, 158, 0.6);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.6);
        }

        /* 상단 헤더 */
        .tier-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255,255,255,0.12);
            padding-bottom: 6px;
        }

        .tier-badge-pill {
            font-size: 13px;
            font-weight: 900;
            letter-spacing: 0.5px;
            padding: 3px 10px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            gap: 5px;
        }

        .tier-badge-pill.op {
            background: linear-gradient(135deg, #ffd700, #ff9100);
            color: #050811;
            box-shadow: 0 0 14px rgba(255, 215, 0, 0.7);
        }

        .tier-badge-pill.s {
            background: rgba(0, 229, 255, 0.25);
            color: #00e5ff;
            border: 1px solid rgba(0, 229, 255, 0.7);
        }

        .tier-badge-pill.a {
            background: rgba(0, 255, 136, 0.22);
            color: #00ff88;
            border: 1px solid rgba(0, 255, 136, 0.6);
        }

        .tier-badge-pill.b {
            background: rgba(139, 148, 158, 0.22);
            color: #c9d1d9;
            border: 1px solid rgba(139, 148, 158, 0.5);
        }

        .rank-pill {
            font-size: 11px;
            font-weight: 800;
            padding: 3px 9px;
            border-radius: 8px;
        }

        .rank-pill.rank-1 {
            background: rgba(255, 215, 0, 0.2);
            color: #ffd700;
            border: 1px solid rgba(255, 215, 0, 0.6);
        }

        .rank-pill.rank-2 {
            background: rgba(0, 229, 255, 0.18);
            color: #00e5ff;
        }

        .rank-pill.rank-3 {
            background: rgba(255, 255, 255, 0.1);
            color: #8b949e;
        }

        /* 증강체 명 */
        .aug-name-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .aug-name-text {
            font-size: 15px;
            font-weight: 900;
            color: #ffffff;
            text-shadow: 0 0 12px rgba(255,255,255,0.4);
        }

        .aug-rarity-badge {
            font-size: 11px;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 4px;
            background: rgba(255,255,255,0.08);
            color: #c9d1d9;
        }

        /* 핵심 시너지 사유 버블 */
        .aug-reason-bubble {
            background: rgba(255, 255, 255, 0.06);
            border-left: 3px solid #00e5ff;
            border-radius: 4px;
            padding: 7px 9px;
            font-size: 11.5px;
            line-height: 1.45;
            color: #e6edf3;
            display: flex;
            gap: 7px;
        }

        .tier-op .aug-reason-bubble {
            border-left-color: #ffd700;
            background: rgba(255, 215, 0, 0.1);
            color: #fff8e1;
        }

        /* 메트릭 태그 바 */
        .aug-metrics-row {
            display: flex;
            justify-content: space-between;
            font-size: 10.5px;
            color: #8b949e;
            padding-top: 2px;
        }

        .metric-item {
            display: flex;
            align-items: center;
            gap: 4px;
        }

        /* 하단 카드 지목 화살표 */
        .pointer-arrow {
            font-size: 20px;
            animation: bounce-arrow 1s infinite alternate ease-in-out;
            margin-top: 2px;
            filter: drop-shadow(0 0 8px currentColor);
        }

        .pointer-arrow.op-arrow { color: #ffd700; }
        .pointer-arrow.s-arrow { color: #00e5ff; }
        .pointer-arrow.a-arrow { color: #00ff88; }
        .pointer-arrow.b-arrow { color: #8b949e; }

        @keyframes bounce-arrow {
            from { transform: translateY(0); }
            to { transform: translateY(6px); }
        }

        /* 토스트 알림 */
        .toast-msg {
            position: fixed;
            top: 70px;
            left: 50%;
            transform: translateX(-50%) translateY(-10px);
            background: rgba(10, 15, 26, 0.95);
            border: 1px solid rgba(0, 229, 255, 0.6);
            box-shadow: 0 8px 30px rgba(0,0,0,0.8), 0 0 15px rgba(0,229,255,0.4);
            backdrop-filter: blur(12px);
            color: #00e5ff;
            font-size: 12px;
            font-weight: 700;
            padding: 8px 18px;
            border-radius: 20px;
            pointer-events: none;
            opacity: 0;
            transition: all 0.3s ease;
            z-index: 20000;
        }

        .toast-msg.show {
            opacity: 1;
            transform: translateX(-50%) translateY(0);
        }
    </style>
</head>
<body>
    <div id="toastMsg" class="toast-msg"></div>

    <!-- 상단 플로팅 컨트롤 바 -->
    <div class="top-ctrl-bar">
        <div class="brand-title">
            <span class="status-dot"></span>
            <i class="fa-solid fa-dice-d20"></i> 증강체 실시간 티어 HUD
        </div>
        <div class="champ-badge" onclick="changeChampionPrompt()" title="클릭하여 플레이 챔피언 변경">
            <i class="fa-solid fa-shield-halved"></i> <span id="currentChampText">타릭</span>
        </div>
        <button class="ctrl-btn" onclick="scanScreenVision()" title="화면의 3개 증강체 즉시 OCR 비전 스캔 (단축키: F1)">
            <i class="fa-solid fa-camera"></i> 화면 스캔 (F1)
        </button>
        <button class="ctrl-btn" onclick="loadTaricScreenshotDemo()" style="background:rgba(0,229,255,0.2);border-color:#00e5ff;color:#00e5ff;" title="타릭 스크린샷 3개 증강(격려하기/처형시간/자연의회복) 테스트">
            <i class="fa-solid fa-gem"></i> 🧪 타릭 스샷 프리셋
        </button>
        <button class="ctrl-btn" onclick="loadDariusScreenshotDemo()" title="다리우스 스크린샷 3개 증강(갈라진하늘/신성한중재/발명가) 테스트">
            <i class="fa-solid fa-vial"></i> 다리우스 스샷 프리셋
        </button>
        <button class="ctrl-btn" onclick="launchNativeApp()" style="background:rgba(255,215,0,0.18);border-color:#ffd700;color:#ffd700;" title="Windows 최상위 100% 클릭 투과 네이티브 오버레이 실행">
            <i class="fa-solid fa-window-restore"></i> 🎴 투과 오버레이 팝업
        </button>
        <div style="display: flex; align-items: center; gap: 4px; font-size: 11px; color: #8b949e;">
            <i class="fa-solid fa-arrows-up-down"></i> 높이:
            <input type="range" min="1" max="30" value="8" id="heightSlider" oninput="updateHeight(this.value)" style="width: 60px; cursor: pointer;">
        </div>
    </div>

    <!-- 3개 증강 카드 상단 티어 뱃지 렌더링 컨테이너 -->
    <div class="augment-cards-container" id="cardsContainer">
        <div class="card-slot" id="slot0"></div>
        <div class="card-slot" id="slot1"></div>
        <div class="card-slot" id="slot2"></div>
    </div>

    <script>
        const API_BASE = 'http://127.0.0.1:8000';

        let currentChampion = "타릭";
        let currentChoices = ["처형 시간", "격려하기", "자연의 회복"];
        let toastTimeout = null;
        let lastAugmentHash = "";

        function showToast(msg) {
            const el = document.getElementById('toastMsg');
            if (!el) return;
            el.innerText = msg;
            el.classList.add('show');
            if (toastTimeout) clearTimeout(toastTimeout);
            toastTimeout = setTimeout(() => el.classList.remove('show'), 2800);
        }

        function updateHeight(val) {
            document.documentElement.style.setProperty('--top-pos', `${val}vh`);
            localStorage.setItem('augment_overlay_top_pos', val);
        }

        const savedTop = localStorage.getItem('augment_overlay_top_pos') || "8.5";
        document.getElementById('heightSlider').value = savedTop;
        updateHeight(savedTop);

        function changeChampionPrompt() {
            const next = prompt("시너지를 분석할 챔피언 이름을 입력하세요 (예: 타릭, 다리우스, 브라이어, 이즈리얼, 세트):", currentChampion);
            if (next && next.trim()) {
                currentChampion = next.trim();
                document.getElementById('currentChampText').innerText = currentChampion;
                evaluateCurrentAugments();
            }
        }

        async function evaluateCurrentAugments() {
            try {
                const res = await fetch(`${API_BASE}/api/lol/coach/augments/evaluate?choices=${encodeURIComponent(currentChoices.join(','))}&champion=${encodeURIComponent(currentChampion)}`);
                if (res.ok) {
                    const data = await res.json();
                    renderAugmentCards(data.augments);
                    if (data.voice_script) {
                        showToast(`👑 1순위 추천: [${data.best_augment.name_ko}] (${data.best_augment.tier}티어)`);
                    }
                }
            } catch (e) {
                console.error("평가 에러:", e);
            }
        }

        function renderAugmentCards(augments) {
            if (!augments || augments.length < 3) return;

            augments.forEach((aug, idx) => {
                const slotEl = document.getElementById(`slot${idx}`);
                if (!slotEl) return;

                const tierClass = `tier-${aug.tier.toLowerCase()}`;
                const arrowClass = `${aug.tier.toLowerCase()}-arrow`;
                const rankClass = `rank-${aug.rank_in_selection}`;

                slotEl.innerHTML = `
                    <div class="tier-card ${tierClass}">
                        <div class="tier-card-header">
                            <div class="tier-badge-pill ${aug.tier.toLowerCase()}">
                                ${aug.tier === 'OP' ? '<i class="fa-solid fa-crown"></i> 0티어 (OP)' : (aug.tier === 'S' ? '<i class="fa-solid fa-star"></i> S티어' : '<i class="fa-solid fa-award"></i> A티어')}
                            </div>
                            <div class="rank-pill ${rankClass}">${aug.pick_label}</div>
                        </div>
                        <div class="aug-name-row">
                            <span class="aug-name-text">${aug.name_ko}</span>
                            <span class="aug-rarity-badge">${aug.rarity}</span>
                        </div>
                        <div class="aug-reason-bubble">
                            <i class="fa-solid ${aug.is_best ? 'fa-bolt-lightning' : 'fa-circle-check'}" style="color:${aug.tier_color};"></i>
                            <span>${aug.champ_synergy_reason}</span>
                        </div>
                        <div class="aug-metrics-row">
                            <span class="metric-item"><i class="fa-solid fa-fire"></i> 시너지 ${aug.synergy_score}점</span>
                            <span class="metric-item"><i class="fa-solid fa-chart-line"></i> 승률 ${aug.win_rate}</span>
                            <span class="metric-item"><i class="fa-solid fa-star"></i> ${aug.is_best ? '강력 추천' : '시너지 검증'}</span>
                        </div>
                    </div>
                    <div class="pointer-arrow ${arrowClass}">
                        <i class="fa-solid fa-angles-down"></i>
                    </div>
                `;
            });
        }

        async function scanScreenVision() {
            showToast("📸 화면의 3개 증강체를 비전 AI로 스캔 중...");
            try {
                const res = await fetch(`${API_BASE}/api/lol/coach/vision/detect?champion=${encodeURIComponent(currentChampion)}`);
                if (res.ok) {
                    const data = await res.json();
                    if (data.augments && data.augments.length >= 3) {
                        currentChoices = data.augments.map(a => a.name_ko);
                        renderAugmentCards(data.augments);
                        showToast(`✅ 감지 완료: [${currentChoices.join(', ')}]`);
                    }
                }
            } catch (e) {
                showToast("스캔 실패: " + e.message);
            }
        }

        function loadTaricScreenshotDemo() {
            currentChampion = "타릭";
            document.getElementById('currentChampText').innerText = currentChampion;
            currentChoices = ["난공불락", "차원 이동", "기본으로 돌아가기"];
            evaluateCurrentAugments();
            showToast("🧪 타릭 최신 3개 증강 [난공불락, 차원 이동, 기본으로 돌아가기] 분석 완료!");
        }

        function loadDariusScreenshotDemo() {
            currentChampion = "다리우스";
            document.getElementById('currentChampText').innerText = currentChampion;
            currentChoices = ["최첨단 발명가", "신성한 중재", "갈라진 하늘 업그레이드"];
            evaluateCurrentAugments();
            showToast("🧪 다리우스 스크린샷 3개 증강 [최첨단 발명가, 신성한 중재, 갈라진 하늘] 분석 완료!");
        }

        async function launchNativeApp() {
            try {
                const res = await fetch(`${API_BASE}/api/lol/overlay/augments/launch_native`, { method: 'POST' });
                if (res.ok) {
                    showToast("🎴 Windows 최상위 투명 오버레이가 실행되었습니다!");
                }
            } catch (e) {
                showToast("실행 요청 에러");
            }
        }

        window.addEventListener('keydown', (e) => {
            if (e.key === 'F1' || e.key === 'f1') {
                e.preventDefault();
                scanScreenVision();
            }
        });

        // 실시간 백엔드 오버레이 상태 자동 폴링 (400ms 주기)
        async function pollLiveAugmentState() {
            try {
                const res = await fetch(`${API_BASE}/api/lol/coach/augments/overlay_state`);
                if (res.ok) {
                    const data = await res.json();
                    if (data.augments && data.augments.length >= 3) {
                        const hash = data.augments.map(a => a.name_ko).join('_') + '_' + data.champion;
                        if (hash !== lastAugmentHash) {
                            lastAugmentHash = hash;
                            currentChampion = data.champion || currentChampion;
                            document.getElementById('currentChampText').innerText = currentChampion;
                            renderAugmentCards(data.augments);
                        }
                    }
                }
            } catch (e) {}
        }

        setInterval(pollLiveAugmentState, 400);
        loadTaricScreenshotDemo();
    </script>
</body>
</html>"""


# =============================================================================
# 🎨 3. 사이버틱 반투명 플로팅 올인원 오버레이 HTML 템플릿 (/overlay)
# =============================================================================
OVERLAY_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>JARVIS LoL Tactical Master HUD</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; user-select: none; }
        body {
            background: transparent;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Malgun Gothic", sans-serif;
            color: #fff;
            overflow: hidden;
            width: 100vw;
            height: 100vh;
            display: flex;
            justify-content: flex-end;
            align-items: flex-end;
            padding: 16px;
        }

        .hud-card {
            width: 360px;
            max-height: 480px;
            background: rgba(10, 15, 26, 0.90);
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            border: 1px solid rgba(0, 229, 255, 0.4);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.75), 0 0 18px rgba(0, 229, 255, 0.2);
            border-radius: 12px;
            padding: 12px;
            font-size: 12px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            opacity: 1;
            transform: translateY(0) scale(1);
            transition: opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1), 
                        transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), 
                        box-shadow 0.3s ease;
        }

        .hud-card.hidden-unfocused {
            opacity: 0;
            pointer-events: none;
            transform: translateY(14px) scale(0.95);
        }

        .hud-card.critical {
            border-color: #ff1744;
            box-shadow: 0 0 25px rgba(255, 23, 68, 0.6);
            animation: pulse-border 1.2s infinite alternate;
        }

        @keyframes pulse-border {
            from { border-color: rgba(255, 23, 68, 0.4); }
            to { border-color: rgba(255, 23, 68, 1); box-shadow: 0 0 30px rgba(255, 23, 68, 0.9); }
        }

        .hud-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            padding-bottom: 6px;
        }

        .hud-title {
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.8px;
            color: #00e5ff;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .hud-meta-group {
            display: flex;
            gap: 5px;
            align-items: center;
        }

        .badge-focus {
            background: rgba(0, 229, 255, 0.12);
            color: #00e5ff;
            border: 1px solid rgba(0, 229, 255, 0.35);
            border-radius: 12px;
            font-size: 10px;
            padding: 2px 7px;
            font-weight: 700;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 4px;
            transition: all 0.2s ease;
        }

        .badge-focus.active {
            background: rgba(0, 255, 136, 0.2);
            color: #00ff88;
            border-color: rgba(0, 255, 136, 0.5);
            box-shadow: 0 0 8px rgba(0, 255, 136, 0.3);
        }

        .badge-focus.wait {
            background: rgba(255, 153, 0, 0.15);
            color: #ffb74d;
            border-color: rgba(255, 153, 0, 0.4);
        }

        .badge-focus.off {
            background: rgba(255, 255, 255, 0.08);
            color: #8b949e;
            border-color: rgba(255, 255, 255, 0.2);
        }

        .badge-live {
            background: rgba(0, 255, 136, 0.18);
            color: #00ff88;
            border: 1px solid rgba(0, 255, 136, 0.4);
            border-radius: 12px;
            font-size: 10px;
            padding: 2px 6px;
            font-weight: 700;
        }

        .badge-gold {
            background: rgba(255, 215, 0, 0.15);
            color: #ffd700;
            border: 1px solid rgba(255, 215, 0, 0.4);
            border-radius: 12px;
            font-size: 10px;
            padding: 2px 6px;
            font-weight: 700;
        }

        .focus-standby-pill {
            position: fixed;
            bottom: 16px;
            right: 16px;
            background: rgba(10, 15, 26, 0.85);
            border: 1px solid rgba(0, 229, 255, 0.4);
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.6), 0 0 10px rgba(0, 229, 255, 0.2);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 5px 12px;
            font-size: 11px;
            color: #8b949e;
            cursor: pointer;
            display: none;
            align-items: center;
            gap: 6px;
            z-index: 9999;
            font-weight: 600;
        }

        .tab-bar {
            display: flex;
            gap: 4px;
            background: rgba(255,255,255,0.05);
            padding: 3px;
            border-radius: 6px;
        }

        .tab-btn {
            flex: 1;
            background: transparent;
            border: none;
            color: #8b949e;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 0;
            border-radius: 4px;
            cursor: pointer;
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 4px;
        }

        .tab-btn.active {
            background: #00e5ff;
            color: #050811;
            box-shadow: 0 0 10px rgba(0, 229, 255, 0.4);
        }

        .tab-content {
            display: none;
            flex-direction: column;
            gap: 8px;
        }

        .tab-content.active {
            display: flex;
        }

        .radar-body {
            display: grid;
            grid-template-columns: 100px 1fr;
            gap: 10px;
            align-items: center;
        }

        .radar-img-box {
            width: 100px;
            height: 100px;
            border-radius: 8px;
            border: 1px solid rgba(0, 229, 255, 0.3);
            background: #050811;
            overflow: hidden;
        }

        .radar-img-box img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        .stats-col {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }

        .stat-badge {
            display: flex;
            justify-content: space-between;
            padding: 3px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
        }

        .badge-enemy {
            background: rgba(255, 23, 68, 0.15);
            border: 1px solid rgba(255, 23, 68, 0.35);
            color: #ff5252;
        }

        .badge-ally {
            background: rgba(0, 229, 255, 0.15);
            border: 1px solid rgba(0, 229, 255, 0.35);
            color: #00e5ff;
        }

        .eta-banner {
            background: rgba(255, 153, 0, 0.2);
            border-left: 3px solid #ff9900;
            border-radius: 4px;
            padding: 6px 8px;
            font-size: 11px;
            display: none;
            color: #ffb74d;
        }

        .eta-banner.active {
            display: block;
        }

        .spell-list {
            display: flex;
            flex-direction: column;
            gap: 4px;
            max-height: 160px;
            overflow-y: auto;
        }

        .spell-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 6px;
            padding: 4px 8px;
        }

        .champ-info {
            font-weight: 700;
            font-size: 11px;
            color: #e6edf3;
            width: 80px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .spell-btn {
            background: rgba(0, 229, 255, 0.12);
            border: 1px solid rgba(0, 229, 255, 0.35);
            color: #00e5ff;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: 700;
            cursor: pointer;
        }

        .spell-btn.on-cd {
            background: rgba(255, 23, 68, 0.2);
            border-color: rgba(255, 23, 68, 0.5);
            color: #ff5252;
        }

        .obj-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 6px;
        }

        .obj-card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 6px;
            padding: 6px;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .obj-name {
            font-size: 10px;
            color: #8b949e;
            display: flex;
            align-items: center;
            gap: 4px;
        }

        .obj-timer {
            font-size: 13px;
            font-weight: 800;
            color: #00ff88;
        }

        /* 탭 4: 증강체 전용 뷰 */
        .aug-box {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .aug-live-preview {
            background: rgba(0, 229, 255, 0.08);
            border: 1px solid rgba(0, 229, 255, 0.35);
            border-radius: 8px;
            padding: 8px;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .aug-preview-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11px;
            padding: 3px 0;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }

        .aug-btn-launch {
            background: linear-gradient(135deg, #ffd700, #ff9100);
            color: #050811;
            border: none;
            padding: 6px 10px;
            font-weight: 800;
            border-radius: 6px;
            cursor: pointer;
            font-size: 11px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 5px;
            text-decoration: none;
        }

        .alert-banner {
            font-size: 11px;
            color: #ff8a80;
            background: rgba(0,0,0,0.5);
            border-radius: 4px;
            padding: 4px 8px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
    </style>
</head>
<body>
    <div id="focusStandbyPill" class="focus-standby-pill" onclick="revealFromStandby()">
        <i class="fa-solid fa-bullseye" style="color:#00e5ff;"></i> 
        <span id="standbyText">롤 포커스 대기 중</span>
    </div>

    <div id="hudCard" class="hud-card">
        <div class="hud-header">
            <div class="hud-title">
                <i class="fa-solid fa-crosshairs"></i> <span id="modeTitle">SUMMONER'S RIFT</span>
            </div>
            <div class="hud-meta-group">
                <span id="focusBadge" class="badge-focus active" onclick="toggleFocusMode()">
                    <i class="fa-solid fa-bullseye"></i> 롤 포커스 ON
                </span>
                <div id="gameTimeBadge" class="badge-live">00:00</div>
                <div id="goldDiffBadge" class="badge-gold">0G Lead</div>
                <div id="fpsBadge" class="badge-live">0.0ms</div>
            </div>
        </div>

        <div class="tab-bar">
            <button class="tab-btn active" onclick="switchTab('tabRadar', this)"><i class="fa-solid fa-radar"></i> 레이더</button>
            <button class="tab-btn" onclick="switchTab('tabSpells', this)"><i class="fa-solid fa-bolt"></i> 스펠(5)</button>
            <button class="tab-btn" onclick="switchTab('tabObjectives', this)"><i class="fa-solid fa-dragon"></i> 오브젝트</button>
            <button class="tab-btn" onclick="switchTab('tabAugments', this)"><i class="fa-solid fa-dice-d20"></i> 증강체</button>
        </div>

        <div id="tabRadar" class="tab-content active">
            <div class="radar-body">
                <div class="radar-img-box"><img id="radarImg" src="" alt="Minimap"></div>
                <div class="stats-col">
                    <div class="stat-badge badge-enemy"><span>적 챔피언</span><span id="enemyCount">0</span></div>
                    <div class="stat-badge badge-ally"><span>아군</span><span id="allyCount">0</span></div>
                    <div id="csGauge" style="font-size: 10px; color: #ffd700; font-weight: 700;">CS/m: 0.0</div>
                    <div id="zoneText" style="font-size: 10px; color: #8b949e;">감시 대기 중</div>
                </div>
            </div>
            <div id="etaBanner" class="eta-banner">
                <i class="fa-solid fa-person-running"></i> <strong id="etaTarget">미드</strong> 갱킹 위험! (<span id="etaTime">8</span>s)
            </div>
        </div>

        <div id="tabSpells" class="tab-content">
            <div id="spellList" class="spell-list">
                <div style="font-size: 10px; color: #8b949e; text-align: center; padding: 10px;">적 챔피언 스펠 로딩 대기 중...</div>
            </div>
        </div>

        <div id="tabObjectives" class="tab-content">
            <div class="obj-grid">
                <div class="obj-card"><div class="obj-name"><i class="fa-solid fa-dragon" style="color:#00e5ff;"></i> 드래곤</div><div id="timerDragon" class="obj-timer">대기 중</div></div>
                <div class="obj-card"><div class="obj-name"><i class="fa-solid fa-skull-crossbones" style="color:#b388ff;"></i> 바론</div><div id="timerBaron" class="obj-timer">대기 중</div></div>
                <div class="obj-card"><div class="obj-name"><i class="fa-solid fa-bug" style="color:#ff80ab;"></i> 유충</div><div id="timerGrubs" class="obj-timer">대기 중</div></div>
                <div class="obj-card"><div class="obj-name"><i class="fa-solid fa-shield-halved" style="color:#ffd700;"></i> 전령</div><div id="timerHerald" class="obj-timer">대기 중</div></div>
            </div>
        </div>

        <div id="tabAugments" class="tab-content">
            <div class="aug-box">
                <div class="aug-live-preview">
                    <div style="font-weight: 800; color: #00e5ff; display: flex; justify-content: space-between;">
                        <span>🎴 인게임 3지선다 실시간 티어</span>
                        <span id="augChampBadge" style="color: #ffd700; font-size: 10px;">다리우스</span>
                    </div>
                    <div id="augPreviewList">
                        <div class="aug-preview-item"><span>👑 갈라진 하늘 업글</span><span style="color:#ffd700;font-weight:bold;">0티어 OP (#1)</span></div>
                        <div class="aug-preview-item"><span>⭐ 신성한 중재</span><span style="color:#00e5ff;font-weight:bold;">S티어 (#2)</span></div>
                        <div class="aug-preview-item"><span>🥇 최첨단 발명가</span><span style="color:#00ff88;font-weight:bold;">A티어 (#3)</span></div>
                    </div>
                </div>
                <a href="/overlay/augments" target="_blank" class="aug-btn-launch">
                    <i class="fa-solid fa-arrow-up-right-from-square"></i> 인게임 카드 상단 실시간 오버레이 실행
                </a>
            </div>
        </div>

        <div id="alertBanner" class="alert-banner">
            <i class="fa-solid fa-circle-info"></i> 전술 위협 없음
        </div>
    </div>

    <script>
        const API_BASE = 'http://127.0.0.1:8000';

        let focusModeEnabled = localStorage.getItem('lol_overlay_focus_mode') !== 'false';
        let isMouseHovered = false;
        let isLolForeground = false;
        let isLolRunning = false;

        document.addEventListener('mouseenter', () => { isMouseHovered = true; updateVisibility(); });
        document.addEventListener('mouseleave', () => { isMouseHovered = false; updateVisibility(); });
        window.addEventListener('focus', () => { updateVisibility(); });
        window.addEventListener('blur', () => { updateVisibility(); });

        function toggleFocusMode() {
            focusModeEnabled = !focusModeEnabled;
            localStorage.setItem('lol_overlay_focus_mode', focusModeEnabled ? 'true' : 'false');
            updateVisibility();
        }

        function revealFromStandby() {
            isMouseHovered = true;
            updateVisibility();
        }

        function updateVisibility() {
            const hudCard = document.getElementById('hudCard');
            const standbyPill = document.getElementById('focusStandbyPill');
            const focusBadge = document.getElementById('focusBadge');
            const overlayInteracting = document.hasFocus() || isMouseHovered;

            if (!focusModeEnabled) {
                hudCard.classList.remove('hidden-unfocused');
                if (standbyPill) standbyPill.style.display = 'none';
                if (focusBadge) {
                    focusBadge.className = 'badge-focus off';
                    focusBadge.innerHTML = '<i class="fa-solid fa-eye"></i> 항상 표시';
                }
                return;
            }

            if (isLolForeground || overlayInteracting) {
                hudCard.classList.remove('hidden-unfocused');
                if (standbyPill) standbyPill.style.display = 'none';
                if (focusBadge) {
                    focusBadge.className = 'badge-focus active';
                    focusBadge.innerHTML = '<i class="fa-solid fa-crosshairs"></i> 롤 포커스 ON';
                }
            } else {
                hudCard.classList.add('hidden-unfocused');
                if (standbyPill) {
                    standbyPill.style.display = 'flex';
                }
                if (focusBadge) {
                    focusBadge.className = 'badge-focus wait';
                    focusBadge.innerHTML = '<i class="fa-solid fa-bullseye"></i> 롤 대기';
                }
            }
        }

        function switchTab(tabId, btn) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            btn.classList.add('active');
        }

        async function triggerSpell(champName, spellKey) {
            try {
                await fetch(`${API_BASE}/api/lol/live/spell/use`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ champion_name: champName, spell_name: spellKey })
                });
                pollOverlayData();
            } catch(e) {}
        }

        function formatSec(sec) {
            if (sec <= 0) return '출현 완료';
            const m = Math.floor(sec / 60);
            const s = sec % 60;
            return `${m}:${s < 10 ? '0' : ''}${s}`;
        }

        async function pollOverlayData() {
            try {
                const statusRes = await fetch(`${API_BASE}/api/lol/overlay/status`);
                if (statusRes.ok) {
                    const st = await statusRes.json();
                    isLolForeground = !!st.is_lol_foreground;
                    isLolRunning = !!st.is_lol_running;
                    updateVisibility();
                }

                const res = await fetch(`${API_BASE}/api/lol/minimap/status`);
                if (res.ok) {
                    const data = await res.json();
                    if (data.debug_image_b64) {
                        document.getElementById('radarImg').src = `data:image/jpeg;base64,${data.debug_image_b64}`;
                    }
                    document.getElementById('enemyCount').innerText = `${data.last_enemies.length}`;
                    document.getElementById('allyCount').innerText = `${data.last_allies.length}`;
                    document.getElementById('fpsBadge').innerText = `${data.latency_ms}ms`;
                }

                const liveRes = await fetch(`${API_BASE}/api/lol/live/status`);
                if (liveRes.ok) {
                    const live = await liveRes.json();
                    if (live.in_game) {
                        document.getElementById('gameTimeBadge').innerText = live.game_time_str;
                        document.getElementById('modeTitle').innerText = live.map_name.toUpperCase();
                        const gDiff = live.gold_diff;
                        document.getElementById('goldDiffBadge').innerText = gDiff >= 0 ? `+${(gDiff/1000).toFixed(1)}k Lead` : `${(gDiff/1000).toFixed(1)}k Deficit`;
                        document.getElementById('csGauge').innerText = `CS/m: ${live.my_cs_per_min}`;
                    }
                }
            } catch (e) {}
        }

        setInterval(pollOverlayData, 300);
        updateVisibility();
        pollOverlayData();
    </script>
</body>
</html>
"""


# =============================================================================
# 🌐 4. REST API 엔드포인트
# =============================================================================
@router.get("/overlay", summary="실시간 인게임 반투명 플로팅 올인원 HUD", response_class=HTMLResponse)
def serve_overlay_hud():
    """브라우저, OBS, 데스크탑 오버레이로 띄울 수 있는 플로팅 올인원 HUD"""
    return HTMLResponse(content=OVERLAY_HTML, status_code=200)


@router.get("/overlay/augments", summary="3개 증강 카드 상단 실시간 티어 전용 오버레이", response_class=HTMLResponse)
def serve_augment_overlay():
    """
    롤 인게임 3개 증강 카드 바로 윗부분에 1:1 티어(OP/S/A/B/C) 및 순위 뱃지를 띄우는
    전체화면 투명 오버레이를 반환합니다.
    """
    return HTMLResponse(content=AUGMENT_OVERLAY_HTML, status_code=200)


@router.get("/api/lol/overlay/status", summary="플로팅 오버레이 HUD 상태 및 롤 포커스 상태 조회")
def get_overlay_status():
    """오버레이 동작 상태 및 현재 롤 창(게임/클라이언트) 활성화(포커스) 여부 반환"""
    try:
        from modules.lol_minimap_tracker import is_lol_foreground_active, is_lol_ingame_active, minimap_tracker
        is_fg = is_lol_foreground_active(include_client_lobby=True)
        is_act = is_lol_ingame_active()
        focus_filter = minimap_tracker.focus_filter_enabled
    except Exception:
        is_fg = False
        is_act = False
        focus_filter = True

    return {
        "status": "online",
        "url": "http://127.0.0.1:8000/overlay",
        "is_lol_foreground": is_fg,
        "is_lol_active": is_act,
        "is_lol_running": is_act or is_fg,
        "focus_filter_enabled": focus_filter
    }


@router.get("/api/lol/overlay/augments/launch", summary="증강체 전용 실시간 오버레이 창 팝업 실행 (GET)")
@router.post("/api/lol/overlay/augments/launch", summary="증강체 전용 실시간 오버레이 창 팝업 실행 (POST)")
def launch_augment_overlay():
    """
    Windows 엣지/크롬 브라우저를 전체화면 투명 앱 모드로 실행하여
    롤 화면 3개 증강체 카드 바로 위에 티어 뱃지를 실시간 오버레이합니다.
    """
    try:
        url = "http://localhost:8000/overlay/augments"
        cmd = f'start msedge --app="{url}" --window-size=1920,1080 --window-position=0,0'
        subprocess.Popen(cmd, shell=True)
        return {"status": "success", "message": "증강체 상단 실시간 티어 오버레이가 실행되었습니다."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/api/lol/overlay/launch", summary="데스크탑 플로팅 올인원 HUD 실행 (GET)")
@router.post("/api/lol/overlay/launch", summary="데스크탑 플로팅 올인원 HUD 실행 (POST)")
def launch_desktop_overlay():
    try:
        url = "http://localhost:8000/overlay"
        cmd = f'start msedge --app="{url}" --window-size=380,480 --window-position=1520,560'
        subprocess.Popen(cmd, shell=True)
        return {"status": "success", "message": "인게임 올인원 플로팅 오버레이 창이 실행되었습니다."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/api/lol/overlay/toggle", summary="오버레이 토글 (GET)")
@router.post("/api/lol/overlay/toggle", summary="오버레이 토글 (POST)")
def toggle_overlay():
    return launch_desktop_overlay()
