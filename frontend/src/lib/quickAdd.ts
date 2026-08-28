import type { Scope } from '../api/client';
import { addDaysString } from './dates';
import type { RecurrenceChoice } from './recurrence';

export type QuickAddParse = {
  title: string;
  scope: Scope | null;
  start_date: string;
  start_time: string;
  estimated_minutes: number | null;
  reminder_offset: number | null;
  recurrence: RecurrenceChoice;
  status: 'waiting' | null;
  waiting_on: string;
  person_role: 'together' | 'waiting' | null;
};

export type QuickAddParseOptions = {
  referenceDate?: string | Date;
};

const WEEKDAYS: Record<string, number> = {
  一: 1,
  二: 2,
  三: 3,
  四: 4,
  五: 5,
  六: 6,
  日: 0,
  天: 0,
};

function pad(value: number) {
  return String(value).padStart(2, '0');
}

function explicitDate(year: number, month: number, day: number): string | null {
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
  return `${year}-${pad(month)}-${pad(day)}`;
}

function normalizeReferenceDate(referenceDate?: string | Date): string {
  if (!referenceDate) return addDaysString(0);
  if (typeof referenceDate === 'string') return referenceDate.slice(0, 10);
  return `${referenceDate.getUTCFullYear()}-${pad(referenceDate.getUTCMonth() + 1)}-${pad(referenceDate.getUTCDate())}`;
}

