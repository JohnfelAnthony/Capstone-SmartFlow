---
name: rl-agent-tuning
description: Best practices and validation workflows for reinforcement learning traffic signal controllers in SmartFlow (QL, DQL, PPO). Use when modifying reward functions, observations, training loops, model contracts or controller evaluation.
---

# RL Agent Tuning (`rl-agent-tuning`)

Standard operating procedures for training and evaluating reinforcement learning models controlling SmartFlow traffic junctions.

## Core Rules

1. **Junction Scope & Contracts**:
   - RL controls one selected junction; routing is a separate graph algorithm. Do not claim coordinated control of the whole network.
   - Maintain the `engine_config` scenario contract across all training runs and benchmark evaluations.
   - `native_contract()` in `simulation/model_contract.py` ties a model to the engine version, observation version, action set and road-network fingerprint. A model with a different contract is rejected: train a new one instead of relabelling an old artifact.

2. **Reward Function Design**:
   - `calculate_reward` in `simulation/rl_reward.py` scores only the controlled junction over the last decision interval: a bonus for vehicles discharged, penalties for stopped vehicle-seconds, the longest approach queue, waiting pedestrians and phase switches.
   - Normalisation scales come from `simulation/rl_state.py`.
   - A reward change bumps `REWARD_VERSION` in `rl_reward.py`. An observation change bumps the observation version in `native_contract()` and the `obs_v2` labels in the DQL, PPO and QL training code.

3. **Evaluation Protocol**:
   - Compare each trained policy with the `fixed-time` controller on the same scenarios, using held-out seeds that were not used in training.
   - `tools/evaluate_controllers.py` defaults to seeds 11, 22, 33, 44, 55, which are also the training scripts' default seeds. Pass held-out seeds with `--seeds`.
   - Report the controlled junction and the whole network, including unfinished vehicles and pedestrian wait, not only mean wait.
   - The app applies DQL and PPO's own action through the engine's safety layer, exactly as training does; QL is masked in both. Keep the two paths the same.

4. **Training Cost and Artifacts**:
   - Defaults (560 episodes of 900 s after a 300 s warmup, about 100,000 decisions) are defined once in `simulation/rl_env.py`. One default run took about 3.5–5.5 hours per algorithm on this laptop in October 2026.
   - Models are saved under `data/models/{ql,dql,ppo}/` with their metadata. Results on synthetic demand or a provisional network are pipeline evidence, not study results.

## Quick Checks

- Validate the training pipeline before starting full episode runs:
  ```powershell
  .venv\Scripts\python.exe -m pytest tests/test_reward_v3.py tests/test_rl_runtime_parity.py tests/test_training_budget.py tests/test_native_learning.py -q -p no:cacheprovider --basetemp <scratch folder>
  ```
- Train each algorithm for 2 episodes (`tools/train_ql.py`, `tools/train_dql.py`, `tools/train_ppo.py` with `--episodes 2`) and evaluate it against `fixed-time` before a full run. Those scores are not results.
