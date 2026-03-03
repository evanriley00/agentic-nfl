import math

def calculator(expression: str) -> float:
    """
    Safe-ish calculator: supports numbers + basic math functions.
    Example: "2 + 2", "sqrt(9) + 1"
    """
    allowed = {
        "sqrt": math.sqrt,
        "pow": pow,
        "abs": abs,
        "round": round,
        "pi": math.pi,
        "e": math.e,
    }

    # VERY restricted eval environment
    return float(eval(expression, {"__builtins__": {}}, allowed))