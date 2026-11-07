"""Keep the study's final random seeds out of training and development."""

FINAL_EVALUATION_SEEDS = range(201, 221)


def validate_study_seeds(seeds, *, final=False):
    if not final and any(int(seed) in FINAL_EVALUATION_SEEDS for seed in seeds):
        raise ValueError(
            "Seeds 201–220 are reserved for the final evaluation (Task 29). "
            "Use different seeds for training and development, or --final for final evaluation."
        )
