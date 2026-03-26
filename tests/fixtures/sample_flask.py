"""Sample Flask application for testing the FlaskRoutesExtractor."""

from flask import Blueprint, Flask, jsonify

app = Flask(__name__)

# ─── Basic route ────────────────────────────────────────────────────────────


@app.route("/")
def index():
    """Home page."""
    return "Hello, World!"


# ─── HTTP method variants ───────────────────────────────────────────────────


@app.route("/users", methods=["GET", "POST"])
def users():
    """List or create users."""
    return jsonify({"action": "list_or_create"})


@app.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    """Get a specific user."""
    return jsonify({"user_id": user_id})


@app.route("/users/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    """Update a user."""
    return jsonify({"user_id": user_id, "action": "update"})


@app.route("/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    """Delete a user."""
    return jsonify({"user_id": user_id, "action": "delete"})


# ─── Flask 2.0+ shortcut decorators ─────────────────────────────────────────


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


@app.post("/api/items")
def create_item():
    """Create an item."""
    return jsonify({"action": "create_item"})


@app.put("/api/items/<item_id>")
def update_item(item_id):
    """Update an item."""
    return jsonify({"item_id": item_id})


@app.patch("/api/items/<item_id>")
def patch_item(item_id):
    """Patch an item."""
    return jsonify({"item_id": item_id})


@app.delete("/api/items/<item_id>")
def delete_item(item_id):
    """Delete an item."""
    return jsonify({"item_id": item_id})


# ─── Blueprint routes ───────────────────────────────────────────────────────

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


@api_bp.route("/posts", methods=["GET"])
def list_posts():
    """List all posts."""
    return jsonify([])


@api_bp.route("/posts", methods=["POST"])
def create_post():
    """Create a new post."""
    return jsonify({"action": "create_post"})


@api_bp.route("/posts/<int:post_id>", methods=["GET"])
def get_post(post_id):
    """Get a specific post."""
    return jsonify({"post_id": post_id})


@api_bp.route("/posts/<int:post_id>", methods=["PUT"])
def put_post(post_id):
    """Full update of a post."""
    return jsonify({"post_id": post_id})


@api_bp.route("/posts/<int:post_id>", methods=["DELETE"])
def remove_post(post_id):
    """Delete a post."""
    return jsonify({"post_id": post_id})


# ─── Blueprint with Flask 2.0+ shortcuts ───────────────────────────────────

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.get("/login")
def login_page():
    """Render login page."""
    return "Login"


@auth_bp.post("/login")
def do_login():
    """Perform login action."""
    return jsonify({"action": "login"})


@auth_bp.post("/logout")
def do_logout():
    """Perform logout action."""
    return jsonify({"action": "logout"})


@auth_bp.get("/register")
def register_page():
    """Render registration page."""
    return "Register"


# ─── Third Blueprint ─────────────────────────────────────────────────────────

utility_bp = Blueprint("utility", __name__, url_prefix="/utility")


@utility_bp.get("/ping")
def ping():
    """Health ping endpoint."""
    return jsonify({"pong": True})


@utility_bp.post("/reset")
def reset():
    """Reset endpoint."""
    return jsonify({"action": "reset"})


# ─── Another app instance ───────────────────────────────────────────────────

other_app = Flask("other")


@other_app.route("/hello")
def hello():
    return "Hello from other app"


@other_app.get("/status")
def status():
    return jsonify({"status": "fine"})
