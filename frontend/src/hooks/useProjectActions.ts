import { useMutation } from '@tanstack/react-query';
import { api, Project, Session } from '../api/client';

export type PatchProjectArgs = {
  project: Project;
  payload: Partial<Project>;
};

export function usePatchProject(session: Session, onSaved: (project: Project) => void) {
  return useMutation({
    mutationFn: ({ project, payload }: PatchProjectArgs) => api.patchProject(session.csrf_token, project, payload),
    onSuccess: onSaved,
  });
}
