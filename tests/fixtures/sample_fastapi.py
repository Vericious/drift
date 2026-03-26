"""Sample FastAPI application for testing the FastAPIRoutesExtractor."""
from fastapi import FastAPI, APIRouter, Query, Path, Body, HTTPException, status
from pydantic import BaseModel
from typing import Annotated

app = FastAPI(title="Sample API", version="1.0.0")
router = APIRouter(prefix="/api/v1", tags=["items"])
users_router = APIRouter(prefix="/users", tags=["users"])


# ─── FastAPI HTTP method shortcuts ───────────────────────────────────────────

@app.get("/")
def root():
    """Root endpoint."""
    return {"message": "Hello, World!"}


@app.get("/items", response_model=list[dict], tags=["items"])
def list_items():
    """List all items."""
    return []


@app.post("/items", status_code=status.HTTP_201_CREATED, response_model=dict, tags=["items"])
def create_item(name: str, price: float):
    """Create a new item."""
    return {"name": name, "price": price}


@app.get("/items/{item_id}", response_model=dict, tags=["items"])
def get_item(item_id: int):
    """Get a specific item by ID."""
    return {"item_id": item_id}


@app.put("/items/{item_id}", response_model=dict, tags=["items"])
def update_item(item_id: int, name: str = None):
    """Update an item."""
    return {"item_id": item_id, "name": name}


@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["items"])
def delete_item(item_id: int):
    """Delete an item."""
    return None


@app.patch("/items/{item_id}/price", response_model=dict, tags=["items"])
def patch_item_price(item_id: int, price: float):
    """Patch item price."""
    return {"item_id": item_id, "price": price}


# ─── APIRouter routes ────────────────────────────────────────────────────────

@router.get("/posts", response_model=list[dict])
def list_posts(skip: int = 0, limit: int = 10):
    """List posts with pagination."""
    return []


@router.post("/posts", status_code=status.HTTP_201_CREATED, response_model=dict)
def create_post(title: str, content: str):
    """Create a new post."""
    return {"title": title, "content": content}


@router.get("/posts/{post_id}", response_model=dict)
def get_post(post_id: int):
    """Get a specific post."""
    return {"post_id": post_id}


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: int):
    """Delete a post."""
    return None


# ─── Users router ────────────────────────────────────────────────────────────

@users_router.get("/", response_model=list[dict])
def list_users():
    """List all users."""
    return []


@users_router.get("/{user_id}", response_model=dict)
def get_user(user_id: int):
    """Get a specific user."""
    return {"user_id": user_id}


@users_router.post("/", status_code=status.HTTP_201_CREATED, response_model=dict)
def create_user(name: str, email: str):
    """Create a new user."""
    return {"name": name, "email": email}


# ─── Annotated style parameters ──────────────────────────────────────────────

@router.get("/search", response_model=list[dict])
def search_items(q: Annotated[str, Query(min_length=1)], limit: Annotated[int, Query(le=100)] = 10):
    """Search items with typed query params."""
    return []


@router.get("/items/{item_id}/detail", response_model=dict)
def get_item_detail(item_id: Annotated[int, Path(gt=0)], include_meta: Annotated[bool, Query()] = False):
    """Get item detail with typed path and query params."""
    return {"item_id": item_id, "include_meta": include_meta}


# ─── api_route style ────────────────────────────────────────────────────────

@app.api_route("/ping", methods=["GET"], tags=["health"])
def ping():
    """Health check."""
    return {"pong": True}


@app.api_route("/legacy", methods=["GET", "POST"], tags=["legacy"])
def legacy_endpoint():
    """Legacy endpoint supporting GET and POST."""
    return {"action": "legacy"}


# ─── Second FastAPI app ──────────────────────────────────────────────────────

admin_app = FastAPI(title="Admin API")


@admin_app.get("/admin/dashboard", response_model=dict, tags=["admin"])
def admin_dashboard():
    """Admin dashboard."""
    return {"stats": {}}


@admin_app.post("/admin/purge", status_code=status.HTTP_204_NO_CONTENT, tags=["admin"])
def purge_cache():
    """Purge all caches."""
    return None


# ─── Item model for body params ─────────────────────────────────────────────

class Item(BaseModel):
    name: str
    price: float


@router.post("/items/model", response_model=dict)
def create_item_model(item: Item):
    """Create item using a Pydantic model as body."""
    return item.dict()
