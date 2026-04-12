from flask import Flask, jsonify
import mysql.connector
import psycopg2 # Thêm thư viện này để kết nối Postgres
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

MYSQL_CONFIG = {
    "host": "mysql",
    "user": "root",
    "password": "your_password",
    "database": "noah_retail"
}

POSTGRES_CONFIG = "host=postgres dbname=finance_db user=admin password=admin_password"

@app.route("/report", methods=["GET"])
def report():
    try:
        conn_mysql = mysql.connector.connect(**MYSQL_CONFIG)
        cursor_mysql = conn_mysql.cursor(dictionary=True)
        
        cursor_mysql.execute("SELECT COUNT(*) as total_orders FROM orders")
        total_orders = cursor_mysql.fetchone()["total_orders"]
        
        cursor_mysql.execute("SELECT SUM(total_price) as total_revenue FROM orders")
        total_revenue = cursor_mysql.fetchone()["total_revenue"] or 0
        
        cursor_mysql.close()
        conn_mysql.close()

        conn_pg = psycopg2.connect(POSTGRES_CONFIG)
        cur_pg = conn_pg.cursor()
        cur_pg.execute("SELECT COUNT(*) FROM transactions")
        processed_orders = cur_pg.fetchone()[0]
        cur_pg.close()
        conn_pg.close()

        return jsonify({
            "status": "success",
            "mysql_data": {
                "total_orders": total_orders,
                "total_revenue": total_revenue
            },
            "postgres_data": {
                "processed_orders_in_finance": processed_orders
            },
            "system_health": "All systems synced" if total_orders == processed_orders else "Syncing..."
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)