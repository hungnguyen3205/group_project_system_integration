from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pika
import mysql.connector
import json
import uvicorn # Nhớ import uvicorn

app = FastAPI()

# Thêm CORS để Ngrok và các máy khác không bị chặn
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONFIG = {
    'host': 'mysql',
    'user': 'root',        
    'password': 'your_password', 
    'database': 'noah_retail'
}

def send_to_queue(order_data):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
        channel = connection.channel()
        channel.queue_declare(queue='order_queue', durable=True)
        channel.basic_publish(
            exchange='',
            routing_key='order_queue',
            body=json.dumps(order_data),
            properties=pika.BasicProperties(delivery_mode=2) 
        )
        connection.close()
    except Exception as e:
        print(f"Lỗi RabbitMQ: {e}")

# ĐƯA RA NGOÀI HÀM (KHÔNG THỤT LỀ)
@app.post("/api/orders")
async def create_order(order: dict):
    p_id = order.get("product_id")
    qty = order.get("quantity")
    
    if not p_id or not qty:
        raise HTTPException(status_code=400, detail="Thiếu thông tin đơn hàng")

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        query = """
            INSERT INTO orders (user_id, product_id, quantity, total_price, status) 
            VALUES (1, %s, %s, 0, 'PENDING')
        """
        cursor.execute(query, (p_id, qty))
        order_id = cursor.lastrowid
        conn.commit()
        
        order_msg = {"order_id": order_id, "product_id": p_id, "quantity": qty}
        send_to_queue(order_msg)
        
        return {"message": "Đơn hàng đã được tiếp nhận", "order_id": order_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()

@app.delete("/api/orders/{product_id}")
async def delete_order(product_id: int):
    conn_mysql = None
    conn_pg = None # Khởi tạo biến để tránh lỗi
    try:
        # --- 1. XÓA BÊN MYSQL ---
        conn_mysql = mysql.connector.connect(**DB_CONFIG)
        cursor_ms = conn_mysql.cursor()
        cursor_ms.execute("DELETE FROM orders WHERE product_id = %s", (product_id,))
        conn_mysql.commit()
        
        # --- 2. XÓA BÊN POSTGRES ---
        import psycopg2 # Đảm bảo đã import thư viện này
        # Nhớ thay đổi thông tin admin/password cho đúng với máy bạn
        conn_pg = psycopg2.connect("host=postgres dbname=finance_db user=admin password=admin_password")
        cursor_pg = conn_pg.cursor() # TẠO BIẾN cursor_pg Ở ĐÂY
        cursor_pg.execute("DELETE FROM transactions WHERE product_id = %s", (product_id,))
        conn_pg.commit()
        
        return {"message": f"Đã xóa sản phẩm {product_id} ở cả 2 database thành công!"}

    except Exception as e:
        print(f"Lỗi: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Đóng kết nối an toàn
        if conn_mysql and conn_mysql.is_connected():
            conn_mysql.close()
        if conn_pg:
            conn_pg.close()
            
# SỬA LẠI CÁCH CHẠY CHO ĐÚNG FASTAPI
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)