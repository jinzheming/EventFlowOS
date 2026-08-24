import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Archive, ArrowDown, ArrowUp, Check, FolderPlus, Palette, Pencil, Plus, RotateCcw, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { api, ProjectGroup, Session } from '../api/client';
import { EmptyState, ListState } from '../components/ListState';
import { ProjectDrawer } from '../components/ProjectDrawer';
import { ProjectRow } from '../components/ProjectRow';
import { usePatchProject } from '../hooks/useProjectActions';
import { buildProjectPatch, filterProjects, groupProjects } from '../lib/projects';

/** 分组色板（无绿系，与全站语义色一致） */
export const GROUP_COLORS = ['#1D4ED8', '#7C3AED', '#B45309', '#CA8A04', '#BE185D', '#64748B'];

type GroupFilter = 'all' | 'none' | string;

export function ProjectsPage({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [groupFilter, setGroupFilter] = useState<GroupFilter>('all');
  const projects = useQuery({ queryKey: ['projects'], queryFn: api.projects });
  const groups = useQuery({ queryKey: ['project-groups'], queryFn: () => api.projectGroups(true) });
  const selected = projects.data?.find((project) => project.id === selectedId) ?? null;
  const items = useQuery({ queryKey: ['project-items', selected?.id], queryFn: () => api.projectItems(selected!.id), enabled: !!selected });

  const activeGroups = useMemo(() => (groups.data ?? []).filter((group) => !group.archived_at), [groups.data]);
  const archivedGroups = useMemo(() => (groups.data ?? []).filter((group) => group.archived_at), [groups.data]);

  const searchedProjects = useMemo(() => filterProjects(projects.data ?? [], search), [projects.data, search]);
  const visibleProjects = useMemo(() => {
    if (groupFilter === 'all') return searchedProjects;
    if (groupFilter === 'none') return searchedProjects.filter((project) => !project.group_id);
    return searchedProjects.filter((project) => project.group_id === groupFilter);
  }, [searchedProjects, groupFilter]);
  const grouped = useMemo(() => groupProjects(visibleProjects), [visibleProjects]);
  const ungroupedCount = useMemo(() => (projects.data ?? []).filter((project) => !project.group_id).length, [projects.data]);

  function invalidateAll() {
    queryClient.invalidateQueries({ queryKey: ['projects'] });
    queryClient.invalidateQueries({ queryKey: ['project-groups'] });
  }

  function invalidateProjects(projectId?: string) {
    queryClient.invalidateQueries({ queryKey: ['projects'] });
    if (projectId) queryClient.invalidateQueries({ queryKey: ['project-items', projectId] });
  }

  const create = useMutation({
    mutationFn: () =>
      api.createProject(session.csrf_token, {
        name: name.trim(),
        status: 'active',
        health: 'unknown',
        progress_mode: 'manual',
        group_id: groupFilter !== 'all' && groupFilter !== 'none' ? groupFilter : null,
      }),
    onSuccess: (project) => {
      setName('');
      setSelectedId(project.id);
      invalidateAll();
      queryClient.invalidateQueries({ queryKey: ['project-items', project.id] });
    },
  });

  const patch = usePatchProject(session, (project) => {
    setSelectedId(project.id);
    invalidateProjects(project.id);
  });

  return (
    <section className="page projects-page">
      <header className="page-header">
        <div>
          <h1>项目跟进</h1>
          <p>{projects.data?.length ?? 0} 个项目 · {activeGroups.length} 个分组 · 跟踪状态、健康度与下一步</p>
        </div>
      </header>

      <div className="projects-layout">
        <GroupRail
          session={session}
          activeGroups={activeGroups}
          archivedGroups={archivedGroups}
          groupFilter={groupFilter}
          onFilter={setGroupFilter}
          totalCount={projects.data?.length ?? 0}
          ungroupedCount={ungroupedCount}
          onChanged={invalidateAll}
        />

        <div className="projects-main">
          <form
            className="project-quick-add"
            onSubmit={(event) => {
              event.preventDefault();
              if (name.trim()) create.mutate();
            }}
          >
            <input placeholder="输入项目名称，按回车创建" value={name} onChange={(event) => setName(event.target.value)} />
            <button className="primary" type="submit" disabled={!name.trim() || create.isPending}>
              <Plus size={16} /> 添加
            </button>
          </form>
          {create.isError && <p className="error-line">{create.error.message}</p>}

          <div className="list-controls">
            <input placeholder="搜索项目名称、下一步或风险备注" value={search} onChange={(event) => setSearch(event.target.value)} />
          </div>

          <ListState loading={projects.isLoading} error={projects.isError ? String(projects.error.message) : null} onRetry={() => projects.refetch()}>
            {visibleProjects.length === 0 ? (
              <EmptyState filtered={Boolean(search.trim()) || groupFilter !== 'all'} onClearFilters={() => { setSearch(''); setGroupFilter('all'); }}>
                {search.trim() ? '没有匹配搜索的项目' : groupFilter === 'all' ? '暂无项目，在上方输入名称回车创建' : '该分组暂无项目'}
              </EmptyState>
            ) : (
              <div className="project-groups">
                {grouped.map((group) => (
                  <section className="project-group" key={group.label}>
                    <h2>
                      {group.label} <span>{group.projects.length}</span>
                    </h2>
                    {group.projects.length === 0 && <p className="empty">暂无项目</p>}
                    {group.projects.map((project) => (
                      <ProjectRow
                        project={project}
                        key={project.id}
                        selected={project.id === selectedId}
                        onOpen={() => setSelectedId(project.id)}
                        groupLabel={groupFilter === 'all' ? project.group_name : null}
                      />
                    ))}
                  </section>
                ))}
              </div>
            )}
          </ListState>
        </div>
      </div>

      {selected && (
        <ProjectDrawer
          project={selected}
          items={items.data ?? []}
          session={session}
          saving={patch.isPending}
          error={patch.error?.message}
          onClose={() => setSelectedId(null)}
          onSave={(draft) => patch.mutate({ project: selected, payload: buildProjectPatch(draft) })}
          onStatus={(status) => patch.mutate({ project: selected, payload: { status } })}
        />
      )}
    </section>
  );
}

function GroupRail({
  session,
  activeGroups,
  archivedGroups,
  groupFilter,
  onFilter,
  totalCount,
  ungroupedCount,
  onChanged,
}: {
  session: Session;
  activeGroups: ProjectGroup[];
  archivedGroups: ProjectGroup[];
  groupFilter: GroupFilter;
  onFilter: (filter: GroupFilter) => void;
  totalCount: number;
  ungroupedCount: number;
  onChanged: () => void;
}) {
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState('');
  const [newColor, setNewColor] = useState(GROUP_COLORS[0]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [colorPickerFor, setColorPickerFor] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onError = (err: Error) => setError(err.message);
  const onSettled = () => onChanged();

  const createGroup = useMutation({
    mutationFn: () => api.createProjectGroup(session.csrf_token, { name: newName.trim(), color: newColor, sort_order: activeGroups.length }),
    onSuccess: (group) => {
      setAdding(false);
      setNewName('');
      setError(null);
      onFilter(group.id);
    },
    onError,
    onSettled,
  });
  const patchGroup = useMutation({
    mutationFn: ({ group, payload }: { group: ProjectGroup; payload: Partial<Pick<ProjectGroup, 'name' | 'color' | 'sort_order'>> }) =>
      api.patchProjectGroup(session.csrf_token, group.id, payload),
    onSuccess: () => {
      setEditingId(null);
      setColorPickerFor(null);
      setError(null);
    },
    onError,
    onSettled,
  });
  const archiveGroup = useMutation({
    mutationFn: (group: ProjectGroup) => api.archiveProjectGroup(session.csrf_token, group.id),
    onSuccess: (group) => {
      if (groupFilter === group.id) onFilter('all');
    },
    onError,
    onSettled,
  });
  const restoreGroup = useMutation({
    mutationFn: (group: ProjectGroup) => api.restoreProjectGroup(session.csrf_token, group.id),
    onError,
    onSettled,
  });

  function move(group: ProjectGroup, direction: -1 | 1) {
    const index = activeGroups.findIndex((candidate) => candidate.id === group.id);
    const neighbor = activeGroups[index + direction];
    if (!neighbor) return;
    patchGroup.mutate({ group, payload: { sort_order: neighbor.sort_order } });
    patchGroup.mutate({ group: neighbor, payload: { sort_order: group.sort_order } });
  }

  function startEdit(group: ProjectGroup) {
    setEditingId(group.id);
    setEditName(group.name);
    setColorPickerFor(null);
  }

  return (
    <aside className="group-rail">
      <button className={groupFilter === 'all' ? 'group-row active' : 'group-row'} type="button" onClick={() => onFilter('all')}>
        <span className="group-dot all" />
        <span className="group-name">全部</span>
        <span className="group-count">{totalCount}</span>
      </button>
      {activeGroups.map((group, index) => (
        <div className={groupFilter === group.id ? 'group-row-wrap active' : 'group-row-wrap'} key={group.id}>
          {editingId === group.id ? (
            <form
              className="group-edit-row"
              onSubmit={(event) => {
                event.preventDefault();
                if (editName.trim() && editName.trim() !== group.name) patchGroup.mutate({ group, payload: { name: editName.trim() } });
                else setEditingId(null);
              }}
            >
              <input value={editName} onChange={(event) => setEditName(event.target.value)} data-autofocus />
              <button className="icon-button" type="submit" title="保存"><Check size={14} /></button>
              <button className="icon-button" type="button" title="取消" onClick={() => setEditingId(null)}><X size={14} /></button>
            </form>
          ) : (
            <>
              <button className={groupFilter === group.id ? 'group-row active' : 'group-row'} type="button" onClick={() => onFilter(group.id)}>
                <span className="group-dot" style={{ background: group.color }} />
                <span className="group-name">{group.name}</span>
                {group.risk_count > 0 && <span className="group-risk">{group.risk_count}</span>}
                <span className="group-count">{group.project_count}</span>
              </button>
              <span className="row-actions">
                <button className="ghost sm" type="button" title="上移" disabled={index === 0} onClick={() => move(group, -1)}><ArrowUp size={13} /></button>
                <button className="ghost sm" type="button" title="下移" disabled={index === activeGroups.length - 1} onClick={() => move(group, 1)}><ArrowDown size={13} /></button>
                <button className="ghost sm" type="button" title="重命名" onClick={() => startEdit(group)}><Pencil size={13} /></button>
                <button className="ghost sm" type="button" title="更改颜色" onClick={() => setColorPickerFor(colorPickerFor === group.id ? null : group.id)}><Palette size={13} /></button>
                <button className="ghost sm danger-text" type="button" title="归档分组（项目将归入未分类）" onClick={() => archiveGroup.mutate(group)}><Archive size={13} /></button>
              </span>
            </>
          )}
          {colorPickerFor === group.id && (
            <div className="group-color-picker">
              {GROUP_COLORS.map((color) => (
                <button
                  key={color}
                  className={color === group.color ? 'color-swatch active' : 'color-swatch'}
                  type="button"
                  style={{ background: color }}
                  title={color}
                  onClick={() => patchGroup.mutate({ group, payload: { color } })}
                />
              ))}
            </div>
          )}
        </div>
      ))}
      <button className={groupFilter === 'none' ? 'group-row active' : 'group-row'} type="button" onClick={() => onFilter('none')}>
        <span className="group-dot none" />
        <span className="group-name">未分类</span>
        <span className="group-count">{ungroupedCount}</span>
      </button>

      <div className="group-rail-footer">
        {adding ? (
          <form
            className="group-add-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (newName.trim()) createGroup.mutate();
            }}
          >
            <input placeholder="分组名称" value={newName} onChange={(event) => setNewName(event.target.value)} data-autofocus />
            <div className="group-color-picker">
              {GROUP_COLORS.map((color) => (
                <button
                  key={color}
                  className={color === newColor ? 'color-swatch active' : 'color-swatch'}
                  type="button"
                  style={{ background: color }}
                  title={color}
                  onClick={() => setNewColor(color)}
                />
              ))}
            </div>
            <div className="panel-actions">
              <button className="ghost sm" type="button" onClick={() => { setAdding(false); setNewName(''); setError(null); }}>取消</button>
              <button className="primary" type="submit" disabled={!newName.trim() || createGroup.isPending}>创建</button>
            </div>
          </form>
        ) : (
          <button className="ghost sm" type="button" onClick={() => setAdding(true)}>
            <FolderPlus size={14} /> 新建分组
          </button>
        )}
        {error && <p className="error-line">{error}</p>}
        {archivedGroups.length > 0 && (
          <details className="group-archived" open={showArchived} onToggle={(event) => setShowArchived((event.target as HTMLDetailsElement).open)}>
            <summary>已归档（{archivedGroups.length}）</summary>
            {archivedGroups.map((group) => (
              <div className="group-row-wrap" key={group.id}>
                <span className="group-row">
                  <span className="group-dot" style={{ background: group.color }} />
                  <span className="group-name">{group.name}</span>
                </span>
                <span className="row-actions">
                  <button className="ghost sm" type="button" title="恢复" onClick={() => restoreGroup.mutate(group)}><RotateCcw size={13} /></button>
                </span>
              </div>
            ))}
          </details>
        )}
      </div>
    </aside>
  );
}
