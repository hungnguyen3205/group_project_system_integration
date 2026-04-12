import pika
import psycopg2
import json
import time
import threading
import pymongo # Thêm thư viện MongoDB
from datetime import datetime
from flask import Flask, send_from_directory
from flask_cors import CORS

PG_CONFIG = {
    "host": "postgres",
    "database": "finance_db",
    "user": "admin",
    "password": "admin_password"
}

try:
    mongo_client = pymongo.MongoClient("mongodb://mongodb:27017/", serverSelectionTimeoutMS=5000)
    db = mongo_client["noah_audit"]
    audit_collection = db["logs"]
except Exception as e:
    print(f" [!] Cảnh báo: Không thể kết nối MongoDB: {e}")

def save_to_audit_log(data, status):
    """Ghi log giao dịch vào MongoDB"""
    try:
        log_entry = {
            "order_id": data.get('order_id'),
            "status": status,
            "timestamp": datetime.utcnow(),
            "payload": data,
            "module": "worker_module_3"
        }
        audit_collection.insert_one(log_entry)
        print(f" [M] Đã ghi Audit Log cho đơn hàng {data.get('order_id')}")
    except Exception as e:
        print(f" [!] Lỗi ghi log MongoDB: {e}")

def save_to_postgres(data):
    """Lưu đơn hàng vào Postgres với cơ chế Retry"""
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
            return True 
        except Exception as e:
            print(f" [!] Postgres chưa sẵn sàng, đang thử lại... ({e})")
            time.sleep(5)

def callback(ch, method, properties, body):
    try:
        order_data = json.loads(body)
        print(f" [!] Đang xử lý đơn hàng: {order_data}")
        
        if save_to_postgres(order_data):
            # 2. Lưu Audit Log vào MongoDB sau khi thành công
            save_to_audit_log(order_data, "SUCCESS")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(f" [v] Đã xử lý xong đơn hàng {order_data['order_id']}")
            
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

app = Flask(__name__, static_folder='static')
CORS(app)

@app.route('/')
def serve_vue():
    return send_from_directory('static', 'index.html')


if __name__ == "__main__":
    worker_thread = threading.Thread(target=start_rabbitmq_worker)
    worker_thread.daemon = True 
    worker_thread.start()

    print(" [Web] Dashboard đang chạy tại http://localhost:5002")
    app.run(host='0.0.0.0', port=5002, debug=False, use_reloader=False)