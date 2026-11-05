import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { createProject, getScenarios, listProjects } from '@/api/projectApi'

import { queryKeys } from './queryKeys'

export function useProjectsQuery() {
  return useQuery({
    queryKey: queryKeys.projects,
    queryFn: listProjects,
  })
}

export function useCreateProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (idea: string) => createProject(idea),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.projects })
    },
  })
}

/** The business cases offered as starting points. Edits invalidate this. */
export function useScenariosQuery() {
  return useQuery({
    queryKey: queryKeys.scenarios,
    queryFn: getScenarios,
    staleTime: Infinity,
  })
}
