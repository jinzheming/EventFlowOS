import { useState } from 'react';
import { reminderOffsets } from '../lib/labels';

const CUSTOM = 'custom';
const MAX_OFFSET_MINUTES = 10080; // 与后端 ReminderPut.offset_minutes 上限一致（7 天）

function clampMinutes(value: number) {
  if (!Number.isFinite(value)) return 1;
  return Math.max(1, Math.min(MAX_OFFSET_MINUTES, Math.round(value)));
}

/**
 * 提醒提前量选择器：预设档位（准时/15 分钟/1 小时/1 天）+ 自定义分钟输入。
 */
export function ReminderOffsetSelect({
  value,
  onChange,
}: {
  value: number;
  onChange: (offsetMinutes: number) => void;
}) {
  const isPreset = reminderOffsets.some((option) => option.value === value);
  const [customMinutes, setCustomMinutes] = useState(isPreset ? 30 : clampMinutes(value || 30));
  const selected = isPreset ? String(value) : CUSTOM;

  function selectChange(next: string) {
    if (next === CUSTOM) {
      onChange(clampMinutes(customMinutes));
    } else {
      onChange(Number(next));
    }
  }

  return (
    <span className="reminder-offset-control">
      <select value={selected} onChange={(event) => selectChange(event.target.value)}>
        {reminderOffsets.map((option) => (
          <option value={option.value} key={option.value}>
            {option.label}
          </option>
        ))}
        <option value={CUSTOM}>自定义（分钟）</option>
      </select>
      {selected === CUSTOM && (
        <input
          type="number"
          min={1}
          max={MAX_OFFSET_MINUTES}
          value={customMinutes}
          onChange={(event) => {
            const next = clampMinutes(Number(event.target.value));
            setCustomMinutes(next);
            onChange(next);
          }}
          aria-label="自定义提醒分钟数"
        />
      )}
    </span>
  );
}
