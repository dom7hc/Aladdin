import { useQuery } from '@tanstack/react-query'

import { getProject } from '@/api/projectApi'

import { queryKeys } from './queryKeys'

export function useProjectQuery(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.project(id ?? ''),
    queryFn: () => getProject(id as string),
    enabled: Boolean(id),
  })
}
