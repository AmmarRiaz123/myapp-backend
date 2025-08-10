import os
from flask import Blueprint, request, jsonify
import psycopg2

review_bp = Blueprint('review', __name__)

def get_db_connection():
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432),
        sslmode='require'
    )
    return conn

@review_bp.route('/product/<int:product_id>/review', methods=['POST'])
def add_review(product_id):
    data = request.get_json(force=True)
    rating = data.get('rating')
    if rating is None:
        return jsonify({'success': False, 'message': 'Rating is required'}), 400
    try:
        rating = float(rating)
        if not (0.0 <= rating <= 5.0):
            return jsonify({'success': False, 'message': 'Rating must be between 0 and 5'}), 400
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Rating must be a decimal number'}), 400

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE products SET rating = %s WHERE id = %s",
            (rating, product_id)
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Review added successfully', 'rating': rating}), 200
    except Exception as e:
        if cur:
            cur.close()
        if conn:
            conn.close()
        return jsonify({'success': False, 'message': 'Failed to add review', 'error': str(e)}), 500
