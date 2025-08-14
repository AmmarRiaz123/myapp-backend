import os
from flask import Flask
from flask_cors import CORS

# Import blueprints
from product_api import product_bp
from product_detail_api import product_detail_bp
from contact_api import contact_bp
from myip_api import my_ip
from auth.auth_routes import auth_bp


app = Flask(__name__)
CORS(app)

# Public endpoints (no auth required)
app.register_blueprint(product_bp)
app.register_blueprint(product_detail_bp)
app.register_blueprint(contact_bp)
app.register_blueprint(auth_bp, url_prefix='/auth')

# Register blueprints
app.add_url_rule('/myip', view_func=my_ip)

if __name__ == '__main__':
    app.run(
        debug=True,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
