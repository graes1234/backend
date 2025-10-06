import sqlite3
#수정용
DB_FILE = "fabrics.db"

def add_fabric(fabric, ko_name, wash, dry, note):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
    INSERT OR REPLACE INTO fabric_care (fabric, ko_name, wash_method, dry_method, special_note)
    VALUES (?, ?, ?, ?, ?)
    """, (fabric, ko_name, wash, dry, note))
    conn.commit()
    conn.close()
    print(f"{fabric} ({ko_name}) 추가/수정 완료 ✅")

def delete_fabric(fabric):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM fabric_care WHERE fabric = ?", (fabric,))
    conn.commit()
    conn.close()
    print(f"{fabric} 삭제 완료 ❌")

def view_all():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT * FROM fabric_care")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("⚠️ 데이터가 없습니다.")
    else:
        print("\n📘 현재 DB 내용:")
        for row in rows:
            print(row)

# 예시 실행
if __name__ == "__main__":
    view_all()  # 현재 DB 내용 확인, 실행 시 함수 바꿔서 사용
    # add_fabric("Linen", "찬물 손세탁", "그늘 건조", "중온 다림질", "수축 주의")
    # delete_fabric("Polyester")
