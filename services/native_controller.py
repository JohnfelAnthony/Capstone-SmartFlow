"""Resolve only registered, compatible policies for hosted experiments."""
import database


def apply_controller(engine, control_mode: str | None):
    mode = str(control_mode or "fixed-time").strip().lower().replace("_", "-")
    if mode in {"fixed-time", "fixed"}:
        engine.disable_rl_control()
        return "fixed-time"
    algorithm, separator, model_id = mode.partition(":")
    if algorithm not in {"ql", "dql", "ppo"} or not separator or not model_id.isdigit():
        raise ValueError("Use fixed-time or ql:<model_id>, dql:<model_id>, ppo:<model_id> with a registered native policy")
    record = database.get_rl_model_by_id(int(model_id))
    if not record or str(record["algorithm"]).lower() != algorithm or not record.get("checkpoint_path"):
        raise ValueError("Registered model not found or algorithm mismatch")
    from simulation.rl_policy_runtime import load_runtime_policy
    policy = load_runtime_policy(algorithm, record["checkpoint_path"])
    policy.artifact_metadata["model_id"] = int(model_id)
    engine.set_runtime_policy(policy)
    return mode
