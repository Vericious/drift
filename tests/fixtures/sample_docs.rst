Sample Sphinx Documentation
===========================

This file contains sample RST documentation for testing the RST extractor.

.. py:function:: greet(name: str, greeting: str = "Hello") -> str

   A simple greeting function.

   :param name: The name of the person to greet.
   :type name: str
   :param greeting: The greeting word to use.
   :type greeting: str
   :returns: The formatted greeting string.
   :rtype: str


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
