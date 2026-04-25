import chromadb

def migrate():
    import os
    db_path = "backend/data/chromadb" if os.path.exists("backend/data/chromadb") else "data/chromadb"
    print(f"Connecting to ChromaDB at {db_path}...")
    client = chromadb.PersistentClient(path=db_path)
    
    try:
        collection = client.get_collection("oil_market_events")
    except Exception as e:
        print("Collection not found or error:", e)
        return

    data = collection.get()
    ids = data['ids']
    metadatas = data['metadatas']

    if not ids:
        print("No records to migrate.")
        return

    updated_metadatas = []
    for m in metadatas:
        new_m = dict(m)
        
        # 기본 단일 기준 메타데이터 가져오기
        wti_score = new_m.get("impact_score", 0)
        wti_change_7d = new_m.get("wti_change_7d", 0.0)
        wti_change_1d = new_m.get("wti_change_1d", 0.0)
        wti_change_30d = new_m.get("wti_change_30d", 0.0)

        direction = "neutral"
        if wti_score > 0: direction = "bullish"
        elif wti_score < 0: direction = "bearish"

        # Dubai 패치
        if "dubai_score" not in new_m:
            new_m["dubai_score"] = wti_score
            new_m["dubai_direction"] = direction
            new_m["dubai_change_1d"] = wti_change_1d
            new_m["dubai_change_7d"] = wti_change_7d
            new_m["dubai_change_30d"] = wti_change_30d

        # Brent 패치
        if "brent_score" not in new_m:
            new_m["brent_score"] = wti_score
            new_m["brent_direction"] = direction
            new_m["brent_change_1d"] = wti_change_1d
            new_m["brent_change_7d"] = wti_change_7d
            new_m["brent_change_30d"] = wti_change_30d

        # WTI 추가 스코어 정보 패치
        if "wti_score" not in new_m:
            new_m["wti_score"] = wti_score
            new_m["wti_direction"] = direction

        updated_metadatas.append(new_m)

    collection.update(ids=ids, metadatas=updated_metadatas)
    print(f"Successfully migrated {len(ids)} records in ChromaDB to Multi-Crude schema!")

if __name__ == "__main__":
    migrate()
