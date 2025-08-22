import os
from flask import Blueprint, request, jsonify
import requests
import logging
from urllib.parse import urlencode
import hashlib

payfast_bp = Blueprint('payfast', __name__)

PAYFAST_MERCHANT_ID = os.getenv('PAYFAST_MERCHANT_ID')
PAYFAST_MERCHANT_KEY = os.getenv('PAYFAST_MERCHANT_KEY')
PAYFAST_URL = os.getenv('PAYFAST_URL', 'https://www.payfast.co.za/eng/process')
PAYFAST_PASSPHRASE = os.getenv('PAYFAST_PASSPHRASE', '')  # Optional

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

def generate_signature(data, passphrase=''):
    """
    Generate PayFast signature:
    - Exclude 'signature' key.
    - Sort keys alphabetically.
    - URL encode key=value pairs.
    - Append passphrase if provided.
    - MD5 hash the final string.
    """
    try:
        params = {k: v for k, v in data.items() if k != 'signature'}
        sorted_items = sorted(params.items())
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

@payfast_bp.route('/payfast/initiate', methods=['POST'])
def initiate_payment():
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return user_friendly_error("Invalid JSON data provided.", str(e))

    try:
        amount = format_amount(data.get('amount'))
        item_name = data.get('item_name', 'Order Payment')
        return_url = data.get('return_url', DEFAULT_RETURN_URL)
        cancel_url = data.get('cancel_url', DEFAULT_CANCEL_URL)

        if not data.get('amount'):
            return user_friendly_error("Amount is required for payment.")
        if not PAYFAST_MERCHANT_ID or not PAYFAST_MERCHANT_KEY:
            return user_friendly_error("Payment gateway is not configured. Please contact support.")

        payfast_data = {
            'merchant_id': PAYFAST_MERCHANT_ID,
            'merchant_key': PAYFAST_MERCHANT_KEY,
            'amount': amount,
            'item_name': item_name,
            'return_url': return_url,
            'cancel_url': cancel_url,
        }

        signature = generate_signature(payfast_data, PAYFAST_PASSPHRASE)
        if not signature:
            return user_friendly_error("Failed to generate payment signature. Please try again.")

        payfast_data['signature'] = signature
        payment_url = f"{PAYFAST_URL}?{urlencode(payfast_data)}"
        return jsonify({'success': True, 'payment_url': payment_url})
    except Exception as e:
        return user_friendly_error("Failed to initiate payment. Please try again later.", str(e))

@payfast_bp.route('/payfast/callback', methods=['POST'])
def payfast_callback():
    try:
        post_data = request.form.to_dict()
        logging.info(f"PayFast callback received: {post_data}")

        if not post_data:
            return user_friendly_error("No callback data received from PayFast.")

        received_signature = post_data.get('signature', '')
        valid_signature = generate_signature(post_data, PAYFAST_PASSPHRASE)
        if not received_signature:
            return user_friendly_error("No signature received in callback.")
        if received_signature != valid_signature:
            logging.warning(f"Signature mismatch: received={received_signature}, expected={valid_signature}")
            return user_friendly_error("Payment verification failed. Invalid signature received.")

        # TODO: Update order status in your database here
        # Example:
        # order_id = post_data.get('m_payment_id')
        # payment_status = post_data.get('payment_status')
        # logging.info(f"Update order {order_id} status to {payment_status}")
        # ...update order in DB...

        return jsonify({'success': True, 'message': 'Callback received and signature validated'}), 200
    except Exception as e:
        return user_friendly_error("Failed to process payment callback. Please contact support.", str(e))
