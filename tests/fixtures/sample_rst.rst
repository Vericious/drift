Sample Sphinx Documentation - Comprehensive
==============================================

This module demonstrates all supported RST patterns.

.. py:function:: greet(name: str, greeting: str = "Hello") -> str

   A simple greeting function.

   :param name: The name of the person to greet.
   :type name: str
   :param greeting: The greeting word to use.
   :type name: str
   :returns: The formatted greeting string.
   :rtype: str
   :raises ValueError: if name is empty.


.. py:function:: add(a: int, b: int) -> int

   Adds two numbers together.

   :param a: First integer.
   :type a: int
   :param b: Second integer.
   :type b: int
   :returns: The sum of a and b.
   :rtype: int


.. py:class:: User(name: str, email: str)

   Represents a user in the system.

   :param name: The user's full name.
   :type name: str
   :param email: The user's email address.
   :type email: str


.. py:method:: User.get_display_name() -> str

   Returns the user's display name.

   :returns: The display name.
   :rtype: str


.. py:method:: User.from_email(email: str) -> User

   Class method to create a User from an email address.

   :param email: The email address.
   :type email: str
   :returns: A new User instance.
   :rtype: User


.. py:function:: process_data(items: list, *, debug: bool = False) -> dict

   Process a list of items with optional debug mode.

   :param items: The items to process.
   :type items: list
   :param debug: Enable debug mode.
   :type debug: bool
   :returns: A dictionary with results.
   :rtype: dict


.. py:data:: MAX_SIZE : int

   Maximum size constant.


.. py:attribute:: User.id : int

   The user's unique identifier.


Code Examples
-------------

Here's how you might use the API:

.. code-block:: python

   user = User("Alice", "alice@example.com")
   print(user.get_display_name())

   greeting = greet("World")
   result = add(3, 4)


Another example with a literal block::

   def hello():
       print("Hello, world!")
   hello()


Edge Cases
----------

.. py:function:: no_params() -> None

   A function with no parameters.

   :returns: Nothing.
   :rtype: None


.. py:function:: varargs_func(*args, **kwargs)

   A function with variable arguments.

   :param args: Positional arguments.
   :param kwargs: Keyword arguments.


Cross-References
-----------------

See :func:`my_module.my_func` for details.

See :class:`package.MyClass` for the base class.

See :meth:`MyClass.do_something` for the method.

See :mod:`my_package` for an overview.

See :ref:`overview-label` for the big picture.

See :func:`Title <alt_func>` for an aliased reference.


References with explicit titles:

See `My Function <http://example.com>`_ for details.


See also: :func:`foo.bar`, :func:`baz.qux`, and :class:`Wiz`.


Automodule Examples
-------------------

.. automodule:: example_package
   :members:


.. automodule:: another_package

   exported_func
   exported_class


Field Lists Extended
--------------------

:orphan:

This file has many patterns. See :func:`greet`, :func:`add`.

.. note::
   This is a note block.

.. warning::
   This is a warning block.
