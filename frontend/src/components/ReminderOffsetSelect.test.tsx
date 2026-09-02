import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ReminderOffsetSelect } from './ReminderOffsetSelect';

describe('ReminderOffsetSelect', () => {
  it('emits preset reminder offsets', () => {
    const onChange = vi.fn();
    render(<ReminderOffsetSelect value={0} onChange={onChange} />);

    fireEvent.change(screen.getByRole('combobox'), { target: { value: '60' } });

    expect(onChange).toHaveBeenCalledWith(60);
  });

  it('clamps custom reminder offsets to the backend limit', () => {
    const onChange = vi.fn();
    render(<ReminderOffsetSelect value={45} onChange={onChange} />);

    const input = screen.getByLabelText('自定义提醒分钟数');
    fireEvent.change(input, { target: { value: '999999' } });

    expect(onChange).toHaveBeenCalledWith(10080);
  });
});
