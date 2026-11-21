import { getAPIUrl } from '@services/config/config'
import { RequestBodyWithAuthHeader, errorHandling } from '@services/utils/ts/requests'
import type {
  CourseGradeResult,
  CourseGrading,
  CourseGradingUpdate,
  CourseGradingUpdateResult,
  Gradebook,
} from '@/lib/grading/types'

// Course-level weighted grading (apps/api/src/routers/courses/grading.py).
// Every call throws on a non-2xx response; the error carries `.status` and the
// backend's `detail` as its message (see errorHandling).

async function request<T>(method: string, path: string, data: unknown, token?: string): Promise<T> {
  const res = await fetch(`${getAPIUrl()}${path}`, RequestBodyWithAuthHeader(method, data, null, token))
  return errorHandling(res)
}

export function getCourseGrading(courseUuid: string, token?: string): Promise<CourseGrading> {
  return request('GET', `courses/${courseUuid}/grading`, null, token)
}

export function updateCourseGrading(
  courseUuid: string,
  body: CourseGradingUpdate,
  token?: string
): Promise<CourseGradingUpdateResult> {
  return request('PUT', `courses/${courseUuid}/grading`, body, token)
}

export function getGradebook(courseUuid: string, token?: string): Promise<Gradebook> {
  return request('GET', `courses/${courseUuid}/gradebook`, null, token)
}

export function getMyCourseGrade(courseUuid: string, token?: string): Promise<CourseGradeResult> {
  return request('GET', `courses/${courseUuid}/grades/me`, null, token)
}

/** The gradebook as CSV text (the caller turns it into a download). */
export async function exportGradebookCsv(courseUuid: string, token?: string): Promise<string> {
  const res = await fetch(
    `${getAPIUrl()}courses/${courseUuid}/gradebook/export`,
    RequestBodyWithAuthHeader('GET', null, null, token)
  )
  if (!res.ok) await errorHandling(res)
  return res.text()
}
