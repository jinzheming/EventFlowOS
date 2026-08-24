import { useMemo } from 'react';

const HOURS = Array.from({ length: 24 }, (_, index) => String(index).padStart(2, '0'));
const QUARTERS = ['00', '15', '30', '45'];
const DEFAULT_TIME = '09:00';

/** 取最接近的刻钟(07→00, 08→15, 23→15, 38→30, 59→45) */
function nearestQuarter(minute: number) {
  if (minute < 8) return '00';
  if (minute < 23) return '15';
  if (minute < 38) return '30';
  return '45';
}

/**
 * 简化时间选择器:小时(00-23)+ 刻钟(00/15/30/45)。
 * 值为空时展示默认 09:00;一旦用户改动任一下拉即写入 HH:mm。
 * 保留未触碰(空值)语义:事项仍是"全天",不强制设时间。
 */
export function QuarterTimePicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const parts = useMemo(() => {
    const [hour, minute] = (value || DEFAULT_TIME).split(':');
    return { hour, minute };
  }, [value]);

  const hour = parts.hour;
  const minute = value ? nearestQuarter(Number(parts.minute)) : '00';

  function commit(nextHour: string, nextMinute: string) {
    onChange(`${nextHour}:${nextMinute}`);
  }

  return (
    <span className="quarter-time-picker">
      <select value={hour} aria-label="小时" onChange={(event) => commit(event.target.value, minute)}>
        {HOURS.map((candidate) => (
          <option value={candidate} key={candidate}>
            {candidate}
          </option>
        ))}
      </select>
      <span className="time-colon">:</span>
      <select value={minute} aria-label="分钟" onChange={(event) => commit(hour, event.target.value)}>
        {QUARTERS.map((candidate) => (
          <option value={candidate} key={candidate}>
            {candidate}
          </option>
        ))}
      </select>
    </span>
  );
}
