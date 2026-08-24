import { useState } from 'react';

const PRESETS: Array<{ value: number; label: string }> = [
  { value: 15, label: '15 分钟' },
  { value: 30, label: '30 分钟' },
  { value: 45, label: '45 分钟' },
  { value: 60, label: '1 小时' },
  { value: 90, label: '1.5 小时' },
  { value: 120, label: '2 小时' },
  { value: 180, label: '3 小时' },
  { value: 240, label: '4 小时（半天）' },
  { value: 480, label: '8 小时（全天）' },
];

const NONE = 'none';
const CUSTOM = 'custom';
const MAX_MINUTES = 10080;

function clamp(value: number) {
  if (!Number.isFinite(value)) return 30;
  return Math.max(1, Math.min(MAX_MINUTES, Math.round(value)));
}

/**
 * 预计时长选择器:预设档位(不设置/15分钟~8小时)+ 自定义分钟输入。
 * draft 侧用字符串表示:'' = 未设置。
 */
export function EstimatedDurationSelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const current = value ? Number(value) : null;
  const isPreset = current !== null && PRESETS.some((preset) => preset.value === current);
  const [customMinutes, setCustomMinutes] = useState(current !== null && !isPreset ? current : 30);
  const selected = current === null ? NONE : isPreset ? String(current) : CUSTOM;

  function selectChange(next: string) {
    if (next === NONE) {
      onChange('');
    } else if (next === CUSTOM) {
      const valueMinutes = clamp(customMinutes);
      setCustomMinutes(valueMinutes);
      onChange(String(valueMinutes));
    } else {
      onChange(next);
    }
  }

  return (
    <span className="estimated-duration-control">
      <select value={selected} onChange={(event) => selectChange(event.target.value)}>
        <option value={NONE}>不设置</option>
        {PRESETS.map((preset) => (
          <option value={preset.value} key={preset.value}>
            {preset.label}
          </option>
        ))}
        <option value={CUSTOM}>自定义（分钟）</option>
      </select>
      {selected === CUSTOM && (
        <input
          type="number"
          min={1}
          max={MAX_MINUTES}
          value={customMinutes}
          onChange={(event) => {
            const next = clamp(Number(event.target.value));
            setCustomMinutes(next);
            onChange(String(next));
          }}
          aria-label="自定义预计分钟数"
        />
      )}
    </span>
  );
}
