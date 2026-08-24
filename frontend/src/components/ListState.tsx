import { ReactNode } from 'react';

/**
 * 统一的列表加载/错误态：loading/error 优先于 children。
 * 传入 onRetry 时错误态附带重试按钮。
 */
export function ListState({
  loading,
  error,
  onRetry,
  children,
}: {
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
  children: ReactNode;
}) {
  if (loading) return <p className="hint list-state">加载中…</p>;
  if (error) {
    return (
      <div className="list-state">
        <p className="error-line">加载失败：{error}</p>
        {onRetry && (
          <button className="secondary" type="button" onClick={onRetry}>
            重试
          </button>
        )}
      </div>
    );
  }
  return <>{children}</>;
}

/** 空态：区分「过滤后空」（给清除筛选 CTA）与「真空」（给创建引导文案）。 */
export function EmptyState({
  filtered,
  onClearFilters,
  children,
}: {
  filtered: boolean;
  onClearFilters?: () => void;
  children: ReactNode;
}) {
  return (
    <div className="empty-state">
      <p className="empty">{children}</p>
      {filtered && onClearFilters && (
        <button className="secondary" type="button" onClick={onClearFilters}>
          清除筛选
        </button>
      )}
    </div>
  );
}
