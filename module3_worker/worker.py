import pika
import psycopg2
import json
import time
import os

PG_CONFIG = {
    "host": "postgres",
    "database": "finance_db",
    "user": "admin",
    "password": "admin_password"
}

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
    """Hàm xử lý khi lấy được tin nhắn từ Queue"""
    try:
        order_data = json.loads(body)
        print(f" [!] Đang xử lý đơn hàng: {order_data}")
        
        if save_to_postgres(order_data):
            ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f" [x] Lỗi xử lý tin nhắn: {e}")

def start_worker():
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
    
    print(' [*] Worker đã sẵn sàng! Đang đợi đơn hàng từ Module 2...')
    channel.start_consuming()

if __name__ == "__main__":
    start_worker()