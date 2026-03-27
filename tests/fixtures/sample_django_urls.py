"""Sample Django URL patterns for testing the extractor.

Contains various Django URL pattern styles:
- path() with URL converters
- url() with regex
- include() for nested URLs
"""

from django.urls import include, path, url
from .views import (
    home_view,
    user_detail,
    user_list,
    user_create,
    user_delete,
    post_detail,
    post_list,
    post_create,
    category_posts,
    tag_posts,
    api_health,
    api_items,
    api_item_detail,
)

# Main URL patterns
urlpatterns = [
    # Basic path() usage
    path("", home_view, name="home"),
    path("users/", user_list, name="user_list"),
    path("users/<int:user_id>/", user_detail, name="user_detail"),
    path("users/create/", user_create, name="user_create"),
    path("users/<int:user_id>/delete/", user_delete, name="user_delete"),
    
    # path() with different converters
    path("posts/", post_list, name="post_list"),
    path("posts/<int:post_id>/", post_detail, name="post_detail"),
    path("posts/create/", post_create, name="post_create"),
    path("posts/<slug:category>/", category_posts, name="category_posts"),
    path("tags/<slug:tag>/", tag_posts, name="tag_posts"),
    
    # Regex patterns with url()
    url(r"^api/health/$", api_health, name="api_health"),
    url(r"^api/items/$", api_items, name="api_items"),
    url(r"^api/items/(?P<item_id>\d+)/$", api_item_detail, name="api_item_detail"),
    
    # Nested URLs with include
    path("blog/", include("blog.urls")),
]

# blog/urls.py equivalent (simulated as a second urlpatterns)
blog_urlpatterns = [
    path("", blog_home, name="blog_home"),
    path("archive/", blog_archive, name="blog_archive"),
    path("<int:year>/<int:month>/", blog_month_archive, name="blog_month_archive"),
]
