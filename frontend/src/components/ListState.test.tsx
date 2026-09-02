import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { EmptyState, ListState } from './ListState';

describe('ListState', () => {
  it('shows loading before children', () => {
    render(
      <ListState loading error={null}>
        <p>Loaded content</p>
      </ListState>,
    );

    expect(screen.getByText('加载中…')).toBeInTheDocument();
    expect(screen.queryByText('Loaded content')).not.toBeInTheDocument();
  });

  it('shows errors with retry action', () => {
    const retry = vi.fn();
    render(
      <ListState loading={false} error="network" onRetry={retry}>
        <p>Loaded content</p>
      </ListState>,
    );

    expect(screen.getByText('加载失败：network')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(retry).toHaveBeenCalledTimes(1);
  });
});

describe('EmptyState', () => {
  it('offers clearing filters only for filtered empty results', () => {
    const clear = vi.fn();
    render(
      <EmptyState filtered onClearFilters={clear}>
        No matching items
      </EmptyState>,
    );

    fireEvent.click(screen.getByRole('button', { name: '清除筛选' }));
    expect(clear).toHaveBeenCalledTimes(1);
  });
});
