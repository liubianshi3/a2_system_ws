TRUE_VALUES = {"1", "true", "yes", "on"}
VALID_RUNTIME_MODES = {"mock", "gazebo", "real"}


def as_bool(value):
    return str(value).strip().lower() in TRUE_VALUES


def normalize_runtime_mode(runtime_mode_value, use_mock_value="true"):
    runtime_mode = str(runtime_mode_value).strip().lower()
    if runtime_mode in VALID_RUNTIME_MODES:
        return runtime_mode
    return "mock" if as_bool(use_mock_value) else "real"


def is_simulated_mode(runtime_mode):
    return runtime_mode in {"mock", "gazebo"}


def use_sim_time_for_mode(runtime_mode):
    return runtime_mode == "gazebo"
