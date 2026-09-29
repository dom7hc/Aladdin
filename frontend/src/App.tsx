import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { ChatPage } from '@/pages/ChatPage'
import { GenerationPage } from '@/pages/GenerationPage'
import { HomePage } from '@/pages/HomePage'
import { RequirementReviewPage } from '@/pages/RequirementReviewPage'
import { ResultPage } from '@/pages/ResultPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 5_000,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/projects/:id" element={<Navigate to="chat" replace />} />
          <Route path="/projects/:id/chat" element={<ChatPage />} />
          <Route path="/projects/:id/review" element={<RequirementReviewPage />} />
          <Route path="/projects/:id/generate" element={<GenerationPage />} />
          <Route path="/projects/:id/result" element={<ResultPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
