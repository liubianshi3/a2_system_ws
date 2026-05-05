from .utils import load_yaml_file


def load_goals(path, first_goal_only=False):
    data = load_yaml_file(path)
    frame_id = data.get("frame_id")
    if not frame_id:
        raise ValueError(f"goals YAML must define frame_id: {path}")
    goals = data.get("goals")
    if not isinstance(goals, list) or not goals:
        raise ValueError(f"goals YAML must contain a non-empty goals list: {path}")

    normalized = []
    seen_ids = set()
    for idx, goal in enumerate(goals):
        if not isinstance(goal, dict):
            raise ValueError(f"goal #{idx + 1} must be a mapping")
        goal_id = goal.get("id", goal.get("goal_id"))
        if not goal_id:
            raise ValueError(f"goal #{idx + 1} must contain id")
        if goal_id in seen_ids:
            raise ValueError(f"duplicate goal id: {goal_id}")
        seen_ids.add(goal_id)
        for key in ("x", "y", "yaw"):
            if key not in goal:
                raise ValueError(f"goal {goal_id} must contain {key}")
        try:
            normalized.append(
                {
                    "id": str(goal_id),
                    "goal_id": str(goal_id),
                    "x": float(goal["x"]),
                    "y": float(goal["y"]),
                    "yaw": float(goal["yaw"]),
                    "frame_id": str(goal.get("frame_id", frame_id)),
                }
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"goal {goal_id} has non-numeric x/y/yaw") from exc

    if first_goal_only:
        return normalized[:1]
    return normalized
