"""Tool argument validation against Python function signatures."""

import inspect
import logging
from typing import Any, get_args, get_origin

logger = logging.getLogger(__name__)

# Primitive types that can be coerced from JSON representations.
_COERCIBLE: dict[type, tuple[type, ...]] = {
    int: (float,),
    float: (int,),
    str: (),
    bool: (),
    list: (),
    dict: (),
}

_NoneType = type(None)


def _origin(annotation: Any) -> Any:
    return get_origin(annotation)


def _is_optional(annotation: Any) -> tuple[bool, Any]:
    """Return (is_optional, inner_type) for Optional[X] / X | None annotations."""
    if _origin(annotation) is type(None):
        return True, Any
    args = get_args(annotation)
    if not args:
        return False, annotation
    non_none = [a for a in args if a is not _NoneType]
    if len(non_none) < len(args):  # at least one None in union
        inner = non_none[0] if len(non_none) == 1 else annotation
        return True, inner
    return False, annotation


def _coerce_value(name: str, value: Any, annotation: Any, errors: list[str]) -> Any:
    """Attempt to coerce *value* to *annotation* type; record errors on failure."""
    if annotation is inspect.Parameter.empty or annotation is Any:
        return value

    optional, inner = _is_optional(annotation)
    if value is None:
        if optional:
            return None
        errors.append(f"'{name}': required (not None)")
        return value

    target_type = _origin(inner) or inner
    if target_type in (Any, inspect.Parameter.empty):
        return value

    if isinstance(value, target_type):
        return value

    # Try primitive coercion (e.g. JSON float 5.0 → int 5).
    if target_type in _COERCIBLE and type(value) in _COERCIBLE.get(target_type, ()):
        try:
            return target_type(value)
        except (ValueError, TypeError):
            pass

    errors.append(f"'{name}': expected {getattr(target_type, '__name__', target_type)}, got {type(value).__name__}")
    return value


def validate_tool_args(func: Any, args: dict[str, Any]) -> dict[str, Any]:
    """Validate and coerce *args* against *func*'s signature.

    Returns either a coerced args dict ready to be unpacked into the function,
    or a dict ``{"error": "..."}`` describing the first validation failure.
    """
    try:
        sig = inspect.signature(func)
    except (ValueError, TypeError) as exc:
        logger.warning("Could not inspect signature of %s: %s", func, exc)
        return args  # pass through unchanged if introspection fails

    errors: list[str] = []
    coerced: dict[str, Any] = {}

    for param_name, param in sig.parameters.items():
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue  # *args / **kwargs – skip

        if param_name in args:
            coerced[param_name] = _coerce_value(param_name, args[param_name], param.annotation, errors)
        elif param.default is not inspect.Parameter.empty:
            pass  # optional, use function default
        else:
            errors.append(f"'{param_name}': required parameter missing")

    # Flag unknown keys (typos from LLM).
    known = set(sig.parameters)
    for key in args:
        if key not in known:
            errors.append(f"'{key}': unknown parameter")

    if errors:
        return {"error": "Tool arg validation failed: " + "; ".join(errors)}

    return coerced
