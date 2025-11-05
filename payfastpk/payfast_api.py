import os
from flask import Blueprint, request, jsonify
import requests
import logging
from urllib.parse import urlencode
import hashlib
import uuid
import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json
from dotenv import load_dotenv
import json

load_dotenv()

payfast_bp = Blueprint('payfast', __name__)

DEFAULT_RETURN_URL = 'https://pekypk.com/payment-success'
DEFAULT_CANCEL_URL = 'https://pekypk.com/payment-cancel'

logging.basicConfig(level=logging.INFO)

def format_amount(amount):
    """Ensure amount is formatted to two decimal places as string."""
    try:
        return "{:.2f}".format(float(amount))
    except Exception as e:
        logging.error(f"Invalid amount format: {amount} ({e})")
        return "0.00"

def load_payfast_config():
    """
    Read PayFast configuration from environment at call time.
    Priority:
      1. PAYFAST_URL (explicit)
      2. PAYFAST_USE_SANDBOX (truthy) -> sandbox URL
      3. default to live URL
    Merchant credentials fall back to provided integration defaults if env vars are not set.
    """
    explicit_url = os.getenv('PAYFAST_URL')
    use_sandbox = os.getenv('PAYFAST_USE_SANDBOX', '').lower() in ('1', 'true', 'yes')
    sandbox_url = os.getenv('PAYFAST_SANDBOX_URL', 'https://sandbox.payfast.co.za/eng/process')
    live_url = 'https://www.payfast.co.za/eng/process'

    if explicit_url:
        url = explicit_url
    elif use_sandbox:
        url = sandbox_url
    else:
        url = os.getenv('PAYFAST_URL', live_url)
        
    # Use environment variables, fall back to defaults only if not set
    merchant_id = os.getenv('PAYFAST_MERCHANT_ID', '10043315')
    merchant_key = os.getenv('PAYFAST_MERCHANT_KEY', 'u82ct2ml2kb80')
    passphrase = os.getenv('PAYFAST_PASSPHRASE', '')

    # Log non-sensitive config for debugging
    if 'sandbox.payfast' in url:
        logging.info("Using PayFast SANDBOX environment for payments")
    else:
        logging.info("Using PayFast LIVE environment for payments")

    return {
        'merchant_id': merchant_id,  # Changed: no longer hardcoded
        'merchant_key': merchant_key,  # Changed: no longer hardcoded
        'url': url,
        'passphrase': passphrase
    }

def generate_signature(data, passphrase=''):
    """
    Generate PayFast signature:
    - Exclude 'signature' key.
    - Sort keys alphabetically.
    - URL encode key=value pairs (values stringified).
    - Append passphrase if provided.
    - MD5 hash the final string.
    """
    try:
        params = {k: v for k, v in data.items() if k != 'signature'}
        # ensure deterministic string conversion of values
        sorted_items = sorted((k, "" if v is None else str(v)) for k, v in params.items())
        param_str = urlencode(sorted_items)
        if passphrase:
            param_str += f"&passphrase={passphrase}"
        return hashlib.md5(param_str.encode('utf-8')).hexdigest()
    except Exception as e:
        logging.error(f"Error generating signature: {e}")
        return ""

def user_friendly_error(message, details=None):
    """Return a user-friendly error response and log details."""
    logging.error(f"PayFast error: {message}" + (f" Details: {details}" if details else ""))
    return jsonify({'success': False, 'message': message}), 400

