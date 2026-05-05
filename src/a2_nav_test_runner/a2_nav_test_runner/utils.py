import math
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import rclpy
from rcl_interfaces.msg import ParameterType
from rcl_interfaces.srv import GetParameters, ListParameters
import yaml


def load_yaml_file(path: str) -> Dict[str, Any]:
    yaml_path = Path(os.path.expanduser(path)).resolve()
    if not yaml_path.exists():
        raise FileNotFoundError(f"YAML file does not exist: {yaml_path}")
    with yaml_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {yaml_path}")
    return data


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    raise ValueError(f"Cannot parse boolean value: {value!r}")


def normalize_name(name: str) -> str:
    if not name:
        return "/"
    return name if name.startswith("/") else f"/{name}"


def now_time() -> float:
    return time.time()


def yaw_to_quaternion(yaw: float):
    half = float(yaw) * 0.5
    return {
        "x": 0.0,
        "y": 0.0,
        "z": math.sin(half),
        "w": math.cos(half),
    }


def bool_to_csv(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).lower() if value is not None else ""


def as_float_or_none(value: Any):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def timestamp_compact() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dir(path: str) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def latest_matching_file(results_dir: str, pattern: str) -> Optional[Path]:
    directory = Path(results_dir)
    matches = sorted(directory.glob(pattern))
    return matches[-1] if matches else None


def yaw_from_quaternion(q) -> float:
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


def normalize_angle(angle: float) -> float:
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def stddev(values: Iterable[float]) -> Optional[float]:
    numbers = [float(v) for v in values]
    if not numbers:
        return None
    mean = sum(numbers) / len(numbers)
    variance = sum((value - mean) ** 2 for value in numbers) / len(numbers)
    return math.sqrt(variance)


def mean(values: Iterable[float]) -> Optional[float]:
    numbers = [float(v) for v in values]
    if not numbers:
        return None
    return sum(numbers) / len(numbers)


def wait_future(node, future, timeout_sec: float) -> bool:
    rclpy.spin_until_future_complete(node, future, timeout_sec=max(0.0, float(timeout_sec)))
    return future.done()


def parameter_value_to_python(value) -> Any:
    kind = value.type
    if kind == ParameterType.PARAMETER_BOOL:
        return value.bool_value
    if kind == ParameterType.PARAMETER_INTEGER:
        return value.integer_value
    if kind == ParameterType.PARAMETER_DOUBLE:
        return value.double_value
    if kind == ParameterType.PARAMETER_STRING:
        return value.string_value
    if kind == ParameterType.PARAMETER_BYTE_ARRAY:
        return list(value.byte_array_value)
    if kind == ParameterType.PARAMETER_BOOL_ARRAY:
        return list(value.bool_array_value)
    if kind == ParameterType.PARAMETER_INTEGER_ARRAY:
        return list(value.integer_array_value)
    if kind == ParameterType.PARAMETER_DOUBLE_ARRAY:
        return list(value.double_array_value)
    if kind == ParameterType.PARAMETER_STRING_ARRAY:
        return list(value.string_array_value)
    return None


def fully_qualified_node_name(namespace: str, name: str) -> str:
    namespace = namespace or "/"
    if namespace == "/":
        return f"/{name}"
    return f"{namespace.rstrip('/')}/{name}"


def discover_nodes(node) -> List[Tuple[str, str, str]]:
    entries = []
    for name, namespace in node.get_node_names_and_namespaces():
        full_name = fully_qualified_node_name(namespace, name)
        entries.append((name, namespace, full_name))
    return entries


def list_node_parameters(node, remote_node_name: str, timeout_sec: float = 3.0) -> Tuple[List[str], Optional[str]]:
    service_name = f"{normalize_name(remote_node_name)}/list_parameters"
    client = node.create_client(ListParameters, service_name)
    if not client.wait_for_service(timeout_sec=timeout_sec):
        return [], f"parameter service not ready for {remote_node_name}"
    request = ListParameters.Request()
    request.prefixes = []
    request.depth = 100
    future = client.call_async(request)
    if not wait_future(node, future, timeout_sec):
        return [], f"list_parameters timeout for {remote_node_name}"
    try:
        result = future.result()
        return sorted(result.result.names), None
    except Exception as exc:
        return [], f"list_parameters failed for {remote_node_name}: {exc}"


def get_node_parameters(node, remote_node_name: str, parameter_names: List[str], timeout_sec: float = 3.0):
    if not parameter_names:
        return {}, None
    service_name = f"{normalize_name(remote_node_name)}/get_parameters"
    client = node.create_client(GetParameters, service_name)
    if not client.wait_for_service(timeout_sec=timeout_sec):
        return {}, f"parameter service not ready for {remote_node_name}"
    request = GetParameters.Request()
    request.names = list(parameter_names)
    future = client.call_async(request)
    if not wait_future(node, future, timeout_sec):
        return {}, f"get_parameters timeout for {remote_node_name}"
    try:
        values = future.result().values
    except Exception as exc:
        return {}, f"get_parameters failed for {remote_node_name}: {exc}"
    return {
        name: parameter_value_to_python(value)
        for name, value in zip(parameter_names, values)
    }, None


def write_markdown(path: str, lines: List[str]) -> str:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(output)
