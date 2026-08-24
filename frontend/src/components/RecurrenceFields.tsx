import { RecurrenceDraftFields, recurrenceFreqOptions } from '../lib/recurrence';

/** 周期规则编辑：频率 + 每 N 间隔 + 结束条件（永不/按日期/按次数）。 */
export function RecurrenceFields({
  value,
  onChange,
}: {
  value: RecurrenceDraftFields;
  onChange: (patch: Partial<RecurrenceDraftFields>) => void;
}) {
  const freq = recurrenceFreqOptions.find((option) => option.value === value.recurrence_freq);
  return (
    <div className="recurrence-fields">
      <label>
        重复
        <select
          value={value.recurrence_freq}
          onChange={(event) => onChange({ recurrence_freq: event.target.value as RecurrenceDraftFields['recurrence_freq'] })}
        >
          {recurrenceFreqOptions.map((option) => (
            <option value={option.value} key={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      {value.recurrence_freq && (
        <>
          <label>
            间隔
            <span className="recurrence-interval-row">
              每
              <input
                type="number"
                min={1}
                max={99}
                value={value.recurrence_interval}
                onChange={(event) => onChange({ recurrence_interval: event.target.value })}
              />
              {freq?.unit}
            </span>
          </label>
          <label>
            结束
            <select
              value={value.recurrence_end}
              onChange={(event) => onChange({ recurrence_end: event.target.value as RecurrenceDraftFields['recurrence_end'] })}
            >
              <option value="">永不</option>
              <option value="until">按日期</option>
              <option value="count">按次数</option>
            </select>
          </label>
          {value.recurrence_end === 'until' && (
            <label>
              结束日期
              <input type="date" value={value.recurrence_until} onChange={(event) => onChange({ recurrence_until: event.target.value })} />
            </label>
          )}
          {value.recurrence_end === 'count' && (
            <label>
              重复次数
              <input
                type="number"
                min={2}
                max={999}
                value={value.recurrence_count}
                onChange={(event) => onChange({ recurrence_count: event.target.value })}
              />
            </label>
          )}
          <p className="hint">完成当前事项时自动生成下一次；结束条件到达后不再生成。</p>
        </>
      )}
    </div>
  );
}
