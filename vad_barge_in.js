/**
 * vad_barge_in.js
 * ----------------
 * Open-LLM-VTuber 스타일의 "바지인(Barge-in)" 기능: AI가 TTS로 말하는 도중에
 * 유저가 마이크에 대고 말을 시작하면 즉시 AI 음성을 끊고 새 입력을 받습니다.
 *
 * 외부 라이브러리 없이 Web Audio API의 AnalyserNode로 에너지 기반 VAD를 구현합니다.
 * (Silero-VAD WASM 같은 정교한 모델보다는 단순하지만, 의존성이 없고 지연이 거의 없습니다.
 *  나중에 정확도를 높이고 싶다면 @ricky0123/vad-web 같은 라이브러리로 교체 가능한 구조로 짰습니다.)
 *
 * chatbot.html에 추가하는 법:
 *   <script src="vad_barge_in.js"></script>
 *   그리고 마이크 권한을 얻은 뒤 (또는 init() 안에서) 아래처럼 한 번 호출:
 *       initVadBargeIn({
 *           onBargeIn: () => stopCurrentAudio(),          // 기존 함수 재사용
 *           onSpeechEnd: async (audioBlob) => {
 *               const text = await transcribeWithLocalASR(audioBlob); // local_asr.py 연동
 *               if (text && text.trim()) {
 *                   messageInput.value = text;
 *                   sendMessage();
 *               }
 *           }
 *       });
 *
 * 필요조건: 이 모듈이 참조하는 window.isAudioPlaying (chatbot.html에 이미 존재하는 전역 변수)
 */

(function () {
    let audioContext = null;
    let analyser = null;
    let mediaStream = null;
    let mediaRecorder = null;
    let recordedChunks = [];
    let vadIntervalId = null;

    // --- 튜닝 가능한 파라미터 ---
    const ENERGY_THRESHOLD = 0.02;      // 이 값보다 크면 "말하는 중"으로 판정 (환경 소음에 맞춰 조절)
    const SPEECH_HOLD_MS = 250;         // 이 시간(ms) 이상 연속으로 음성이 감지되면 확정 발화로 인정
    const SILENCE_HOLD_MS = 800;        // 이 시간(ms) 이상 조용하면 발화 종료로 판정하고 녹음 종료
    const POLL_INTERVAL_MS = 50;

    let speechStartedAt = null;
    let lastVoiceAt = null;
    let isSpeaking = false;

    async function initVadBargeIn(handlers) {
        const { onBargeIn, onSpeechStart, onSpeechEnd } = handlers || {};

        try {
            mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch (e) {
            console.warn('[VAD] 마이크 권한을 얻지 못했습니다. 바지인 기능이 비활성화됩니다.', e);
            return false;
        }

        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioContext.createMediaStreamSource(mediaStream);
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 512;
        source.connect(analyser);

        const dataArray = new Uint8Array(analyser.frequencyBinCount);

        // MediaRecorder는 발화가 확정된 시점부터 시작 (매번 새로 만듦)
        function startRecording() {
            recordedChunks = [];
            try {
                mediaRecorder = new MediaRecorder(mediaStream, { mimeType: 'audio/webm' });
            } catch (e) {
                mediaRecorder = new MediaRecorder(mediaStream);
            }
            mediaRecorder.ondataavailable = (e) => {
                if (e.data && e.data.size > 0) recordedChunks.push(e.data);
            };
            mediaRecorder.start();
        }

        function stopRecordingAndEmit() {
            if (!mediaRecorder || mediaRecorder.state === 'inactive') return;
            mediaRecorder.onstop = () => {
                const blob = new Blob(recordedChunks, { type: 'audio/webm' });
                recordedChunks = [];
                if (blob.size > 1000 && onSpeechEnd) { // 너무 짧은 노이즈는 무시
                    onSpeechEnd(blob);
                }
            };
            mediaRecorder.stop();
        }

        function computeRmsEnergy() {
            analyser.getByteTimeDomainData(dataArray);
            let sumSquares = 0;
            for (let i = 0; i < dataArray.length; i++) {
                const normalized = (dataArray[i] - 128) / 128;
                sumSquares += normalized * normalized;
            }
            return Math.sqrt(sumSquares / dataArray.length);
        }

        vadIntervalId = setInterval(() => {
            const energy = computeRmsEnergy();
            const now = Date.now();
            const voiceDetected = energy > ENERGY_THRESHOLD;

            if (voiceDetected) {
                lastVoiceAt = now;
                if (speechStartedAt === null) {
                    speechStartedAt = now;
                }
                const heldLongEnough = now - speechStartedAt >= SPEECH_HOLD_MS;

                if (heldLongEnough && !isSpeaking) {
                    isSpeaking = true;

                    // AI가 말하는 중이었다면 즉시 끊기 (바지인의 핵심)
                    if (window.isAudioPlaying && onBargeIn) {
                        console.log('[VAD] 바지인 감지! AI 음성을 중단합니다.');
                        onBargeIn();
                    }
                    if (onSpeechStart) onSpeechStart();
                    startRecording();
                }
            } else {
                // 침묵 감지 - 발화 중이었다면 종료 판정
                if (isSpeaking && lastVoiceAt !== null && now - lastVoiceAt >= SILENCE_HOLD_MS) {
                    isSpeaking = false;
                    speechStartedAt = null;
                    stopRecordingAndEmit();
                }
                if (!isSpeaking) {
                    speechStartedAt = null;
                }
            }
        }, POLL_INTERVAL_MS);

        console.log('[VAD] 바지인 감지가 활성화되었습니다.');
        return true;
    }

    function stopVadBargeIn() {
        if (vadIntervalId) clearInterval(vadIntervalId);
        if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
        if (mediaStream) mediaStream.getTracks().forEach((t) => t.stop());
        if (audioContext) audioContext.close();
        vadIntervalId = null;
    }

    // local_asr.py 연동 헬퍼 (선택 사용)
    async function transcribeWithLocalASR(audioBlob, serverUrl) {
        const base = serverUrl || (window.SERVER_URL || window.location.origin);
        const formData = new FormData();
        formData.append('file', audioBlob, 'recording.webm');
        const res = await fetch(`${base}/api/asr?language=ko`, { method: 'POST', body: formData });
        if (!res.ok) {
            console.error('[VAD] 로컬 ASR 호출 실패:', await res.text());
            return '';
        }
        const data = await res.json();
        return data.text || '';
    }

    window.initVadBargeIn = initVadBargeIn;
    window.stopVadBargeIn = stopVadBargeIn;
    window.transcribeWithLocalASR = transcribeWithLocalASR;
})();
