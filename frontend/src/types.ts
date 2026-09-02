/** Mirrors backend/app/api/helpers.py serializers. */

export const SESSION_TYPES = ['lecture', 'lab', 'group', 'seminar', 'meeting'] as const
export type SessionType = (typeof SESSION_TYPES)[number]

export const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

export const CAPABILITIES = [
  { key: 'supports_lecture', label: 'Lecture', session: 'lecture' },
  { key: 'supports_lab', label: 'Lab', session: 'lab' },
  { key: 'supports_group', label: 'Group', session: 'group' },
  { key: 'supports_seminar', label: 'Seminar', session: 'seminar' },
  { key: 'supports_meeting', label: 'Meeting', session: 'meeting' },
] as const

export type CapabilityKey = (typeof CAPABILITIES)[number]['key']

export interface TimeSlot {
  id: number
  day: number
  hour: number
  label: string
}

export interface Equipment {
  id: number
  code: string
  name: string
}

export interface Room {
  id: number
  code: string
  name: string | null
  capacity: number
  supports_lecture: boolean
  supports_lab: boolean
  supports_group: boolean
  supports_seminar: boolean
  supports_meeting: boolean
  equipment: Equipment[]
}

export interface Instructor {
  id: number
  name: string
  email: string | null
  prefer_morning: boolean
  preferred_days: number[]
  availability_slot_ids?: number[]
  course_count?: number
}

export interface EquipmentRequirement {
  equipment_id: number
  code: string
  name: string
  is_essential: boolean
}

export interface Course {
  id: number
  code: string
  name: string
  instructor_id: number
  duration_hours: number
  expected_students: number
  session_type: SessionType
  instructor?: Instructor | null
  equipment_requirements?: EquipmentRequirement[]
}

export interface ConstraintConfig {
  enable_h2_room_conflict: boolean
  enable_h3_instructor_conflict: boolean
  enable_h4_capacity: boolean
  enable_h5_availability: boolean
  enable_h6_essential_equipment: boolean
  w1_morning: number
  w2_preferred_day: number
  w3_equipment: number
  w4_room_type: number
  solver_time_limit_seconds: number
}

export interface Assignment {
  id: number
  course: {
    id: number
    code: string
    name: string
    session_type: SessionType
    expected_students: number
    instructor: string | null
  }
  room: { id: number; code: string; capacity: number }
  time_slot: TimeSlot
}

export type ScheduleStatus = 'pending' | 'optimal' | 'feasible' | 'infeasible' | 'failed'

export interface PenaltyBreakdown {
  S1_morning: number
  S2_preferred_day: number
  S3_equipment: number
  S4_room_type: number
  S1_morning_count: number
  S2_preferred_day_count: number
  S3_equipment_count: number
  S4_room_type_count: number
}

export interface Schedule {
  id: number
  name: string | null
  algorithm: string
  status: ScheduleStatus
  hard_violations: number
  soft_score: number | null
  optimality_gap: number | null
  solve_seconds: number | null
  weights: {
    w1_morning: number
    w2_preferred_day: number
    w3_equipment: number
    w4_room_type: number
  }
  message: string | null
  created_at: string | null
  assignment_count: number
  assignments?: Assignment[]
  diagnostics?: {
    num_variables: number
    pruned_triples: number
    penalty_breakdown: PenaltyBreakdown
  }
}

export interface Grid {
  schedule: Schedule
  hours: number[]
  days: number[]
  grid: Record<string, Record<string, Assignment[]>>
}

/* ---- write payloads -------------------------------------------------
   The shape you SEND differs from the shape you GET back: requirements go
   out as {equipment_id, is_essential} and come back enriched with code/name. */

export interface EquipmentRequirementInput {
  equipment_id: number
  is_essential: boolean
}

export type CourseInput = Partial<Omit<Course, 'equipment_requirements' | 'instructor'>> & {
  equipment_requirements?: EquipmentRequirementInput[]
}

export type RoomInput = Partial<Omit<Room, 'equipment'>> & {
  equipment_ids?: number[]
}
