/* parseQuickAdd 快速添加解析的单测(node --test,利用 Node 原生 TS 支持) */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseQuickAdd, resolveScope } from './src/lib/quickAdd.ts';
import { addDaysString } from './src/lib/dates.ts';

const FIXED_TODAY = '2026-08-28';

function weekdayOf(dateStr) {
  const [y, m, d] = dateStr.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d)).getUTCDay();
}

test('完整示例: 明天下午3点 约牙医 提前1小时提醒 #个人', () => {
  const r = parseQuickAdd('明天下午3点 约牙医 提前1小时提醒 #个人');
  assert.equal(r.scope, 'personal');
  assert.equal(r.start_date, addDaysString(1));
  assert.equal(r.start_time, '15:00');
  assert.equal(r.reminder_offset, 60);
  assert.equal(r.title, '约牙医');
  assert.equal(r.recurrence, '');
  assert.equal(r.status, null);
});

test('周期: 每天9点 打卡 → daily 并锚定今天', () => {
  const r = parseQuickAdd('每天9点 打卡');
  assert.equal(r.recurrence, 'daily');
  assert.equal(r.start_date, addDaysString(0));
  assert.equal(r.start_time, '09:00');
  assert.equal(r.title, '打卡');
});

test('周期: 每周一 10点 站会 → weekly + 下个周一', () => {
  const r = parseQuickAdd('每周一 10点 站会');
  assert.equal(r.recurrence, 'weekly');
  assert.equal(r.start_time, '10:00');
  assert.equal(r.title, '站会');
  assert.equal(weekdayOf(r.start_date), 1);
  const delta = (new Date(`${r.start_date}T00:00:00Z`) - new Date(`${addDaysString(0)}T00:00:00Z`)) / 86400000;
  assert.ok(delta >= 1 && delta <= 7, `delta=${delta}`);
});

test('周期: 每两周 周五 同步 → biweekly + 下个周五', () => {
  const r = parseQuickAdd('每两周 周五 同步');
  assert.equal(r.recurrence, 'biweekly');
  assert.equal(r.title, '同步');
  assert.equal(weekdayOf(r.start_date), 5);
});

test('周期: 每月15号 交房租 → monthly + 下一个15号', () => {
  const r = parseQuickAdd('每月15号 交房租', { referenceDate: FIXED_TODAY });
  assert.equal(r.recurrence, 'monthly');
  assert.equal(r.start_date, '2026-09-15');
  assert.equal(r.title, '交房租');
});

test('等待: 等小王回邮件', () => {
  const r = parseQuickAdd('等小王回邮件');
  assert.equal(r.status, 'waiting');
  assert.equal(r.waiting_on, '小王回邮件');
  assert.equal(r.title, '等小王回邮件');
});

test('等待 + 提醒: 等小王回邮件 提前1小时提醒', () => {
  const r = parseQuickAdd('等小王回邮件 提前1小时提醒');
  assert.equal(r.status, 'waiting');
  assert.equal(r.waiting_on, '小王回邮件');
  assert.equal(r.reminder_offset, 60);
});

test('协作者: 和小王一起 写方案', () => {
  const r = parseQuickAdd('和小王一起 写方案');
  assert.equal(r.waiting_on, '小王');
  assert.equal(r.title, '写方案');
});

test('预计时长: 明天 15:00 写方案 预计90分钟', () => {
  const r = parseQuickAdd('明天 15:00 写方案 预计90分钟');
  assert.equal(r.start_date, addDaysString(1));
  assert.equal(r.start_time, '15:00');
  assert.equal(r.estimated_minutes, 90);
  assert.equal(r.title, '写方案');
});

test('显式日期: 2026-08-20 14:30 交周报', () => {
  const r = parseQuickAdd('2026-08-20 14:30 交周报');
  assert.equal(r.start_date, '2026-08-20');
  assert.equal(r.start_time, '14:30');
  assert.equal(r.title, '交周报');
});

test('下周三 开会 → 下一个自然周的周三', () => {
  const r = parseQuickAdd('下周三 开会', { referenceDate: FIXED_TODAY });
  assert.equal(r.start_date, '2026-09-02');
  assert.equal(r.title, '开会');
});

test('8月20日 15:00 提报销', () => {
  const r = parseQuickAdd('8月20日 15:00 提报销', { referenceDate: FIXED_TODAY });
  assert.equal(r.start_time, '15:00');
  assert.equal(r.start_date, '2027-08-20');
  assert.equal(r.title, '提报销');
});

test('无年份日期: 过去7天内优先识别为本年度近过去', () => {
  const r = parseQuickAdd('8月27日 15:00 提报销', { referenceDate: FIXED_TODAY });
  assert.equal(r.start_date, '2026-08-27');
  assert.equal(r.start_time, '15:00');
  assert.equal(r.title, '提报销');
});

test('无年份日期: 仅写号数时同样应用过去7天规则', () => {
  const r = parseQuickAdd('27号 复盘', { referenceDate: FIXED_TODAY });
  assert.equal(r.start_date, '2026-08-27');
  assert.equal(r.title, '复盘');
});

test('相对过去日期: 昨天/前天/大前天', () => {
  assert.equal(parseQuickAdd('昨天复盘', { referenceDate: FIXED_TODAY }).start_date, '2026-08-27');
  assert.equal(parseQuickAdd('前天报销', { referenceDate: FIXED_TODAY }).start_date, '2026-08-26');
  assert.equal(parseQuickAdd('大前天整理', { referenceDate: FIXED_TODAY }).start_date, '2026-08-25');
});

test('周语义: 本周/上周按自然周解析', () => {
  assert.equal(parseQuickAdd('本周三 开会', { referenceDate: FIXED_TODAY }).start_date, '2026-08-26');
  assert.equal(parseQuickAdd('上周三 开会', { referenceDate: FIXED_TODAY }).start_date, '2026-08-19');
});

