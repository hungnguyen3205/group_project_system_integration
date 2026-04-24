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

# --- PHẦN MỚI: HÀM LỌC DỮ LIỆU (DATA CLEANING) ---

def clean_and_validate(row):
    """
    Hàm lọc dữ liệu bẩn (Dirty Data):
    1. Kiểm tra ID có phải số nguyên dương không.
    2. Kiểm tra giá trị tồn kho có hợp lệ không.
    3. Loại bỏ khoảng trắng thừa.
    """
    try:
        # Làm sạch key và value
        clean_row = {str(k).strip().lower(): str(v).strip() for k, v in row.items()}
        
        p_id = clean_row.get('product_id')
        raw_val = clean_row.get('quantity') or clean_row.get('stock') or clean_row.get('qty')

        # Lọc: Nếu thiếu ID hoặc thiếu giá trị tồn kho -> Bỏ qua
        if not p_id or raw_val is None:
            return None

        # Lọc: Kiểm tra ID phải là số
        p_id = int(p_id)
        if p_id <= 0: return None

        # Lọc & Transform: Xử lý giá trị tồn kho (Float -> Int)
        stock_value = int(float(raw_val))
        if stock_value < 0: stock_value = 0 # Không để tồn kho âm

        return (p_id, stock_value)
    except:
        return None

# --- GIỮ NGUYÊN CÁC PHẦN KHỞI TẠO ---

def init_database_schema(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Products (
            id INT PRIMARY KEY,
            name VARCHAR(255) DEFAULT 'Unknown',
            price DECIMAL(10, 2) DEFAULT 0.0,
            stock INT DEFAULT 0
        )
    """)

def sync_inventory():
    if not os.path.exists(CSV_PATH):
        return

    # Kết nối DB (giữ nguyên logic retry của bạn)
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        init_database_schema(cursor)

        # BỘ NHỚ ĐỆM ĐỂ GỘP DỮ LIỆU
        final_inventory = {} 

        with open(CSV_PATH, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # 1. Làm sạch dữ liệu bẩn (Dirty Data)
                    row = {str(k).strip().lower(): str(v).strip() for k, v in row.items()}
                    p_id = row.get('product_id')
                    raw_val = row.get('quantity') or row.get('stock') or row.get('qty')

                    # LỌC BẨN: Bỏ qua nếu ID hoặc số lượng không hợp lệ
                    if not p_id or raw_val is None:
                        continue
                    
                    p_id = int(p_id)
                    stock_value = int(float(raw_val))
                    
                    if p_id <= 0 or stock_value <= 0:
                        continue # Bỏ qua ID âm hoặc số lượng bằng 0

                    # 2. GỘP DỮ LIỆU (AGGREGATION): Cộng dồn nếu trùng ID trong file
                    if p_id in final_inventory:
                        final_inventory[p_id] += stock_value
                    else:
                        final_inventory[p_id] = stock_value

                except Exception as e:
                    print(f"[DIRTY DATA SKIPPED]: {e}")
                    continue

        # 3. ĐẨY DỮ LIỆU ĐÃ SẠCH VÀ ĐÃ GỘP VÀO DATABASE
        if final_inventory:
            # Xóa trắng bảng cũ để nạp lại bản mới đã gộp (nếu muốn số liệu chính xác 5000 dòng)
            # cursor.execute("TRUNCATE TABLE Products") 
            
            sql = "INSERT INTO Products (id, stock) VALUES (%s, %s) ON DUPLICATE KEY UPDATE stock = VALUES(stock)"
            data_to_db = [(k, v) for k, v in final_inventory.items()]
            cursor.executemany(sql, data_to_db)
            
            conn.commit()
            print(f"--- Đã đồng bộ {len(data_to_db)} sản phẩm sạch (đã gộp) ---")

    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    # Chạy đồng bộ một lần hoặc theo chu kỳ
    sync_inventory()