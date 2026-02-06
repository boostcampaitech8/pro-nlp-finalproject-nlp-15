import pymysql

# dbname 없이 접속 시도
conn = pymysql.connect(
    host="168.107.45.18",
    port=7319,
    user="confident-ai",
    password="nbcfp235780",
    charset='utf8mb4'
)

try:
    with conn.cursor() as cursor:
        cursor.execute("SHOW DATABASES;") # 접근 가능한 모든 DB 목록 조회
        databases = cursor.fetchall()
        print("\n=== 접근 가능한 데이터베이스 목록 ===")
        for db in databases:
            print(f"👉 {db[0]}")
        print("==================================\n")
finally:
    conn.close()