test('无效日期: 不解析不存在的日历日期', () => {
  const r = parseQuickAdd('2月30日 复盘', { referenceDate: FIXED_TODAY });
  assert.equal(r.start_date, '');
  assert.equal(r.title, '2月30日 复盘');
});

test('周三 开会 → 本周/下周的周三(delta 1..7)', () => {
  const r = parseQuickAdd('周三 开会');
  assert.equal(weekdayOf(r.start_date), 3);
  const delta = (new Date(`${r.start_date}T00:00:00Z`) - new Date(`${addDaysString(0)}T00:00:00Z`)) / 86400000;
  assert.ok(delta >= 1 && delta <= 7, `delta=${delta}`);
});

test('纯标题: 买牛奶 不产生任何解析', () => {
  const r = parseQuickAdd('买牛奶');
  assert.equal(r.title, '买牛奶');
  assert.equal(r.start_date, '');
  assert.equal(r.start_time, '');
  assert.equal(r.recurrence, '');
  assert.equal(r.status, null);
  assert.equal(r.reminder_offset, null);
});

test('回归: 提前N分钟 提醒', () => {
  const r = parseQuickAdd('明天 15:00 交方案 提前30分钟提醒 #工作');
  assert.equal(r.scope, 'work');
  assert.equal(r.reminder_offset, 30);
  assert.equal(r.start_time, '15:00');
  assert.equal(r.start_date, addDaysString(1));
  assert.equal(r.title, '交方案');
});

test('协作符号: @人名 → together', () => {
  const r = parseQuickAdd('明天下午4点 AI玩偶线上交流 @孙俊教授');
  assert.equal(r.waiting_on, '孙俊教授');
  assert.equal(r.person_role, 'together');
  assert.equal(r.status, null);
  assert.equal(r.title, 'AI玩偶线上交流');
  assert.equal(r.start_time, '16:00');
});

test('等待符号: !人名 → waiting', () => {
  const r = parseQuickAdd('!财务 报销打款');
  assert.equal(r.waiting_on, '财务');
  assert.equal(r.person_role, 'waiting');
  assert.equal(r.status, 'waiting');
  assert.equal(r.title, '报销打款');
});

test('协作符号: 全角＠兼容', () => {
  const r = parseQuickAdd('评审方案 ＠小李');
  assert.equal(r.waiting_on, '小李');
  assert.equal(r.person_role, 'together');
});

test('协作别名: 和小王一起 → 捕获不带"和"', () => {
  const r = parseQuickAdd('明天下午4点 线上交流 和孙俊教授一起');
  assert.equal(r.waiting_on, '孙俊教授');
  assert.equal(r.person_role, 'together');
  assert.equal(r.title, '线上交流');
});

test('时长符号: ~30 → 30分钟', () => {
  const r = parseQuickAdd('明天9点 晨跑 ~30');
  assert.equal(r.estimated_minutes, 30);
  assert.equal(r.title, '晨跑');
});

test('时长符号: ~1.5h → 90分钟', () => {
  const r = parseQuickAdd('下午2点 评审 ~1.5h');
  assert.equal(r.estimated_minutes, 90);
});

test('时长符号: 裸 ~ → 60分钟', () => {
  const r = parseQuickAdd('下午2点 评审 ~');
  assert.equal(r.estimated_minutes, 60);
});

test('缺省: 有开始时间未写时长 → 60分钟', () => {
  const r = parseQuickAdd('明天 15:00 交方案');
  assert.equal(r.start_time, '15:00');
  assert.equal(r.estimated_minutes, 60);
});

test('缺省: 无开始时间不补时长', () => {
  const r = parseQuickAdd('买牛奶');
  assert.equal(r.estimated_minutes, null);
});

test('回归: 预计1小时 自然语言优先于缺省', () => {
  const r = parseQuickAdd('明天下午3点 约牙医 预计2小时');
  assert.equal(r.estimated_minutes, 120);
});

const RULES = [
  { keyword: '同事', scope: 'work' },
  { keyword: '家人', scope: 'personal' },
];
const PEOPLE = [
  { name: '张三', identity: '同事' },
  { name: '李四', identity: null },
  { name: '妈妈', identity: '家人' },
];

test('归类链: 显式 #标签 优先于身份规则', () => {
  const parsed = parseQuickAdd('对齐预算 @张三 #个人');
  const r = resolveScope(parsed, RULES, PEOPLE);
  assert.equal(r.scope, 'personal');
  assert.equal(r.source, 'explicit');
});

test('归类链: @同事身份 → work', () => {
  const parsed = parseQuickAdd('对齐预算 @张三');
  const r = resolveScope(parsed, RULES, PEOPLE);
  assert.equal(r.scope, 'work');
  assert.equal(r.source, 'identity');
});

test('归类链: !家人身份 → personal（等待角色同样适用）', () => {
  const parsed = parseQuickAdd('等报价 !妈妈');
  const r = resolveScope(parsed, RULES, PEOPLE);
  assert.equal(r.scope, 'personal');
  assert.equal(r.source, 'identity');
});

test('归类链: 人名无身份档案 → inbox', () => {
  const parsed = parseQuickAdd('回电话 @李四');
  const r = resolveScope(parsed, RULES, PEOPLE);
  assert.equal(r.scope, null);
  assert.equal(r.source, 'inbox');
});

test('归类链: 无任何信号 → inbox', () => {
  const r = resolveScope(parseQuickAdd('买牛奶'), RULES, PEOPLE);
  assert.equal(r.scope, null);
  assert.equal(r.source, 'inbox');
});
