from flask import Blueprint, request, jsonify
from auth.token_validator import require_admin
import os
import psycopg2
from psycopg2.extras import RealDictCursor

admin_orders_bp = Blueprint('admin_orders', __name__)

def get_db_connection(cursor_factory=None):
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432),
        sslmode='require'
    )
    cur = conn.cursor(cursor_factory=cursor_factory)
    return conn, cur

@admin_orders_bp.route('/admin/orders', methods=['GET'])
@require_admin
def list_orders():
    conn, cur = get_db_connection(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT o.*, c.name as customer_name, c.email as customer_email,
                   json_agg(json_build_object(
                       'product_id', oi.product_id,
                       'quantity', oi.quantity,
                       'price', oi.price,
                       'product_name', p.name
                   )) as items
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            JOIN order_items oi ON o.id = oi.order_id
            JOIN products p ON oi.product_id = p.id
            GROUP BY o.id, c.name, c.email
            ORDER BY o.created_at DESC
        """)
        orders = cur.fetchall()
        return jsonify({'success': True, 'orders': orders})
    finally:
        cur.close()
        conn.close()

@admin_orders_bp.route('/admin/orders/<int:order_id>', methods=['PUT'])
@require_admin
def update_order_status(order_id):
    data = request.get_json()
    new_status = data.get('status')
    
    conn, cur = get_db_connection()
    try:
        cur.execute("""
            UPDATE orders 
            SET status = %s 
            WHERE id = %s
            RETURNING id
        """, (new_status, order_id))
        updated = cur.fetchone()
        conn.commit()
        
        if not updated:
            return jsonify({'success': False, 'message': 'Order not found'}), 404
            
        return jsonify({'success': True, 'message': f'Order status updated to {new_status}'})
    finally:
        cur.close()
        conn.close()
