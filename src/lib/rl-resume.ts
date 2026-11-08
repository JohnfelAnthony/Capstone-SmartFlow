/** Whether the chosen resume target can run: the selected checkpoint if there is one, otherwise the final model artifact. */
export function resumeTargetCompatible(
  model: { compatible: boolean; checkpoints: Array<{ id: number; compatible: boolean }> } | null | undefined,
  checkpointId: number | null,
): boolean {
  if (!model) return false
  const checkpoint = model.checkpoints.find((item) => item.id === checkpointId)
  return checkpoint ? checkpoint.compatible : model.compatible
}
