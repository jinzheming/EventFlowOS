import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, X } from 'lucide-react';
import { useState } from 'react';
import { api, ItemPerson, Person, PersonRole, Session } from '../api/client';
import type { DraftPerson } from '../lib/drafts';

export const personRoleLabels: Record<PersonRole, string> = {
  together: '一起',
  waiting: '等待',
};

function personSubtitle(person: Pick<Person, 'identity' | 'active'> | Pick<ItemPerson, 'identity' | 'active'>) {
  return [person.identity || '未设置身份', person.active ? null : '已停用'].filter(Boolean).join(' · ');
}

export function PersonChips({ people }: { people: ItemPerson[] }) {
  if (people.length === 0) return null;
  return (
    <>
      {people.slice(0, 4).map((person) => (
        <span className={`field-pill person-field ${person.role}`} key={`${person.id}-${person.role}`}>
          {personRoleLabels[person.role]} {person.name}
          {person.identity ? ` · ${person.identity}` : ''}
        </span>
      ))}
      {people.length > 4 && <span className="field-pill person-field">+{people.length - 4}</span>}
    </>
  );
}

export function InlinePersonList({ people }: { people: ItemPerson[] }) {
  if (people.length === 0) return null;
  return (
    <div className="inline-person-list">
      {people.map((person) => (
        <span className={`person-token ${person.role}`} key={`${person.id}-${person.role}`}>
          {personRoleLabels[person.role]} {person.name}
          {person.identity ? ` · ${person.identity}` : ''}
        </span>
      ))}
    </div>
  );
}

export function PersonPicker({
  session,
  value,
  onChange,
}: {
  session: Session;
  value: DraftPerson[];
  onChange: (people: DraftPerson[]) => void;
}) {
  const queryClient = useQueryClient();
  const people = useQuery({ queryKey: ['people'], queryFn: () => api.people(true) });
  const [selectedPersonId, setSelectedPersonId] = useState('');
  const [selectedRole, setSelectedRole] = useState<PersonRole>('together');
  const [newName, setNewName] = useState('');
  const [newIdentity, setNewIdentity] = useState('');
  const selectedIds = new Set(value.map((person) => person.person_id));
  const peopleById = new Map((people.data ?? []).map((person) => [person.id, person]));
  const activePeople = (people.data ?? []).filter((person) => person.active);

  const createPerson = useMutation({
    mutationFn: () => api.createPerson(session.csrf_token, { name: newName.trim(), identity: newIdentity.trim() || null }),
    onSuccess: (person) => {
      queryClient.invalidateQueries({ queryKey: ['people'] });
      onChange([...value.filter((existing) => existing.person_id !== person.id), { person_id: person.id, role: selectedRole }]);
      setNewName('');
      setNewIdentity('');
    },
  });

  function addExisting() {
    if (!selectedPersonId || selectedIds.has(selectedPersonId)) return;
    onChange([...value, { person_id: selectedPersonId, role: selectedRole }]);
    setSelectedPersonId('');
  }

  function updateRole(personId: string, role: PersonRole) {
    onChange(value.map((person) => (person.person_id === personId ? { ...person, role } : person)));
  }

  function remove(personId: string) {
    onChange(value.filter((person) => person.person_id !== personId));
  }

  return (
    <section className="person-picker">
      <div className="person-picker-title">相关的人</div>
      {value.length === 0 && <p className="hint">可逐个添加人员，并标记为“一起”或“等待”。有等待人员时，事项会自动变为等待他人。</p>}
      <div className="person-selected-list">
        {value.map((entry) => {
          const person = peopleById.get(entry.person_id);
          return (
            <div className="person-row" key={entry.person_id}>
              <div>
                <strong>{person?.name ?? '未知人员'}</strong>
                <span>{person ? personSubtitle(person) : '请刷新人员列表'}</span>
              </div>
              <select value={entry.role} onChange={(event) => updateRole(entry.person_id, event.target.value as PersonRole)}>
                <option value="together">一起</option>
                <option value="waiting">等待</option>
              </select>
              <button className="icon-button" type="button" title="移除" onClick={() => remove(entry.person_id)}>
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
      <div className="person-add-grid">
        <select value={selectedPersonId} onChange={(event) => setSelectedPersonId(event.target.value)}>
          <option value="">选择已有人员</option>
          {activePeople.map((person) => (
            <option value={person.id} key={person.id} disabled={selectedIds.has(person.id)}>
              {person.name}{person.identity ? ` · ${person.identity}` : ''}
            </option>
          ))}
        </select>
        <select value={selectedRole} onChange={(event) => setSelectedRole(event.target.value as PersonRole)}>
          <option value="together">一起</option>
          <option value="waiting">等待</option>
        </select>
        <button className="secondary" type="button" onClick={addExisting} disabled={!selectedPersonId}>
          添加
        </button>
      </div>
      <div className="person-create-grid">
        <input placeholder="新人员姓名" value={newName} onChange={(event) => setNewName(event.target.value)} />
        <input placeholder="身份（可选，自定义）" value={newIdentity} onChange={(event) => setNewIdentity(event.target.value)} />
        <button className="secondary" type="button" onClick={() => createPerson.mutate()} disabled={!newName.trim() || createPerson.isPending}>
          <Plus size={14} /> 新建并添加
        </button>
      </div>
      {people.isError && <p className="error-line">{people.error.message}</p>}
      {createPerson.isError && <p className="error-line">{createPerson.error.message}</p>}
    </section>
  );
}