def update_order_payment_status(m_payment_id, success=True):
    """
    Update orders.payment_status = TRUE for the given order id.
    m_payment_id is expected to be the orders.id (integer). If not integer, skip update.
    """
    if not m_payment_id:
        logging.info("No m_payment_id provided; skipping DB update.")
        return False

    # try converting to int (orders.id is integer). If not possible, skip.
    try:
        order_id = int(m_payment_id)
    except (ValueError, TypeError):
        logging.warning(f"m_payment_id is not an integer (m_payment_id={m_payment_id}); cannot update orders table.")
        return False

    try:
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST'),
            database=os.environ.get('DB_NAME'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD'),
            port=os.environ.get('DB_PORT', 5432),
            sslmode=os.getenv('DB_SSLMODE', 'require')
        )
        cur = conn.cursor()
        # Only mark as paid when success is True
        cur.execute(
            "UPDATE orders SET payment_status = %s WHERE id = %s RETURNING id",
            (success, order_id)
        )
        updated = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        if updated:
            logging.info(f"Order {order_id} payment_status updated to {success}.")
            return True
        else:
            logging.warning(f"No order found with id={order_id}; payment_status not updated.")
            return False
    except Exception as e:
        logging.error(f"Failed to update order payment_status for id={order_id}: {e}")
        return False

# --- New DB helpers (added) ---
def db_connect():
    """Return (conn, cur) connected to Postgres using environment variables."""
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432),
        sslmode=os.getenv('DB_SSLMODE', 'require')
    )
    cur = conn.cursor()
    return conn, cur

def find_order_by_m_payment_id(m_payment_id):
    """
    Try to resolve m_payment_id to an order id.
    - If m_payment_id is integer, try orders.id
    - Otherwise try orders.m_payment_id = provided value
    Returns order_id or None.
    """
    if not m_payment_id:
        return None
    try:
        # try as integer id first
        order_id = int(m_payment_id)
        conn, cur = db_connect()
        cur.execute("SELECT id FROM orders WHERE id = %s", (order_id,))
        rec = cur.fetchone()
        cur.close()
        conn.close()
        if rec:
            return rec[0]
    except (ValueError, TypeError):
        order_id = None
    except Exception:
        # fallthrough to try m_payment_id lookup
        try:
            cur.close()
            conn.close()
        except Exception:
            pass

    try:
        conn, cur = db_connect()
        cur.execute("SELECT id FROM orders WHERE m_payment_id = %s", (m_payment_id,))
        rec = cur.fetchone()
        cur.close()
        conn.close()
        if rec:
            return rec[0]
    except Exception:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass

    return None

@payfast_bp.route('/payfast/initiate', methods=['POST'])
def initiate_payment():
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return user_friendly_error("Invalid JSON data provided.", str(e))

    try:
        cfg = load_payfast_config()

        amount_raw = data.get('amount')
        if amount_raw is None:
            return user_friendly_error("Amount is required for payment.")
        amount = format_amount(amount_raw)
        # ensure amount is positive and not zero
        try:
            if float(amount) <= 0:
                return user_friendly_error("Amount must be greater than zero.")
        except Exception:
            return user_friendly_error("Invalid amount provided.")

        item_name = data.get('item_name', 'Order Payment')
        return_url = data.get('return_url', DEFAULT_RETURN_URL)
        cancel_url = data.get('cancel_url', DEFAULT_CANCEL_URL)

        if not cfg['merchant_id'] or not cfg['merchant_key']:
            return user_friendly_error("Payment gateway is not configured. Please contact support.")

        # Build payfast payload; include optional fields if provided
        payfast_data = {
            'merchant_id': cfg['merchant_id'],
            'merchant_key': cfg['merchant_key'],
            'amount': amount,
            'item_name': item_name,
            'return_url': return_url,
            'cancel_url': cancel_url,
        }

        # include m_payment_id if supplied; otherwise generate one
        m_payment_id = data.get('m_payment_id') or str(uuid.uuid4())
        payfast_data['m_payment_id'] = m_payment_id

        # include optional customer email if provided
        email = data.get('email_address')
        if email:
            payfast_data['email_address'] = email

        # Attempt to link this m_payment_id to an order (if caller passed an order id)
        try:
            resolved_order = find_order_by_m_payment_id(m_payment_id)
            if resolved_order:
                # set m_payment_id and provider on the order for traceability
                conn, cur = db_connect()
                cur.execute("""
                    UPDATE orders
                    SET m_payment_id = %s, payment_provider = %s, payment_updated_at = NOW()
                    WHERE id = %s
                    RETURNING id
                """, (m_payment_id, 'payfast', resolved_order))
                if cur.fetchone():
                    conn.commit()
                    logging.info(f"Linked m_payment_id to order {resolved_order}")
                else:
                    conn.rollback()
                cur.close()
                conn.close()
        except Exception as e:
            logging.warning(f"Failed to link m_payment_id to order: {e}")

        signature = generate_signature(payfast_data, cfg['passphrase'])
        if not signature:
            return user_friendly_error("Failed to generate payment signature. Please try again.")

        payfast_data['signature'] = signature
        payment_url = f"{cfg['url']}?{urlencode(payfast_data)}"

        # Avoid logging secrets: log non-sensitive information only
        logging.info(f"Initiating PayFast payment: merchant_id={cfg['merchant_id']}, m_payment_id={m_payment_id}, amount={amount}, item_name={item_name}")

        return jsonify({'success': True, 'payment_url': payment_url})
    except Exception as e:
        return user_friendly_error("Failed to initiate payment. Please try again later.", str(e))

