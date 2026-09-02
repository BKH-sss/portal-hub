import os
import sys
import time
import shutil
import chromadb
import uuid
from datetime import datetime

# 강제로 UTF-8 출력으로 설정하여 윈도우 cmd에서 이모지 출력 시 발생하는 cp949 에러 방지
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

MEMORY_DIR = r"B:\AI_Brain"
OBSIDIAN_DIR = os.path.join(MEMORY_DIR, "Obsidian_Vault")
PROCESSED_DIR = os.path.join(MEMORY_DIR, "processed_data")
LOG_PATH = os.path.join(MEMORY_DIR, "data_absorber.log")

os.makedirs(OBSIDIAN_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# ChromaDB client
client = chromadb.PersistentClient(path=MEMORY_DIR)

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def get_collection_for_file(filename):
    fname = filename.lower()
    if fname.startswith("lol_"):
        return "lol_knowledge"
    elif fname.startswith("r6s_"):
        return "r6s_knowledge"
    elif fname.startswith("coding_"):
        return "coding_memory"
    elif fname.startswith("hacking_"):
        return "hacking_knowledge"
    else:
        # 접두사가 없으면 스카디가 챙기는 일반 지식으로 분류
        return "general_knowledge"

def chunk_markdown(text, chunk_size=800):
    """마크다운 텍스트를 문단 단위로 쪼갭니다."""
    chunks = []
    current_chunk = ""
    for paragraph in text.split("\n\n"):
        if len(current_chunk) + len(paragraph) < chunk_size:
            current_chunk += paragraph + "\n\n"
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = paragraph + "\n\n"
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    return chunks

def process_file(file_path, filename):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        collection_name = get_collection_for_file(filename)
        collection = client.get_or_create_collection(name=collection_name)
        
        chunks = chunk_markdown(content)
        
        if not chunks:
            log(f"⚠ 내용이 없어 건너뜀: {filename}")
            return
            
        docs = []
        ids = []
        metadatas = []
        
        for i, chunk in enumerate(chunks):
            doc_id = f"{filename}_{uuid.uuid4().hex[:6]}_{i}"
            docs.append(chunk)
            ids.append(doc_id)
            metadatas.append({"source": filename, "chunk_index": i, "date_added": datetime.now().isoformat()})
            
        collection.add(documents=docs, ids=ids, metadatas=metadatas)
        log(f"✅ [{collection_name}] '{filename}' 소화 완료! (청크 {len(chunks)}개)")
        
    except Exception as e:
        log(f"❌ '{filename}' 처리 실패: {e}")

def run_absorber():
    log("🚀 자율형 데이터 흡수 파이프라인 (Data Absorber) 가동 시작!")
    log(f"감시 폴더: {OBSIDIAN_DIR}")
    
    while True:
        try:
            for filename in os.listdir(OBSIDIAN_DIR):
                if filename.endswith((".md", ".txt", ".json")):
                    file_path = os.path.join(OBSIDIAN_DIR, filename)
                    
                    # 파일 쓰기가 완전히 끝났는지 기다림
                    time.sleep(1)
                    
                    log(f"👀 새로운 파일 발견: {filename}")
                    process_file(file_path, filename)
                    
                    # 처리 완료된 파일은 processed_data 폴더로 이동
                    dest_path = os.path.join(PROCESSED_DIR, filename)
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    shutil.move(file_path, dest_path)
                    
            time.sleep(5) # 5초마다 옵시디언 볼트(폴더) 확인
            
        except Exception as e:
            log(f"시스템 오류 발생: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_absorber()
