import { ReactNode } from 'react';
import { Item, Project, Session } from '../api/client';
import { projectHealthLabels, scopeLabel } from '../lib/labels';
import { formatProjectDue } from '../lib/projects';
import { ItemRowShell, RowPriorityMark, RowSegments, RowTimeSlot, RowWaitingMark, rowTooltip } from './ItemRow';
import { RowFocusButton } from './RowFocusButton';

export function TodaySection({ title, count, children }: { title: string; count: number; children: ReactNode }) {
  return (
    <section className="today-card">
      <h2>
        {title} <span>{count}</span>
      </h2>
      <div className="today-list">{count === 0 ? <p className="empty">暂无内容</p> : children}</div>
    </section>
  );
}

export function TodayItemButton({ item, session, onOpen, onToggleDone }: { item: Item; session?: Session; onOpen: () => void; onToggleDone?: () => void }) {
  return (
    <ItemRowShell
      className="today-row"
      onOpen={onOpen}
      tooltip={rowTooltip(item)}
      check={onToggleDone ? { done: false, onToggle: onToggleDone } : undefined}
      flow={
        <>
          <span className="row-scope">{scopeLabel(item.scope)}</span>
          <strong className="row-title">{item.title}</strong>
          <RowPriorityMark item={item} />
          <RowWaitingMark item={item} />
          <RowSegments item={item} />
        </>
      }
      timeslot={<RowTimeSlot item={item} />}
      ops={session ? <RowFocusButton itemId={item.id} session={session} /> : undefined}
    />
  );
}

export function TodayTimedRow({ item, session, time: _time, onOpen, onToggleDone }: { item: Item; session?: Session; time: string; onOpen: () => void; onToggleDone?: () => void }) {
  return (
    <ItemRowShell
      className="today-row timed"
      onOpen={onOpen}
      tooltip={rowTooltip(item)}
      check={onToggleDone ? { done: false, onToggle: onToggleDone } : undefined}
      flow={
        <>
          <span className="row-scope">{scopeLabel(item.scope)}</span>
          <strong className="row-title">{item.title}</strong>
          <RowPriorityMark item={item} />
          <RowWaitingMark item={item} />
          <RowSegments item={item} />
        </>
      }
      timeslot={<RowTimeSlot item={item} />}
      ops={session ? <RowFocusButton itemId={item.id} session={session} /> : undefined}
    />
  );
}

export function TodayProjectRow({ project, onOpen }: { project: Project; onOpen: () => void }) {
  return (
    <button className="today-row" type="button" onClick={onOpen}>
      <strong>{projectHealthLabels[project.health]}</strong>
      <span>{project.name}</span>
      <small>下一步：{project.next_step?.trim() || '未记录'} · 截止：{formatProjectDue(project)}</small>
    </button>
  );
}
