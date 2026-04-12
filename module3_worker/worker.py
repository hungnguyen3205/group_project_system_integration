import pika
import psycopg2
import json
import time
import threading # Cần thiết để chạy song song Web và Worker
from flask import Flask, send_from_directory
from flask_cors import CORS

# --- CẤU HÌNH ---
PG_CONFIG = {
    "host": "postgres",
    "database": "finance_db",
    "user": "admin",
    "password": "admin_password"
}

# --- PHẦN 1: LOGIC WORKER (XỬ LÝ NGẦM) ---

def save_to_postgres(data):
    """Lưu đơn hàng vào Postgres với cơ chế Retry liên tục"""
    while True:
        try:
            conn = psycopg2.connect(**PG_CONFIG)
            cur = conn.cursor()
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    order_id INT,
                    product_id INT,
                    quantity INT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            query = "INSERT INTO transactions (order_id, product_id, quantity) VALUES (%s, %s, %s)"
            cur.execute(query, (data['order_id'], data['product_id'], data['quantity']))
            
            conn.commit()
            cur.close()
            conn.close()
            print(f" [v] Đã lưu đơn hàng {data['order_id']} vào Postgres thành công!")
            return True 
        except Exception as e:
            print(f" [!] Postgres chưa sẵn sàng, đang thử lại sau 5s... ({e})")
            time.sleep(5)

def callback(ch, method, properties, body):
    try:
        order_data = json.loads(body)
        print(f" [!] Đang xử lý đơn hàng: {order_data}")
        if save_to_postgres(order_data):
            ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f" [x] Lỗi xử lý tin nhắn: {e}")

def start_rabbitmq_worker():
    """Hàm chạy RabbitMQ Consumer"""
    print(' [*] Đang kết nối tới RabbitMQ...')
    while True:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host='rabbitmq', heartbeat=600)
            )
            break
        except:
            print(" [!] RabbitMQ chưa sẵn sàng, đợi 5s...")
            time.sleep(5)

    channel = connection.channel()
    channel.queue_declare(queue='order_queue', durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='order_queue', on_message_callback=callback)
    
    print(' [*] Worker đã sẵn sàng! Đang đợi đơn hàng...')
    channel.start_consuming()

# --- PHẦN 2: LOGIC WEB SERVER (HIỂN THỊ GIAO DIỆN VUE) ---

app = Flask(__name__, static_folder='static')
CORS(app) # Cho phép gọi API từ bên ngoài nếu cần

@app.route('/')
def serve_vue():
    """Trả về file index.vue khi truy cập localhost:5002"""
    # Lưu ý: Trình duyệt sẽ đọc .vue như một file text/plain nếu không có loader. 
    # Nhưng theo yêu cầu của bạn, Flask sẽ gửi file này đi.
    return send_from_directory('static', 'index.html')

# --- PHẦN 3: KHỞI CHẠY ĐA LUỒNG ---

if __name__ == "__main__":
    # 1. Chạy Worker RabbitMQ trong một luồng riêng (Background Thread)
    worker_thread = threading.Thread(target=start_rabbitmq_worker)
    worker_thread.daemon = True # Tự tắt khi main thread tắt
    worker_thread.start()

    # 2. Chạy Flask Web Server ở luồng chính (Main Thread)
    # Port 5002 như đã thống nhất cho Dashboard Module 3
    print(" [Web] Dashboard đang chạy tại http://localhost:5002")
    app.run(host='0.0.0.0', port=5002, debug=False, use_reloader=False)