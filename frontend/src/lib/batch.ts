/** 逐条顺序执行批量动作（乐观锁要求逐条带版本），收集成功/失败。 */
export async function runBatchSequential<T>(
  items: T[],
  fn: (item: T) => Promise<unknown>,
): Promise<{ succeeded: T[]; failed: T[] }> {
  const succeeded: T[] = [];
  const failed: T[] = [];
  for (const item of items) {
    try {
      await fn(item);
      succeeded.push(item);
    } catch {
      failed.push(item);
    }
  }
  return { succeeded, failed };
}
