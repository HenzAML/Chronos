import type {
  ConstraintConfig, Course, CourseInput, Equipment, Fix, Grid, Instructor, Room, RoomInput,
  Schedule, TimeSlot,
} from '../types'

/** Error carrying the structured payload the Flask API returns. */
export class ApiError extends Error {
  status: number
  details: string[]

  constructor(message: string, status: number, details: string[] = []) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, {
      headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
      ...init,
    })
  } catch {
    throw new ApiError(
      'Cannot reach the backend. Is the Flask server running on port 5001?', 0,
    )
  }

  if (res.status === 204) return undefined as T

  const text = await res.text()
  let payload: unknown = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      throw new ApiError(`Server returned non-JSON (HTTP ${res.status}).`, res.status)
    }
  }

  if (!res.ok) {
    const err = (payload as { error?: { message?: string; details?: string[] } })?.error
    throw new ApiError(err?.message ?? `Request failed (HTTP ${res.status}).`,
                       res.status, err?.details ?? [])
  }
  return payload as T
}

const get = <T,>(p: string) => request<T>(p)
const post = <T,>(p: string, body?: unknown) =>
  request<T>(p, { method: 'POST', body: JSON.stringify(body ?? {}) })
const patch = <T,>(p: string, body: unknown) =>
  request<T>(p, { method: 'PATCH', body: JSON.stringify(body) })
const put = <T,>(p: string, body: unknown) =>
  request<T>(p, { method: 'PUT', body: JSON.stringify(body) })
const del = (p: string) => request<void>(p, { method: 'DELETE' })

export const api = {
  health: () => get<{ status: string }>('/health'),

  courses: {
    list: () => get<Course[]>('/courses'),
    create: (b: CourseInput) => post<Course>('/courses', b),
    update: (id: number, b: CourseInput) => patch<Course>(`/courses/${id}`, b),
    remove: (id: number) => del(`/courses/${id}`),
  },

  instructors: {
    list: () => get<Instructor[]>('/instructors'),
    create: (b: Partial<Instructor>) => post<Instructor>('/instructors', b),
    update: (id: number, b: Partial<Instructor>) => patch<Instructor>(`/instructors/${id}`, b),
    remove: (id: number) => del(`/instructors/${id}`),
    setAvailability: (id: number, slotIds: number[]) =>
      put<Instructor>(`/instructors/${id}/availability`, { slot_ids: slotIds }),
  },

  rooms: {
    list: () => get<Room[]>('/rooms'),
    create: (b: RoomInput) => post<Room>('/rooms', b),
    update: (id: number, b: RoomInput) => patch<Room>(`/rooms/${id}`, b),
    remove: (id: number) => del(`/rooms/${id}`),
  },

  equipment: {
    list: () => get<Equipment[]>('/equipment'),
    create: (b: { code: string; name: string }) => post<Equipment>('/equipment', b),
    remove: (id: number) => del(`/equipment/${id}`),
  },

  timeslots: {
    list: () => get<TimeSlot[]>('/timeslots'),
    generate: (b: { days: number; start_hour: number; end_hour: number }) =>
      post<{ created: number }>('/timeslots/generate', b),
  },

  constraints: {
    get: () => get<ConstraintConfig>('/constraints'),
    update: (b: Partial<ConstraintConfig>) => put<ConstraintConfig>('/constraints', b),
  },

  schedules: {
    list: () => get<Schedule[]>('/schedules'),
    get: (id: number) => get<Schedule>(`/schedules/${id}`),
    grid: (id: number) => get<Grid>(`/schedules/${id}/grid`),
    suggestions: (id: number) => post<Fix[]>(`/schedules/${id}/suggestions`),
    remove: (id: number) => del(`/schedules/${id}`),
  },

  generate: (b?: Record<string, unknown>) => post<Schedule>('/generate', b),
}
