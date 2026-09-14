# SMARTFLOW RL Training Reliability

This note documents the practical training workflow for QL, DQL, and PPO after checkpointing and resume support.

## Checkpoints

QL, DQL, and PPO training CLIs support:

```powershell
--checkpoint-every 25
--resume-model path
```

Checkpoints are saved under the model output directory:

```text
data/models/ql/checkpoints/
data/models/dql/checkpoints/
data/models/ppo/checkpoints/
```

QL checkpoints are JSON Q-table artifacts. DQL and PPO checkpoints are Stable-Baselines3 `.zip` artifacts with matching `.metadata.json` sidecars.

When resuming, `--episodes` means additional training episodes for that command.

## Graceful Interrupts

Pressing `Ctrl+C` during QL, DQL, or PPO training now attempts to save:

- partial model artifact
- metadata
- DB checkpoint when DB registration is enabled

The process exits with code `130` after saving the partial artifact.

## Recommended Training Sizes

Quick laptop run:

```powershell
.venv\Scripts\python.exe tools\train_ql.py --episodes 150 --traffic-density low --checkpoint-every 25
.venv\Scripts\python.exe tools\train_dql.py --episodes 150 --traffic-density low --checkpoint-every 25
.venv\Scripts\python.exe tools\train_ppo.py --episodes 150 --traffic-density low --checkpoint-every 25
```

Use 150-200 episodes when you need a practical local run that finishes in a reasonable time.

Stronger run:

```powershell
.venv\Scripts\python.exe tools\train_ql.py --episodes 500 --traffic-density low --checkpoint-every 25
.venv\Scripts\python.exe tools\train_dql.py --episodes 500 --traffic-density low --checkpoint-every 25
.venv\Scripts\python.exe tools\train_ppo.py --episodes 500 --traffic-density low --checkpoint-every 25
```

Use 500+ episodes when you want a stronger model and can leave the laptop running.

## Evaluation Recommendation

Evaluate low and medium traffic separately. Do not mix densities in one headline comparison.

Recommended low-density evaluation:

```powershell
.venv\Scripts\python.exe tools\evaluate_controllers.py --controllers fixed-time,ql,dql,ppo --seeds 11,22,33,44,55 --duration-seconds 300 --warmup-seconds 20 --intersection-id tagum_1 --traffic-density low --pedestrian-density medium --emergency-mode disabled --road-constraint None --record-timeline-seed 11
```

Recommended medium-density evaluation:

```powershell
.venv\Scripts\python.exe tools\evaluate_controllers.py --controllers fixed-time,ql,dql,ppo --seeds 11,22,33,44,55 --duration-seconds 300 --warmup-seconds 20 --intersection-id tagum_1 --traffic-density medium --pedestrian-density medium --emergency-mode disabled --road-constraint None --record-timeline-seed 11
```

If a low-density model performs badly on medium density, that is expected. Treat each density as its own training and evaluation protocol until we deliberately implement mixed-density curriculum training.
