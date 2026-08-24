import { PersonalDraft, WorkDraft } from '../lib/drafts';
import { previewPersonalReminder, previewWorkReminder } from '../lib/reminderPreview';

export function ReminderPreviewHint({
  draft,
  kind,
}: {
  draft: WorkDraft | PersonalDraft;
  kind: 'work' | 'personal';
}) {
  const preview = kind === 'work' ? previewWorkReminder(draft as WorkDraft) : previewPersonalReminder(draft as PersonalDraft);
  if (!preview) return null;
  return <p className="hint reminder-preview">{preview.label}</p>;
}
