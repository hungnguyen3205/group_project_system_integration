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

# THÊM ĐOẠN NÀY VÀO MODULE 2
@app.delete("/api/orders/{product_id}")
async def delete_order(product_id: int):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Lệnh xóa tất cả đơn hàng của sản phẩm đó
        query = "DELETE FROM orders WHERE product_id = %s"
        cursor.execute(query, (product_id,))
        conn.commit()
        
        return {"message": f"Đã xóa toàn bộ đơn hàng của sản phẩm {product_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()
            
# SỬA LẠI CÁCH CHẠY CHO ĐÚNG FASTAPI
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)