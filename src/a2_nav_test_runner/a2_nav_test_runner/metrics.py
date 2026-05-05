from .utils import as_float_or_none, mean, stddev


def pose_error(goal, final_pose):
    dx = float(goal["x"]) - float(final_pose[0])
    dy = float(goal["y"]) - float(final_pose[1])
    return (dx * dx + dy * dy) ** 0.5


def compute_summary(log_rows):
    rows = list(log_rows or [])
    if not rows:
        return None

    total_goals = len(rows)
    successes = [row for row in rows if truthy(row.get("success"))]
    failures = [row for row in rows if not truthy(row.get("success"))]
    backend_successes = [row for row in rows if truthy(row.get("backend_success"))]
    runner_arrivals = [row for row in rows if truthy(row.get("runner_arrival_success"))]
    durations = [
        value
        for value in (as_float_or_none(row.get("duration")) for row in successes)
        if value is not None
    ]
    final_errors = field_values(rows, "final_error")
    timeouts = [row for row in rows if truthy(row.get("timeout"))]
    backend = rows[0].get("backend", "") if rows else ""

    return {
        "backend": backend,
        "run_count": len({row.get("run_id") for row in rows}),
        "total_goals": total_goals,
        "success_count": len(successes),
        "success_rate": len(successes) / total_goals if total_goals else 0.0,
        "backend_success_rate": len(backend_successes) / total_goals if total_goals else 0.0,
        "runner_arrival_success_rate": len(runner_arrivals) / total_goals if total_goals else 0.0,
        "total_navigation_time": sum(durations),
        "average_navigation_time": sum(durations) / len(durations) if durations else "",
        "average_final_error": sum(final_errors) / len(final_errors) if final_errors else "",
        "mean_final_error_amcl": field_mean(rows, "final_error_amcl"),
        "mean_final_error_odom": field_mean(rows, "final_error_odom"),
        "mean_final_error_tf_map_base_link": field_mean(rows, "final_error_tf_map_base_link"),
        "mean_final_error_tf_map_base_footprint": field_mean(rows, "final_error_tf_map_base_footprint"),
        "max_final_error_tf_map_base_link": field_max(rows, "final_error_tf_map_base_link"),
        "std_final_error_tf_map_base_link": field_std(rows, "final_error_tf_map_base_link"),
        "mean_yaw_error_tf_map_base_link": field_mean(rows, "yaw_error_tf_map_base_link"),
        "failed_goals": ",".join(str(row.get("goal_id", "")) for row in failures),
        "timeout_count": len(timeouts),
    }


def truthy(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "success", "succeeded"}
    return False


def field_values(rows, key):
    return [
        value
        for value in (as_float_or_none(row.get(key)) for row in rows)
        if value is not None
    ]


def field_mean(rows, key):
    values = field_values(rows, key)
    return mean(values) if values else ""


def field_std(rows, key):
    values = field_values(rows, key)
    return stddev(values) if values else ""


def field_max(rows, key):
    values = field_values(rows, key)
    return max(values) if values else ""
