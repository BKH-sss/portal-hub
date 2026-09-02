import os
import chromadb

# 1. 파일 삭제
profile_path = r"B:\AI_Brain\user_profile.md"
if os.path.exists(profile_path):
    os.remove(profile_path)
    print(f"Deleted {profile_path}")
else:
    print(f"File not found: {profile_path}")

# 2. ChromaDB 청소
try:
    client = chromadb.PersistentClient(path=r"B:\AI_Brain")
    collection = client.get_collection(name="lol_knowledge")
    
    # game_reflection 메타데이터를 가진 항목을 찾아 삭제
    results = collection.get(where={"source": "game_reflection"})
    if results and results['ids']:
        print(f"Found {len(results['ids'])} reflection memories in ChromaDB. Deleting...")
        collection.delete(ids=results['ids'])
        print("ChromaDB reflections cleared.")
    else:
        print("No reflection memories found in ChromaDB.")
except Exception as e:
    print(f"ChromaDB cleanup error: {e}")
