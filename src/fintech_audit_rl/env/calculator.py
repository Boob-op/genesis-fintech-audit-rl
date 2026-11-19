"""Bounded decimal arithmetic; no names, calls, attributes or files."""

import ast
from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext


def calculate(expression: str) -> str:
    if type(expression) is not str or not 1 <= len(expression) <= 128:
        raise ValueError("invalid calculator expression")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as error:
        raise ValueError("invalid calculator expression") from error
    if sum(1 for _ in ast.walk(tree)) > 64:
        raise ValueError("calculator expression too complex")

    def evaluate(node: ast.AST, depth: int = 0) -> Decimal:
        if depth > 16:
            raise ValueError("calculator expression too deep")
        if isinstance(node, ast.Expression):
            return evaluate(node.body, depth + 1)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = Decimal(str(node.value))
            if not value.is_finite():
                raise ValueError("nonfinite calculator number")
            return value
        if isinstance(node, ast.UnaryOp) and type(node.op) in (ast.UAdd, ast.USub):
            operand = evaluate(node.operand, depth + 1)
            return operand if isinstance(node.op, ast.UAdd) else -operand
        if isinstance(node, ast.BinOp) and type(node.op) in (ast.Add, ast.Sub, ast.Mult, ast.Div):
            left = evaluate(node.left, depth + 1)
            right = evaluate(node.right, depth + 1)
            try:
                with localcontext() as context:
                    context.prec = 28
                    if isinstance(node.op, ast.Add):
                        result = left + right
                    elif isinstance(node.op, ast.Sub):
                        result = left - right
                    elif isinstance(node.op, ast.Mult):
                        result = left * right
                    else:
                        result = left / right
            except (DivisionByZero, InvalidOperation, OverflowError) as error:
                raise ValueError("invalid calculator operation") from error
            if not result.is_finite() or abs(result) > Decimal("1e18"):
                raise ValueError("calculator result outside limit")
            return result
        raise ValueError("unsupported calculator expression")

    result = evaluate(tree)
    if abs(result) > Decimal("1e18"):
        raise ValueError("calculator result outside limit")
    return format(result.normalize(), "f")
