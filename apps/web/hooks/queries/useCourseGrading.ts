'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { queryKeys } from '@lib/query/keys'
import { getCourseGrading, getMyCourseGrade, updateCourseGrading } from '@services/courses/grading'
import type { CourseGradingUpdate } from '@/lib/grading/types'

function useAccessToken(): string | undefined {
  const session = useLHSession() as any
  return session?.data?.tokens?.access_token as string | undefined
}

/** The course's grading setup. courseUuid is the full `course_...` uuid. */
export function useCourseGrading(courseUuid?: string) {
  const token = useAccessToken()
  return useQuery({
    queryKey: queryKeys.grading.setup(courseUuid!),
    queryFn: () => getCourseGrading(courseUuid!, token),
    enabled: !!courseUuid && !!token,
    staleTime: 30_000,
    retry: false,
  })
}

/** Save the whole setup; refreshes every grading view of the course. */
export function useSaveCourseGrading(courseUuid?: string) {
  const token = useAccessToken()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CourseGradingUpdate) => updateCourseGrading(courseUuid!, body, token),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.grading.setup(courseUuid!), data)
      queryClient.invalidateQueries({ queryKey: ['grading', courseUuid] })
    },
  })
}

/**
 * The signed-in learner's own course grade. Pass enabled=false for anyone who
 * is not an enrolled learner, so the page never asks on their behalf.
 */
export function useMyCourseGrade(courseUuid?: string, enabled = true) {
  const token = useAccessToken()
  return useQuery({
    queryKey: queryKeys.grading.mine(courseUuid!),
    queryFn: () => getMyCourseGrade(courseUuid!, token),
    enabled: enabled && !!courseUuid && !!token,
    staleTime: 30_000,
    retry: false,
  })
}