function addDaysFrom(referenceDate: string, days: number): string {
  const [year, month, day] = referenceDate.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day + days));
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`;
}

function daysBetween(left: string, right: string): number {
  const [leftYear, leftMonth, leftDay] = left.split('-').map(Number);
  const [rightYear, rightMonth, rightDay] = right.split('-').map(Number);
  const leftTime = Date.UTC(leftYear, leftMonth - 1, leftDay);
  const rightTime = Date.UTC(rightYear, rightMonth - 1, rightDay);
  return Math.round((leftTime - rightTime) / 86400000);
}

function resolveMonthDay(referenceDate: string, month: number, day: number, preferPast: boolean): string | null {
  const [year] = referenceDate.split('-').map(Number);
  const candidates = [year - 1, year, year + 1]
    .map((candidateYear) => explicitDate(candidateYear, month, day))
    .filter((value): value is string => Boolean(value));
  const recentPast = candidates
    .map((value) => ({ value, delta: daysBetween(referenceDate, value) }))
    .filter((candidate) => candidate.delta >= 0 && candidate.delta <= 7)
    .sort((a, b) => a.delta - b.delta)[0];
  if (recentPast) return recentPast.value;

  if (preferPast) {
    const pastCandidates = candidates.filter((value) => value <= referenceDate).sort();
    const past = pastCandidates[pastCandidates.length - 1];
    if (past) return past;
  }

  return candidates.filter((value) => value >= referenceDate).sort()[0] ?? null;
}

function resolveDayOfMonth(referenceDate: string, day: number, preferPast: boolean): string | null {
  const [year, month] = referenceDate.split('-').map(Number);
  const candidates = [-1, 0, 1, 2]
    .map((offset) => {
      const monthStart = new Date(Date.UTC(year, month - 1 + offset, 1));
      return explicitDate(monthStart.getUTCFullYear(), monthStart.getUTCMonth() + 1, day);
    })
    .filter((value): value is string => Boolean(value));
  const recentPast = candidates
    .map((value) => ({ value, delta: daysBetween(referenceDate, value) }))
    .filter((candidate) => candidate.delta >= 0 && candidate.delta <= 7)
    .sort((a, b) => a.delta - b.delta)[0];
  if (recentPast) return recentPast.value;

  if (preferPast) {
    const pastCandidates = candidates.filter((value) => value <= referenceDate).sort();
    const past = pastCandidates[pastCandidates.length - 1];
    if (past) return past;
  }

  return candidates.filter((value) => value >= referenceDate).sort()[0] ?? null;
}

function nextWeekday(referenceDate: string, target: number): string {
  const [year, month, day] = referenceDate.split('-').map(Number);
  const dow = new Date(Date.UTC(year, month - 1, day)).getUTCDay();
  let delta = (target - dow + 7) % 7;
  if (delta === 0) delta = 7;
  return addDaysFrom(referenceDate, delta);
}

function relativeWeekday(referenceDate: string, target: number, prefix: string | undefined): string {
  if (!prefix) return nextWeekday(referenceDate, target);
  const [year, month, day] = referenceDate.split('-').map(Number);
  const dow = new Date(Date.UTC(year, month - 1, day)).getUTCDay();
  const currentIso = dow === 0 ? 7 : dow;
  const targetIso = target === 0 ? 7 : target;
  const weekOffset = prefix === '上' ? -7 : prefix === '下' ? 7 : 0;
  return addDaysFrom(referenceDate, targetIso - currentIso + weekOffset);
}

/**
 * Parse a quick-add line such as "明天下午3点 约牙医 提前1小时提醒 #个人".
 * Chinese-first; unknown fragments stay in the title.
 */
export function parseQuickAdd(raw: string, options: QuickAddParseOptions = {}): QuickAddParse {
  let text = ` ${raw.trim()} `;
  const referenceDate = normalizeReferenceDate(options.referenceDate);
  let scope: Scope | null = null;
  let startDate = '';
  let startTime = '';
  let estimatedMinutes: number | null = null;
  let reminderOffset: number | null = null;
  let recurrence: RecurrenceChoice = '';
  let anchorWeekday: string | null = null;
  let status: 'waiting' | null = null;
  let waitingOn = '';
  let personRole: 'together' | 'waiting' | null = null;

  const scopeMatch = text.match(/[#＃](工作|个人)/);
  if (scopeMatch) {
    scope = scopeMatch[1] === '工作' ? 'work' : 'personal';
    text = text.replace(scopeMatch[0], ' ');
  }

  // 符号前置协作/等待: @人名=一起协作, !人名=等待他人(全角兼容, 捕获到空格/标点/下一个符号)
  const NAME_STOP = '[^\\s，。,#＃@＠!！~～]';
  const atMatch = text.match(new RegExp(`(?:^|\\s)[@＠](${NAME_STOP}+)`));
  const bangMatch = text.match(new RegExp(`(?:^|\\s)[!！](${NAME_STOP}+)`));
  if (atMatch) {
    waitingOn = atMatch[1];
    personRole = 'together';
    text = text.replace(atMatch[0].trim(), ' ');
  } else if (bangMatch) {
    waitingOn = bangMatch[1];
    personRole = 'waiting';
    status = 'waiting';
    text = text.replace(bangMatch[0].trim(), ' ');
  }

  // 周期任务: 每天/每日/每周/每两周/每月(每周X 时把 X 作为锚点星期,如「每周一 10点 站会」)
  const weeklyAnchorMatch = text.match(/(每周|每两周|每2周)([一二三四五六日天])/);
  if (weeklyAnchorMatch) {
    recurrence = weeklyAnchorMatch[1] === '每周' ? 'weekly' : 'biweekly';
    anchorWeekday = weeklyAnchorMatch[2];
    text = text.replace(weeklyAnchorMatch[0], ' ');
  } else {
    const recurrenceMatch = text.match(/每天|每日|每周|每两周|每2周|每月/);
    if (recurrenceMatch) {
      const token = recurrenceMatch[0];
      recurrence =
        token === '每天' || token === '每日' ? 'daily'
        : token === '每两周' || token === '每2周' ? 'biweekly'
        : token === '每周' ? 'weekly'
        : 'monthly';
      text = text.replace(token, ' ');
    }
  }

  const reminderMatch = text.match(/提前(\d{1,4})\s*(分钟|小时|天)(?:提醒|通知)/);
  if (reminderMatch) {
    const amount = Number(reminderMatch[1]);
    const unit = reminderMatch[2];
    reminderOffset = unit === '分钟' ? amount : unit === '小时' ? amount * 60 : amount * 1440;
    text = text.replace(reminderMatch[0], ' ');
  } else if (/(?:提醒|通知)我?/.test(text)) {
    reminderOffset = 0;
    text = text.replace(/(?:提醒|通知)我?/, ' ');
  }

  const timeMatch = text.match(/(凌晨|早上|早晨|上午|中午|下午|傍晚|晚上)?\s*(\d{1,2})[:：点](\d{1,2})?分?/);
  if (timeMatch) {
    let hour = Number(timeMatch[2]);
    const minute = timeMatch[3] ? Number(timeMatch[3]) : 0;
    const period = timeMatch[1];
    if ((period === '下午' || period === '傍晚' || period === '晚上' || period === '中午') && hour < 12) hour += 12;
    if (period === '凌晨' && hour === 12) hour = 0;
    if (hour <= 23 && minute <= 59) {
      startTime = `${pad(hour)}:${pad(minute)}`;
      text = text.replace(timeMatch[0], ' ');
    }
  }

  const ymdMatch = text.match(/(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})[日号]?/);
  const mdMatch = text.match(/(\d{1,2})月(\d{1,2})[日号]/);
  const dayMatch = text.match(/(?:^|\s)(\d{1,2})[日号](?=\s|$)/);
  const preferPastDate = /补录|回顾|上次|已完成|完成了|过去/.test(text);
  if (ymdMatch) {
    const parsed = explicitDate(Number(ymdMatch[1]), Number(ymdMatch[2]), Number(ymdMatch[3]));
    if (parsed) {
      startDate = parsed;
      text = text.replace(ymdMatch[0], ' ');
    }
  } else if (mdMatch) {
    const parsed = resolveMonthDay(referenceDate, Number(mdMatch[1]), Number(mdMatch[2]), preferPastDate);
    if (parsed) {
      startDate = parsed;
      text = text.replace(mdMatch[0], ' ');
    }
  } else if (/大前天/.test(text)) {
    startDate = addDaysFrom(referenceDate, -3);
    text = text.replace(/大前天/, ' ');
  } else if (/前天/.test(text)) {
    startDate = addDaysFrom(referenceDate, -2);
    text = text.replace(/前天/, ' ');
  } else if (/昨天|昨日/.test(text)) {
    startDate = addDaysFrom(referenceDate, -1);
    text = text.replace(/昨天|昨日/, ' ');
  } else if (/大后天/.test(text)) {
    startDate = addDaysFrom(referenceDate, 3);
    text = text.replace(/大后天/, ' ');
  } else if (/后天/.test(text)) {
    startDate = addDaysFrom(referenceDate, 2);
    text = text.replace(/后天/, ' ');
  } else if (/明天|明日/.test(text)) {
    startDate = addDaysFrom(referenceDate, 1);
    text = text.replace(/明天|明日/, ' ');
  } else if (/今天|今日/.test(text)) {
    startDate = referenceDate;
    text = text.replace(/今天|今日/, ' ');
  } else if (dayMatch) {
    const parsed = resolveDayOfMonth(referenceDate, Number(dayMatch[1]), preferPastDate);
    if (parsed) {
      startDate = parsed;
      text = text.replace(dayMatch[0], ' ');
    }
  } else if (anchorWeekday) {
    const target = WEEKDAYS[anchorWeekday];
    startDate = nextWeekday(referenceDate, target);
    anchorWeekday = null;
  } else {
    const weekMatch = text.match(/(上|本|下)?(?:周|星期)([一二三四五六日天])/);
    if (weekMatch) {
      const target = WEEKDAYS[weekMatch[2]];
      startDate = relativeWeekday(referenceDate, target, weekMatch[1]);
      text = text.replace(weekMatch[0], ' ');
    }
  }

  // 周期事项没给日期时,锚定到今天(如: 每天9点 打卡)
  if (recurrence && !startDate) startDate = addDaysString(0);

  const durationMatch = text.match(/(?:预计|用时|时长)\s*(\d{1,4})\s*(分钟|小时)/);
  if (durationMatch) {
    const amount = Number(durationMatch[1]);
    estimatedMinutes = durationMatch[2] === '小时' ? amount * 60 : amount;
    text = text.replace(durationMatch[0], ' ');
  }

  // 时长符号: ~30=30分钟, ~1.5h=90分钟, ~ 裸符号=60分钟(全角～兼容)
  if (estimatedMinutes === null) {
    const tildeMatch = text.match(/(?:^|\s)[~～]\s*(\d{1,3}(?:\.\d+)?)?\s*(h|H|小时|分钟)?(?=\s|$)/);
    if (tildeMatch) {
      if (!tildeMatch[1]) {
        estimatedMinutes = 60;
      } else {
        const amount = Number(tildeMatch[1]);
        const unit = tildeMatch[2];
        estimatedMinutes = unit === 'h' || unit === 'H' || unit === '小时' ? Math.round(amount * 60) : amount;
      }
      text = text.replace(tildeMatch[0], ' ');
    }
  }

  // 缺省: 有开始时间但未写时长 → 默认 1 小时
  if (estimatedMinutes === null && startTime) estimatedMinutes = 60;

  // 自然语言协作别名: 和/与/跟 X 一起|协作|共同(非贪婪, 剥离残留连词)
  const collaboratorMatch = text.match(/(?:和|与|跟)\s*([^\s，。]{1,12}?)\s*(?:一起|协作|共同)/);
  if (collaboratorMatch && !personRole) {
    waitingOn = collaboratorMatch[1].trim();
    personRole = 'together';
    text = text.replace(collaboratorMatch[0], ' ');
  }

  const title = text.replace(/\s+/g, ' ').trim();
  const waitMatch = title.match(/^(?:等|等待)\s*(.+)$/);
  if (waitMatch && !personRole) {
    status = 'waiting';
    waitingOn = waitMatch[1].trim();
    personRole = 'waiting';
  }

  return {
    title,
    scope,
    start_date: startDate,
    start_time: startTime,
    estimated_minutes: estimatedMinutes,
    reminder_offset: reminderOffset,
    recurrence,
    status,
    waiting_on: waitingOn,
    person_role: personRole,
  };
}

export type ScopeResolution = {
  scope: Scope | null;
  source: 'explicit' | 'identity' | 'inbox';
};

/**
 * Scope decision chain for quick add:
 * explicit #标签 wins; otherwise the collaborator's person-directory identity
 * is matched against identity→scope rules; no signal means inbox triage.
 */
export function resolveScope(
  parsed: QuickAddParse,
  rules: { keyword: string; scope: Scope }[],
  people: { name: string; identity: string | null }[],
): ScopeResolution {
  if (parsed.scope) return { scope: parsed.scope, source: 'explicit' };
  const personName = parsed.waiting_on.trim();
  if (personName) {
    const identity = (people.find((person) => person.name === personName)?.identity ?? '').toLowerCase();
    if (identity) {
      for (const rule of rules) {
        const keyword = rule.keyword.trim().toLowerCase();
        if (keyword && identity.includes(keyword)) {
          return { scope: rule.scope, source: 'identity' };
        }
      }
    }
  }
  return { scope: null, source: 'inbox' };
}
