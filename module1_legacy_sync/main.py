import csv
import mysql.connector
import time
import os

DB_CONFIG = {
    'host': 'mysql', 
    'user': 'root',
    'password': 'your_password',
    'database': 'noah_retail'
}
CSV_PATH = "/app/data/inventory.csv"

def process_float_stock(value):
    """Xử lý lỗi FLOAT_VALUES cho Nhóm 3 [cite: 72, 73]"""
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0

def init_database_schema(cursor):
    """Tự động tạo bảng Products nếu init.sql chưa có [cite: 19]"""
    print("Đang kiểm tra và khởi tạo cấu trúc bảng...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Products (
            id INT PRIMARY KEY,
            name VARCHAR(255) DEFAULT 'Unknown',
            price DECIMAL(10, 2) DEFAULT 0.0,
            stock INT DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Orders (
            id INT PRIMARY KEY AUTO_INCREMENT,
            product_id INT,
            quantity INT,
            order_date DATETIME,
            status VARCHAR(20) DEFAULT 'PENDING'
        )
    """)

def sync_inventory():
    if not os.path.exists(CSV_PATH):
        return

    while True:
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            break
        except:
            print("Đợi MySQL khởi động...")
            time.sleep(5)
            
    cursor = conn.cursor()

    try:
        init_database_schema(cursor)

        with open(CSV_PATH, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    row = {str(k).strip().lower(): str(v).strip() for k, v in row.items()}
                    p_id = row.get('product_id')
                    raw_val = row.get('quantity') or row.get('stock') or row.get('qty')

                    if not p_id or raw_val is None:
                        continue

                    stock_value = process_float_stock(raw_val)
                    sql = """
                        INSERT INTO Products (id, stock) 
                        VALUES (%s, %s) 
                        ON DUPLICATE KEY UPDATE stock = VALUES(stock)
                    """
                    cursor.execute(sql, (p_id, stock_value))
                    
                except Exception as e:
                    print(f"[DIRTY DATA FOUND]: {e}")
                    continue
        
        conn.commit()
        print(f"--- Đã đồng bộ thành công lúc {time.ctime()} ---")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    while True:
        sync_inventory()
        time.sleep(10) 