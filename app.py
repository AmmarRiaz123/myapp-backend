import os
from flask import Flask
from flask_cors import CORS

# Import blueprints
from product_api import product_bp
from product_detail_api import product_detail_bp
from contact_api import contact_bp

app = Flask(__name__)
CORS(app)

# Register blueprints
app.register_blueprint(product_bp)
app.register_blueprint(product_detail_bp)
app.register_blueprint(contact_bp)

if __name__ == '__main__':
    app.run(
        debug=True,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
