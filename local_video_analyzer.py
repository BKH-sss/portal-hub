"""
local_video_analyzer.py
------------------------------------------------------------
자막 텍스트뿐 아니라 영상 "화면"을 로컬 VLM(Qwen3-VL 등, Ollama)으로 직접 보고
이해한 요약을 만드는 모듈. Gemini/클라우드 API 없이 100% 로컬로 동작합니다.

사전 준비 (사용자 PC에서 1회):
    ollama pull qwen3-vl:8b      # VRAM 8GB 기준. 4GB면 qwen3-vl:2b, 여유되면 :32b
    pip install yt-dlp
    (ffmpeg, ffprobe가 PATH에 있어야 합니다 - SD/GPT-SoVITS 세팅에 보통 이미 있을 겁니다)

동작 방식:
    영상 다운로드 -> 균등 간격 프레임 6장 추출 -> 각 프레임을 VLM에게 보여주고
    "화면에 뭐가 보이는지" 설명 받기 -> 자막(청각 정보) + 프레임 설명(시각 정보)을
    로컬 LLM으로 하나의 요약으로 융합.

    ffmpeg로 프레임을 직접 뽑는 방식을 쓴 이유: Ollama의 "영상 직접 입력" 지원은
    모델/버전마다 아직 들쭉날쭉합니다. 프레임 추출 방식은 어떤 VLM으로 바꿔도
    항상 동작하는 가장 안전한 방법이라 이걸 기본으로 잡았습니다.

사용법 (brain_server.py에서):
    from local_video_analyzer import analyze_video_visually
    result = analyze_video_visually(video_url, transcript_text, title="영상제목")
    # result = {"visual_summary": "...", "fused_summary": "..."}
"""
import os
import subprocess
import tempfile
import shutil

from ollama_utils import ollama_chat_with_images, ollama_generate

VLM_MODEL = "qwen3-vl:8b"   # 4080 Super(16GB)엔 충분히 들어감. 한글 OCR 강점 때문에 유지 권장
                             # (gemma4:12b도 비전 지원하니 A/B 테스트 후 취향껏 교체 가능)
FRAME_COUNT = 6              # 영상 전체에서 균등 간격으로 뽑을 프레임 수
MAX_VIDEO_SECONDS_DOWNLOAD_TIMEOUT = 300


def download_video(url: str, out_dir: str) -> str | None:
    """yt-dlp로 720p 이하 화질로 영상을 다운로드. 실패하면 None."""
    out_path = os.path.join(out_dir, "video.mp4")
    cmd = ["yt-dlp", "-f", "best[height<=720]", "-o", out_path, url]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=MAX_VIDEO_SECONDS_DOWNLOAD_TIMEOUT)
        return out_path if os.path.exists(out_path) else None
    except Exception as e:
        print(f"[local_video_analyzer] 다운로드 실패: {e}")
        return None


def _get_duration(video_path: str) -> float:
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, timeout=30,
        )
        return float(probe.stdout.strip())
    except Exception:
        return 60.0  # 조회 실패 시 기본값


def extract_frames(video_path: str, out_dir: str, count: int = FRAME_COUNT) -> list[str]:
    """ffmpeg로 영상 전체 길이에서 균등 간격 프레임을 추출."""
    duration = _get_duration(video_path)
    interval = max(duration / (count + 1), 1)

    frame_paths = []
    for i in range(1, count + 1):
        t = interval * i
        frame_path = os.path.join(out_dir, f"frame_{i}.jpg")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-ss", str(t), "-i", video_path,
                 "-frames:v", "1", "-q:v", "2", frame_path],
                capture_output=True, timeout=30,
            )
            if os.path.exists(frame_path):
                frame_paths.append(frame_path)
        except Exception as e:
            print(f"[local_video_analyzer] 프레임 추출 실패 ({t:.0f}s): {e}")
    return frame_paths


def describe_frames(frame_paths: list[str], context_hint: str = "") -> list[str]:
    """각 프레임을 VLM에게 보여주고 화면 설명을 받는다."""
    descriptions = []
    prompt = (
        "이 이미지는 게임 공략 유튜브 영상의 한 장면이다. "
        "화면에 보이는 게임 정보(챔피언, 아이템, 스킬, 맵 위치, 텍스트/UI 등)를 "
        "한국어로 2~3문장으로 구체적으로 설명해라. 추측하지 말고 실제로 보이는 것만 말해라."
        + (f"\n참고 맥락(영상 제목): {context_hint}" if context_hint else "")
    )
    for path in frame_paths:
        desc = ollama_chat_with_images(prompt, image_paths=[path], model=VLM_MODEL, num_predict=250)
        if desc:
            descriptions.append(desc)
    return descriptions


def fuse_transcript_and_visuals(transcript: str, visual_descriptions: list[str], title: str) -> str:
    """자막(청각 정보)과 프레임 설명(시각 정보)을 하나의 요약으로 융합."""
    visuals_text = "\n".join(f"- {d}" for d in visual_descriptions) if visual_descriptions else "(시각 정보 없음)"
    prompt = f"""다음은 같은 영상('{title}')에서 나온 두 종류의 정보다.

[음성 자막 내용]
{transcript[:3000]}

[화면에서 관찰된 시각 정보 (시간순)]
{visuals_text}

두 정보를 종합해서, 이 영상이 실제로 무엇을 보여주고 설명하는지 한국어로 5~8문장으로 요약해라.
자막에는 없지만 화면에서 확인된 사실(예: 실제 아이템 배치, 스킬 순서, 화면에 표시된 수치)이
있다면 반드시 포함해라. 화면 정보와 자막 정보가 서로 다르면 그 사실도 언급해라.
"""
    return ollama_generate(prompt, model="gemma4:12b", temperature=0.2, num_predict=800)


def analyze_video_visually(video_url: str, transcript: str, title: str = "") -> dict:
    """
    영상 다운로드 -> 프레임 추출 -> VLM 화면 분석 -> 자막과 융합, 전 과정을 한 번에 실행.
    어느 단계에서 실패하든 예외를 던지지 않고 안전하게 축소된 결과를 반환합니다
    (기존 파이프라인이 이 단계 때문에 죽지 않도록).
    """
    tmp_dir = tempfile.mkdtemp(prefix="video_analysis_")
    try:
        video_path = download_video(video_url, tmp_dir)
        if not video_path:
            return {"visual_summary": "", "fused_summary": transcript[:500], "visual_ok": False}

        frames = extract_frames(video_path, tmp_dir)
        if not frames:
            return {"visual_summary": "", "fused_summary": transcript[:500], "visual_ok": False}

        descriptions = describe_frames(frames, context_hint=title)
        if not descriptions:
            return {"visual_summary": "", "fused_summary": transcript[:500], "visual_ok": False}

        fused = fuse_transcript_and_visuals(transcript, descriptions, title)
        return {"visual_summary": "\n".join(descriptions), "fused_summary": fused, "visual_ok": True}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
