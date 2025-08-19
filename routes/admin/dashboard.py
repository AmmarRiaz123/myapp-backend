from flask import Blueprint, jsonify
from auth.token_validator import require_admin
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv() 

admin_dashboard_bp = Blueprint('admin_dashboard', __name__)

def get_db_connection(cursor_factory=None):
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432),
        sslmode=os.getenv('DB_SSLMODE', 'require')
    )
    cur = conn.cursor(cursor_factory=cursor_factory)
    return conn, cur

@admin_dashboard_bp.route('/admin/dashboard', methods=['GET'])
@require_admin
def get_dashboard():
    conn, cur = get_db_connection(cursor_factory=RealDictCursor)
    try:
        # Get dashboard summary
        cur.execute("SELECT * FROM admin_dashboard")
        summary = cur.fetchone()
        
        # Get low stock items
        cur.execute("""
            SELECT p.name, p.product_code, i.quantity
            FROM inventory i
            JOIN products p ON i.product_id = p.id
            WHERE i.quantity < 10
            ORDER BY i.quantity ASC
        """)
        low_stock = cur.fetchall()
        
        return jsonify({
            'success': True,
            'summary': summary,
            'low_stock_items': low_stock
        })
    finally:
        cur.close()
        conn.close()
