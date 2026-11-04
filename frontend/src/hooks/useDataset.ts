import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { deleteDataset, getDataset, uploadDataset } from '@/api/projectApi'
import { ApiError } from '@/api/errors'
import type { DatasetInfo } from '@/types'

import { queryKeys } from './queryKeys'

/** The project's uploaded file, or null when there is none (a 404). */
export function useDatasetQuery(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.dataset(id ?? ''),
    queryFn: async (): Promise<DatasetInfo | null> => {
      try {
        return await getDataset(id as string)
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null
        throw error
      }
    },
    enabled: Boolean(id),
  })
}

export function useUploadDataset(id: string | undefined) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => uploadDataset(id as string, file),
    onSuccess: (dataset: DatasetInfo) => {
      client.setQueryData(queryKeys.dataset(id ?? ''), dataset)
    },
  })
}

export function useDeleteDataset(id: string | undefined) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => deleteDataset(id as string),
    onSuccess: () => {
      client.setQueryData(queryKeys.dataset(id ?? ''), null)
    },
  })
}
