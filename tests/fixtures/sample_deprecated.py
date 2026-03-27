"""Sample Python file with various deprecation patterns for testing.

This file contains:
- Functions decorated with @deprecated (from the deprecated package simulation)
- A class with a custom abc-deprecated-like decorator
- Functions with docstring-level .. deprecated:: directives
"""

# Stub for the 'deprecated' package's @deprecated decorator
# This mimics the interface: @deprecated(version=None, reason=None, msg=None)
def deprecated(version=None, reason=None, msg=None):
    """Mark a function/class as deprecated."""
    def decorator(func):
        return func
    return decorator


# Stub for abc.deprecated (simulated - not in stdlib)
class _abc:
    @staticmethod
    def deprecated(msg=None):
        """Simulated abc.deprecated decorator."""
        def decorator(func):
            return func
        return decorator

abc = _abc()


# --- Decorator-based deprecations ---


@deprecated(reason="Use new_function instead")
def old_func_with_reason():
    """Old function using @deprecated decorator with reason."""
    return "old"


@deprecated(version="1.5", reason="Use new_versioned_function instead")
def versioned_deprecated():
    """Function with version and reason in decorator."""
    return "old versioned"


@deprecated(msg="version 2.0: Use new_msg_function instead")
def msg_style_deprecated():
    """Function deprecated using msg parameter style."""
    return "old msg style"


@abc.deprecated("Use NewClass instead")
class OldClass:
    """A deprecated class using @abc.deprecated."""

    def old_method(self):
        """An old method."""
        pass


# --- Docstring-based deprecations (reStructuredText) ---


def docstring_deprecated_func():
    """Summary line.

    .. deprecated:: 2.0
       Use replacement_func instead.
       This function will be removed in version 3.0.
    """
    return "deprecated via docstring"


def docstring_since_deprecated():
    """Function deprecated using since syntax.

    .. deprecated since: 1.8
       Use new_function instead.
    """
    return "deprecated via docstring since"


class ClassWithDocstringDeprecation:
    """A class with deprecated methods.

    .. deprecated:: 1.10
       Migrate to NewClass.
    """

    def deprecated_method(self):
        """Method with docstring deprecation.

        .. deprecated:: 1.9
           Use new_method instead.
        """
        pass

    def normal_method(self):
        """A regular non-deprecated method."""
        return "normal"


def reason_only_deprecated():
    """Function with only a reason in docstring.

    .. deprecated::
       This function is no longer supported.
    """
    return "reason only"


# --- Non-deprecated (controls) ---


class NonDeprecatedClass:
    """This class should not produce any deprecation facts."""

    def method(self):
        """A regular method."""
        pass


def no_deprecation():
    """A completely normal function with no deprecation markers."""
    return "normal"


async def async_deprecated():
    """An async function that is deprecated.

    .. deprecated:: 1.6
       Use async_replacement instead.
    """
    return "async deprecated"


class SubClass(OldClass):
    """A subclass of a deprecated class."""

    pass
