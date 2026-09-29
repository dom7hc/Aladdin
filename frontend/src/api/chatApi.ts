import type { ChatMessage, RequirementResponse } from '@/types'

import { apiFetch } from './httpClient'

export function getChatMessages(id: string): Promise<ChatMessage[]> {
  return apiFetch<ChatMessage[]>(`/projects/${id}/chat`)
}

export function sendChatMessage(
  id: string,
  message: string,
): Promise<RequirementResponse> {
  return apiFetch<RequirementResponse>(`/projects/${id}/chat`, {
    method: 'POST',
    body: { message },
  })
}
