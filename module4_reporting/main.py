from flask import Flask, jsonify
from flask_cors import CORS
import mysql.connector
import psycopg2
import time

app = Flask(__name__)
# Cấu hình CORS chặt chẽ hơn để tránh lỗi trình duyệt
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

MYSQL_CONFIG = {
    "host": "mysql",
    "user": "root",
    "password": "your_password",
    "database": "noah_retail"
}

POSTGRES_CONFIG = "host=postgres dbname=finance_db user=admin password=admin_password"

def get_mysql_connection():
    """Hàm tự động kết nối lại nếu MySQL chưa sẵn sàng"""
    max_retries = 3
    while max_retries > 0:
        try:
            conn = mysql.connector.connect(**MYSQL_CONFIG)
            if conn.is_connected():
                return conn
        except:
            print("--- Đang đợi MySQL khởi động (Module 4) ---")
            time.sleep(2)
            max_retries -= 1
    return None

@app.route("/report", methods=["GET"])
def report():
    conn_mysql = None
    conn_pg = None
    try:
        # --- 1. KẾT NỐI VÀ LẤY DỮ LIỆU MYSQL ---
        conn_mysql = get_mysql_connection()
        if not conn_mysql:
            return jsonify({"error": "Không thể kết nối MySQL sau nhiều lần thử"}), 500
            
        cursor_mysql = conn_mysql.cursor(dictionary=True)
        
        # Lấy danh sách đơn hàng (Sắp xếp mới nhất lên đầu)
        cursor_mysql.execute("SELECT id, product_id, quantity FROM orders ORDER BY id DESC")
        orders_list = cursor_mysql.fetchall()
        
        # Tính tổng doanh thu
        cursor_mysql.execute("SELECT SUM(total_price) as total_revenue FROM orders")
        row_rev = cursor_mysql.fetchone()
        total_revenue = float(row_rev["total_revenue"]) if row_rev and row_rev["total_revenue"] else 0.0
        
        cursor_mysql.close()

        # --- 2. KẾT NỐI VÀ LẤY DỮ LIỆU POSTGRES ---
        conn_pg = psycopg2.connect(POSTGRES_CONFIG)
        cur_pg = conn_pg.cursor()
        cur_pg.execute("SELECT COUNT(*) FROM transactions")
        processed_orders = cur_pg.fetchone()[0]
        cur_pg.close()

        # --- 3. ĐÓNG GÓI JSON ĐÚNG CẤU TRÚC DASHBOARD ---
        total_raw = len(orders_list)
        result_data = {
            "status": "success",
            "mysql_data": {
                "total_orders": total_raw,
                "total_revenue": total_revenue,
                "orders_list": orders_list  # Dữ liệu này giúp Vue hiện "Total Unique Items"
            },
            "postgres_data": {
                "processed_orders_in_finance": processed_orders
            },
            "system_health": "All systems synced" if total_raw == processed_orders else "Syncing..."
        }

        # --- 4. TRẢ VỀ RESPONSE VÀ XỬ LÝ LỖI TRÌNH DUYỆT/ĐIỆN THOẠI ---
        # Trong main.py
        response = jsonify(result_data)
        response.headers.add("Access-Control-Allow-Origin", "*") # Mở cửa cho Dashboard
        response.headers.add("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("bypass-tunnel-reminder", "true") # Bỏ qua trang xác nhận của lhr.life
        return response

    except Exception as e:
        print(f"Lỗi Module 4: {e}") 
        return jsonify({"status": "error", "message": str(e)}), 500
        
    finally:
        # LUÔN LUÔN ĐÓNG KẾT NỐI ĐỂ GIẢI PHÓNG TÀI NGUYÊN
        if conn_mysql and conn_mysql.is_connected():
            conn_mysql.close()
        if conn_pg:
            conn_pg.close()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, threaded=True)