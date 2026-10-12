---
name: rl-agent-tuning
description: Best practices and validation workflows for reinforcement learning traffic signal controllers in SmartFlow. Use when modifying reward functions, state observations, DQN/PPO training loops, or junction evaluation metrics.
---

# RL Agent Tuning (`rl-agent-tuning`)

Standard operating procedures for training and evaluating reinforcement learning models controlling SmartFlow traffic junctions.

## Core Rules

1. **Junction Scope & Contracts**:
   - RL agents currently target single-junction signal timing policies.
   - Maintain the `engine_config` scenario contract across all training runs and benchmark evaluations.

2. **Reward Function Design**:
   - Reward definitions must penalize cumulative waiting time and queue length while rewarding throughput (cleared vehicles per cycle).
   - Avoid excessive reward oscillation: clip or normalize reward increments across varying traffic density levels.

3. **Evaluation Protocol**:
   - Compare trained policies directly against Fixed-Time and Actuated baseline controllers under identical seed distributions.
   - Save model checkpoints with clear version tags and associated configuration JSONs in the artifacts directory.

## Quick Checks

- Validate the training pipeline before starting full episode runs:
  ```powershell
  .venv\Scripts\python.exe -m pytest tests/test_rl_agent.py
  ```
- Ensure evaluation metrics report average delay (s/veh), total throughput, and queue length.
