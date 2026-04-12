from fastapi import FastAPI, HTTPException
import pika
import mysql.connector
import json

app = FastAPI()

DB_CONFIG = {
    'host': 'mysql',
    'user': 'root',        
    'password': 'your_password', 
    'database': 'noah_retail'
}

def send_to_queue(order_data):
    """Đẩy dữ liệu đơn hàng vào RabbitMQ"""
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
        channel = connection.channel()
        # Tạo queue tên là 'order_queue'
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
        if 'conn' in locals(): conn.close()