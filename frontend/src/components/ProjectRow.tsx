import { Project } from '../api/client';
import { formatProjectDue } from '../lib/projects';
import { projectHealthLabels, projectStatusLabels } from '../lib/labels';

export function ProjectRow({ project, selected, onOpen, groupLabel }: { project: Project; selected: boolean; onOpen: () => void; groupLabel?: string | null }) {
  return (
    <article
      className={selected ? 'project-line active' : 'project-line'}
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onOpen();
        }
      }}
    >
      <span className={`project-health-dot ${project.health}`} />
      <div className="project-line-main">
        <strong>{project.name}</strong>
        <span>
          {projectStatusLabels[project.status]} · {projectHealthLabels[project.health]}
          {groupLabel ? ` · ${groupLabel}` : ''}
        </span>
      </div>
      <span className="project-next">下一步：{project.next_step?.trim() || '未记录'}</span>
      <span className="project-due">截止：{formatProjectDue(project)}</span>
    </article>
  );
}
