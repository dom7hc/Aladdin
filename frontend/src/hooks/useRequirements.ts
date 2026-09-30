import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getRequirements, autofillRequirements } from '@/api/projectApi'
import { getChatMessages, sendChatMessage } from '@/api/chatApi'
import { finalizeRequirements } from '@/api/projectApi'

import { queryKeys } from './queryKeys'

export function useChatMessagesQuery(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.messages(id ?? ''),
    queryFn: () => getChatMessages(id as string),
    enabled: Boolean(id),
  })
}

export function useRequirementsQuery(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.requirements(id ?? ''),
    queryFn: () => getRequirements(id as string),
    enabled: Boolean(id),
  })
}

export function useSendMessage(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (message: string) => sendChatMessage(id, message),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.messages(id) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.requirements(id) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.project(id) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.projects })
    },
  })
}

export function useAutofillRequirements(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => autofillRequirements(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.messages(id) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.requirements(id) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.project(id) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.projects })
    },
  })
}

export function useFinalizeRequirements(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => finalizeRequirements(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.project(id) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.requirements(id) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.projects })
    },
  })
}
