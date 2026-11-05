import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createScenario,
  deleteScenario,
  getHomeContent,
  listAllScenarios,
  reorderScenarios,
  resetHomeContent,
  resetScenarios,
  saveHomeContent,
  updateScenario,
} from '@/api/contentApi'
import { HOME_DEFAULTS } from '@/mocks/seedContent'
import type { HomeContent, ScenarioInput } from '@/types'

import { queryKeys } from './queryKeys'

/**
 * The home page texts. Starts from the defaults, so the page never flashes
 * empty headings while the request is in flight or if it fails.
 */
export function useHomeContent() {
  return useQuery({
    queryKey: queryKeys.home,
    queryFn: getHomeContent,
    placeholderData: HOME_DEFAULTS,
    staleTime: 60_000,
  })
}

export function useAllScenarios() {
  return useQuery({ queryKey: queryKeys.allScenarios, queryFn: listAllScenarios })
}

/** Every business-case write refreshes both the editor list and the home page. */
function useScenarioMutation<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.scenarios })
    },
  })
}

export function useCreateScenario() {
  return useScenarioMutation((input: ScenarioInput) => createScenario(input))
}

export function useUpdateScenario() {
  return useScenarioMutation(({ id, input }: { id: string; input: ScenarioInput }) =>
    updateScenario(id, input),
  )
}

export function useDeleteScenario() {
  return useScenarioMutation((id: string) => deleteScenario(id))
}

export function useReorderScenarios() {
  return useScenarioMutation((ids: string[]) => reorderScenarios(ids))
}

export function useResetScenarios() {
  return useScenarioMutation(() => resetScenarios())
}

export function useSaveHomeContent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (content: HomeContent) => saveHomeContent(content),
    onSuccess: (saved) => queryClient.setQueryData(queryKeys.home, saved),
  })
}

export function useResetHomeContent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => resetHomeContent(),
    onSuccess: (saved) => queryClient.setQueryData(queryKeys.home, saved),
  })
}