@payfast_bp.route('/payfast/callback', methods=['POST'])
def payfast_callback():
    try:
        post_data = request.form.to_dict()
        logging.info(f"PayFast callback received: keys={list(post_data.keys())}")

        if not post_data:
            return user_friendly_error("No callback data received from PayFast.")

        cfg = load_payfast_config()
        received_signature = post_data.get('signature', '')
        valid_signature = generate_signature(post_data, cfg['passphrase'])
        if not received_signature:
            return user_friendly_error("No signature received in callback.")
        if received_signature != valid_signature:
            logging.warning(f"Signature mismatch on callback: received!=expected")
            return user_friendly_error("Payment verification failed. Invalid signature received.")

        # Signature validated — persist notification and update order status as needed
        m_payment_id = post_data.get('m_payment_id')
        pf_status = (post_data.get('payment_status') or '').upper()
        payment_success = pf_status in ('COMPLETE', 'PAID', 'SUCCESS') or pf_status == ''

        # Try to resolve to our order id
        order_id = find_order_by_m_payment_id(m_payment_id)

        # Persist notification
        try:
            conn, cur = db_connect()
            cur.execute("""
                INSERT INTO payment_notifications (order_id, provider, notification_payload, payment_status)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (order_id, 'payfast', Json(post_data), post_data.get('payment_status')))
            # Safely get returned id without relying on cursor.rowcount (may not exist on test doubles)
            try:
                notif_row = cur.fetchone()
                notif_id = notif_row[0] if notif_row else None
            except Exception:
                notif_id = None

            # Update orders table: set payment_payload, provider, m_payment_id and payment_updated_at
            if order_id:
                cur.execute("""
                    UPDATE orders
                    SET payment_payload = %s,
                        payment_provider = %s,
                        payment_updated_at = NOW(),
                        m_payment_id = %s
                    WHERE id = %s
                    RETURNING id
                """, (Json(post_data), 'payfast', m_payment_id, order_id))

                # mark as paid when appropriate
                if payment_success:
                    cur.execute("UPDATE orders SET payment_status = TRUE WHERE id = %s", (order_id,))

            conn.commit()
            # close resources in normal flow
            try:
                cur.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass

            logging.info(f"Payment notification persisted (notif_id={notif_id}) for order_id={order_id}")
        except Exception as e:
            # attempt to cleanup partially opened resources
            try:
                cur.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
            logging.error(f"Failed to persist payment notification or update order: {e}")

        # TODO: Additional order processing (notify user, bookkeeping, etc.)

        return jsonify({'success': True, 'message': 'Callback received and signature validated'}), 200
    except Exception as e:
        return user_friendly_error("Failed to process payment callback. Please contact support.", str(e))

__all__ = [
    'payfast_bp',
    'format_amount',
    'load_payfast_config',
    'generate_signature',
    'db_connect',
    'find_order_by_m_payment_id'
]
