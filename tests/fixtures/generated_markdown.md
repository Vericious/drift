# API Documentation

## User Management

### `greet(name: str, greeting: str = "Hello") -> str`

Greets a user with a custom greeting.

**Parameters:**
- `name` (str): The user's name
- `greeting` (str, optional): The greeting to use. Defaults to "Hello".

**Returns:**
- `str`: The formatted greeting string

**Example:**
```python
result = greet("Alice", "Hi")
# Returns: "Hi, Alice!"
```

### `process_data(data: list[int], multiplier: int = 1) -> list[int]`

Processes a list of integers by multiplying each element.

**Parameters:**
- `data` (list[int]): Input list of integers
- `multiplier` (int, optional): Factor to multiply by. Defaults to 1.

**Returns:**
- `list[int]`: Processed list of integers

## Calculator Class

### `class Calculator`

A simple calculator for basic arithmetic operations.

#### `Calculator.__init__(precision: int = 2)`

Initialize the calculator.

**Parameters:**
- `precision` (int): Number of decimal places for results. Defaults to 2.

#### `Calculator.add(a: float, b: float) -> float`

Add two numbers.

**Parameters:**
- `a` (float): First operand
- `b` (float): Second operand

**Returns:**
- `float`: Sum of a and b

#### `Calculator.multiply(a: float, b: float) -> float`

Multiply two numbers.

**Parameters:**
- `a` (float): First operand
- `b` (float): Second operand

**Returns:**
- `float`: Product of a and b
