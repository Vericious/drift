"""Sample Python file with various decorator patterns for testing."""


def login_required(func):
    """Mark a route as requiring authentication."""
    return func


def cache(ttl=60):
    """Cache decorator with TTL support."""
    def decorator(func):
        return func
    return decorator


def deprecated(reason=None):
    """Mark a function as deprecated."""
    def decorator(func):
        return func
    return decorator


# Flask-style routing
class MockFlask:
    def route(self, path):
        """Route decorator."""
        def decorator(func):
            return func
        return decorator


app = MockFlask()


@app.route("/")
def index():
    """Home page."""
    return "index"


@login_required
def protected_page():
    """Protected route that requires login."""
    return "protected"


@cache(ttl=300)
def expensive_computation():
    """Result that can be cached for 5 minutes."""
    return 42


@deprecated("Use new_function instead")
def old_function():
    """Deprecated function."""
    pass


def rate_limit(max_calls=10):
    """Rate limiting decorator."""
    def decorator(func):
        return func
    return decorator


@rate_limit(max_calls=100)
def api_endpoint():
    """Rate-limited API endpoint."""
    return {"status": "ok"}


async def async_handler():
    """Async function without decorators."""
    return "async result"


@cache
def simple_cached():
    """Simple cached function (no arguments)."""
    return "cached"


class MyClass:
    @login_required
    def method(self):
        """A method requiring login."""
        pass

    @classmethod
    def class_method(cls):
        """A class method without decorators."""
        pass


def no_decorators():
    """Function with no decorators at all."""
    return "plain"
