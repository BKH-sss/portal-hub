import time
import datetime
import os
import sys
from mss import mss
from PIL import Image, ImageGrab
import io
import cv2
import numpy as np

# YOLOv8 초기화 (최초 실행 시 yolov8n.pt를 다운로드할 수 있습니다)
try:
    from ultralytics import YOLO
    # 추후 롤 전용 모델(best.pt 등)으로 교체 시 이 부분을 수정하면 됩니다.
    model = YOLO('yolov8n.pt') 
except ImportError:
    print("ultralytics 패키지가 설치되지 않았습니다. pip install ultralytics 명령어로 설치해주세요.")
    exit(1)

MEMORY_DIR = "B:\\AI_Brain"
SESSION_LOG_PATH = os.path.join(MEMORY_DIR, "game_session.log")

# B드라이브 경로가 없다면 폴더 생성
if not os.path.exists(MEMORY_DIR):
    os.makedirs(MEMORY_DIR, exist_ok=True)

def capture_screen():
    try:
        with mss() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            sct_img = sct.grab(monitor)
            # mss는 BGRA를 반환하므로 RGB로 변환
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
    except Exception as e:
        print(f"mss 캡처 실패 ({e}), ImageGrab으로 재시도합니다.")
        img = ImageGrab.grab()
    
    return img

def main():
    summoner_name = sys.argv[1] if len(sys.argv) > 1 else "Unknown"
    game_mode = sys.argv[2] if len(sys.argv) > 2 else "Unknown"
    champion = sys.argv[3] if len(sys.argv) > 3 else "Unknown"

    def safe_filename(name):
        return "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()

    safe_summoner = safe_filename(summoner_name)
    safe_mode = safe_filename(game_mode)
    safe_champ = safe_filename(champion)
    
    replays_dir = os.path.join(MEMORY_DIR, "replays")
    os.makedirs(replays_dir, exist_ok=True)
    
    date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    video_filename = f"[{safe_mode}]_[{safe_champ}]_[{safe_summoner}]_{date_str}.mp4"
    video_path = os.path.join(replays_dir, video_filename)
    
    video_writer = None
    fps = 10.0

    print("========================================")
    print("초고속 비전 에이전트(YOLOv8 Agent) 시작...")
    print(f"녹화 대상: {summoner_name} | {game_mode} | {champion}")
    print(f"저장 경로: {video_path}")
    print("========================================")
    print("리그오브레전드(LoL) 화면을 실시간(약 0.1초 반응)으로 캡처하여 사물을 인식 및 녹화합니다.\n")
    
    with open(SESSION_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n\n--- 새로운 리그오브레전드 세션 시작 (YOLOv8 Mode): {datetime.datetime.now()} ---\n")
        f.write(f"플레이어: {summoner_name}, 모드: {game_mode}, 챔피언: {champion}\n")
        
    while True:
        try:
            start_time = time.time()
            now_str = datetime.datetime.now().strftime("%H:%M:%S")
            
            # 1. 화면 캡처
            img = capture_screen()
            
            # 1.5. 비디오 라이터 초기화 및 프레임 쓰기
            frame_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            if video_writer is None:
                height, width, _ = frame_bgr.shape
                fourcc = cv2.VideoWriter_fourcc(*'mp4v') # mp4 포맷 코덱
                video_writer = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
            
            video_writer.write(frame_bgr)
            
            # 2. YOLO 추론 (verbose=False로 콘솔 로그 최소화)
            results = model.predict(source=img, verbose=False, conf=0.5)
            
            # 3. 결과 분석
            detected_items = []
            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    label = model.names[cls_id]
                    detected_items.append(f"{label}({conf:.2f})")
            
            elapsed = time.time() - start_time
            
            # 너무 많이 로깅되는 것을 방지하기 위해 결과가 있을 때만
            if detected_items:
                summary = ", ".join(detected_items)
                log_msg = f"[{now_str}] 0.1초 인식 결과 ({elapsed:.3f}s 소요): {summary}"
                print(log_msg)
                # 로그 파일 기록 (기본 COCO 모델 사용 시 TV, 식물 등 오인식 데이터가 LLM을 오염시키므로 로깅 중단)
                # with open(SESSION_LOG_PATH, "a", encoding="utf-8") as f:
                #     f.write(log_msg + "\n")
                
            # CPU/GPU 과부하 방지를 위해 최대 초당 10프레임 속도로 제한
            sleep_time = max(0.0, 0.1 - elapsed)
            time.sleep(sleep_time)
            
        except KeyboardInterrupt:
            print("\nYOLOv8 비전 에이전트를 종료합니다.")
            if video_writer is not None:
                video_writer.release()
            break
        except Exception as e:
            print(f"예기치 않은 에러 발생: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
