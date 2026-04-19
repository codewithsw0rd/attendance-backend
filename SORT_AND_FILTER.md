# Attendance System - Sorting and Filtering Documentation

This document provides comprehensive information about available filters, search fields, and sorting options for each API endpoint.

---

## 📚 Table of Contents
1. [Academics App](#academics-app)
2. [Accounts App](#accounts-app)
3. [Attendance App](#attendance-app)
4. [Query Parameter Guidelines](#query-parameter-guidelines)

---

## Academics App

### 1. Subjects Endpoint
**URL:** `/api/subjects/`

#### Available Filters
- `name` - Subject name (contains, case-insensitive)
- `code` - Subject code (exact match, case-insensitive)
- `department` - Department name (contains, case-insensitive)
- `semester` - Exact semester number
- `semester_range` - Semester range (min,max format)
- `teacher` - Teacher ID (UUID)
- `teacher_name` - Teacher first name (contains, case-insensitive)

#### Search Fields
Search across: `name`, `code`, `department`

**Query Parameter:** `?search=value`

#### Available Sort Fields
| Sort Alias | Field | Description |
|-----------|-------|-------------|
| `id` | id | Subject ID |
| `name` | name | Subject name |
| `code` | code | Subject code |
| `department` | department | Department |
| `semester` | semester | Semester number |
| `teacher_name` | teacher__first_name | Teacher's first name |
| `created_at` | created_at | Created timestamp |
| `updated_at` | updated_at | Updated timestamp |

**Default Sort:** `created_at` (ascending)

**Query Parameter:** `?sort=field1,-field2` (prefix `-` for descending)

#### Examples
```bash
# Get all subjects
GET /api/subjects/

# Filter by department
GET /api/subjects/?department=Engineering

# Filter by semester with range
GET /api/subjects/?semester=3

# Search by name or code
GET /api/subjects/?search=Mathematics

# Filter and search
GET /api/subjects/?department=Engineering&search=Math

# Sort by semester descending
GET /api/subjects/?sort=-semester

# Complex query: Filter, search, and sort
GET /api/subjects/?department=Engineering&teacher_name=John&search=Lab&sort=name

# Filter by teacher
GET /api/subjects/?teacher=550e8400-e29b-41d4-a716-446655440000

# Range filter on semester
GET /api/subjects/?semester_range=2,4
```

---

### 2. Enrollments Endpoint
**URL:** `/api/enrollments/`

#### Available Filters
- `student` - Student ID (UUID)
- `student_roll_number` - Student roll number (contains, case-insensitive)
- `student_department` - Student department (contains, case-insensitive)
- `student_year` - Student year (exact)
- `subject` - Subject ID (UUID)
- `subject_code` - Subject code (exact match, case-insensitive)
- `subject_name` - Subject name (contains, case-insensitive)

#### Search Fields
Search across: `student__roll_number`, `subject__name`, `subject__code`

**Query Parameter:** `?search=value`

#### Available Sort Fields
| Sort Alias | Field | Description |
|-----------|-------|-------------|
| `id` | id | Enrollment ID |
| `student_id` | student__id | Student ID |
| `student_roll_number` | student__roll_number | Student roll number |
| `student_department` | student__department | Student department |
| `student_year` | student__year | Student year |
| `subject_id` | subject__id | Subject ID |
| `subject_name` | subject__name | Subject name |
| `subject_code` | subject__code | Subject code |
| `created_at` | created_at | Created timestamp |
| `updated_at` | updated_at | Updated timestamp |

**Default Sort:** `created_at` (ascending)

**Query Parameter:** `?sort=field1,-field2`

#### Examples
```bash
# Get all enrollments
GET /api/enrollments/

# Filter by student roll number
GET /api/enrollments/?student_roll_number=CS001

# Filter by subject
GET /api/enrollments/?subject=550e8400-e29b-41d4-a716-446655440000

# Filter by student year
GET /api/enrollments/?student_year=2

# Search by subject code
GET /api/enrollments/?search=CSE101

# Filter by department and sort
GET /api/enrollments/?student_department=Engineering&sort=student_roll_number

# Complex query: Filter by subject and search for student
GET /api/enrollments/?subject_code=CS201&search=CS001&sort=-created_at

# Filter by student and subject
GET /api/enrollments/?student=550e8400-e29b-41d4-a716-446655440000&subject_name=Database
```

---

### 3. Class Sessions Endpoint
**URL:** `/api/class-sessions/`

#### Available Filters
- `subject` - Subject ID (UUID)
- `subject_name` - Subject name (contains, case-insensitive)
- `subject_code` - Subject code (exact match, case-insensitive)
- `class_name` - Class name (contains, case-insensitive)
- `date` - Exact date (YYYY-MM-DD)
- `date_after` - Date from (YYYY-MM-DD, inclusive)
- `date_before` - Date until (YYYY-MM-DD, inclusive)
- `date_range` - Date range (startDate,endDate format)
- `start_time` - Start time (HH:MM:SS)
- `end_time` - End time (HH:MM:SS)

#### Search Fields
Search across: `class_name`, `subject__name`, `subject__code`

**Query Parameter:** `?search=value`

#### Available Sort Fields
| Sort Alias | Field | Description |
|-----------|-------|-------------|
| `id` | id | Session ID |
| `subject_id` | subject__id | Subject ID |
| `subject_name` | subject__name | Subject name |
| `subject_code` | subject__code | Subject code |
| `class_name` | class_name | Class name |
| `date` | date | Session date |
| `start_time` | start_time | Start time |
| `end_time` | end_time | End time |
| `created_at` | created_at | Created timestamp |
| `updated_at` | updated_at | Updated timestamp |

**Default Sort:** `-date, start_time` (latest date first, then by start time)

**Query Parameter:** `?sort=field1,-field2`

#### Examples
```bash
# Get all class sessions
GET /api/class-sessions/

# Filter by exact date
GET /api/class-sessions/?date=2024-01-15

# Filter by date range
GET /api/class-sessions/?date_after=2024-01-01&date_before=2024-12-31

# Filter by subject
GET /api/class-sessions/?subject=550e8400-e29b-41d4-a716-446655440000

# Search by class name
GET /api/class-sessions/?search=Lab

# Filter by subject code
GET /api/class-sessions/?subject_code=CS201

# Filter by date and sort
GET /api/class-sessions/?date_range=2024-01-01,2024-12-31&sort=start_time

# Complex query: Date range, subject, and search
GET /api/class-sessions/?date_after=2024-06-01&subject_name=Mathematics&search=Theory&sort=-date

# Filter by time range
GET /api/class-sessions/?start_time=09:00:00&end_time=12:00:00
```

---

## Accounts App

### 1. Students Endpoint
**URL:** `/api/students/`

#### Available Filters
- `email` - User email (contains, case-insensitive)
- `roll_number` - Roll number (contains, case-insensitive)
- `department` - Department (contains, case-insensitive)
- `year` - Exact year
- `year_range` - Year range (min,max format)
- `first_name` - First name (contains, case-insensitive)
- `last_name` - Last name (contains, case-insensitive)
- `is_active` - Active status (true/false)

#### Search Fields
Search across: `user__email`, `roll_number`, `first_name`, `last_name`, `department`

**Query Parameter:** `?search=value`

#### Available Sort Fields
| Sort Alias | Field | Description |
|-----------|-------|-------------|
| `id` | id | Student ID |
| `email` | user__email | Email address |
| `roll_number` | roll_number | Roll number |
| `department` | department | Department |
| `year` | year | Academic year |
| `first_name` | first_name | First name |
| `last_name` | last_name | Last name |
| `created_at` | created_at | Created timestamp |
| `updated_at` | updated_at | Updated timestamp |

**Default Sort:** `roll_number` (ascending)

**Query Parameter:** `?sort=field1,-field2`

#### Examples
```bash
# Get all students
GET /api/students/

# Filter by department
GET /api/students/?department=Engineering

# Filter by year
GET /api/students/?year=2

# Search by email
GET /api/students/?search=student@email.com

# Filter by active status
GET /api/students/?is_active=true

# Filter by year range
GET /api/students/?year_range=1,3

# Search by name
GET /api/students/?search=John

# Filter and search
GET /api/students/?department=Engineering&search=john@email.com

# Sort by first name
GET /api/students/?sort=first_name

# Complex query: Filter, search, and sort
GET /api/students/?department=Engineering&year=2&search=john&sort=-created_at

# Filter by department and sort by roll number descending
GET /api/students/?department=CSE&sort=-roll_number
```

---

### 2. Teachers Endpoint
**URL:** `/api/teachers/`

#### Available Filters
- `email` - User email (contains, case-insensitive)
- `employee_id` - Employee ID (contains, case-insensitive)
- `department` - Department (contains, case-insensitive)
- `first_name` - First name (contains, case-insensitive)
- `last_name` - Last name (contains, case-insensitive)
- `is_active` - Active status (true/false)

#### Search Fields
Search across: `user__email`, `employee_id`, `first_name`, `last_name`, `department`

**Query Parameter:** `?search=value`

#### Available Sort Fields
| Sort Alias | Field | Description |
|-----------|-------|-------------|
| `id` | id | Teacher ID |
| `email` | user__email | Email address |
| `employee_id` | employee_id | Employee ID |
| `department` | department | Department |
| `first_name` | first_name | First name |
| `last_name` | last_name | Last name |
| `created_at` | created_at | Created timestamp |
| `updated_at` | updated_at | Updated timestamp |

**Default Sort:** `employee_id` (ascending)

**Query Parameter:** `?sort=field1,-field2`

#### Examples
```bash
# Get all teachers
GET /api/teachers/

# Filter by department
GET /api/teachers/?department=Engineering

# Search by email
GET /api/teachers/?search=teacher@email.com

# Filter by active status
GET /api/teachers/?is_active=true

# Search by name
GET /api/teachers/?search=John

# Filter by department and search
GET /api/teachers/?department=Engineering&search=john

# Sort by last name
GET /api/teachers/?sort=last_name

# Complex query: Filter and sort by creation date
GET /api/teachers/?department=CSE&is_active=true&sort=-created_at

# Search and sort by employee ID descending
GET /api/teachers/?search=emp&sort=-employee_id
```

---

### 3. Admins Endpoint
**URL:** `/api/admins/`

#### Available Filters
- `email` - User email (contains, case-insensitive)
- `first_name` - First name (contains, case-insensitive)
- `last_name` - Last name (contains, case-insensitive)
- `is_active` - Active status (true/false)

#### Search Fields
Search across: `user__email`, `first_name`, `last_name`

**Query Parameter:** `?search=value`

#### Available Sort Fields
| Sort Alias | Field | Description |
|-----------|-------|-------------|
| `id` | id | Admin ID |
| `email` | user__email | Email address |
| `first_name` | first_name | First name |
| `last_name` | last_name | Last name |
| `created_at` | created_at | Created timestamp |
| `updated_at` | updated_at | Updated timestamp |

**Default Sort:** `created_at` (ascending)

**Query Parameter:** `?sort=field1,-field2`

#### Examples
```bash
# Get all admins
GET /api/admins/

# Search by email
GET /api/admins/?search=admin@email.com

# Filter by active status
GET /api/admins/?is_active=true

# Search by name
GET /api/admins/?search=John

# Sort by creation date descending
GET /api/admins/?sort=-created_at

# Complex query: Search and sort
GET /api/admins/?search=john&is_active=true&sort=last_name
```

---

## Attendance App

### 1. Face Data Endpoint
**URL:** `/api/face-data/`

#### Available Filters
- `student` - Student ID (UUID)
- `student_email` - Student email (contains, case-insensitive)
- `student_roll_number` - Student roll number (contains, case-insensitive)
- `is_enrolled` - Enrollment status (true/false)
- `total_photos_registered` - Exact photo count
- `total_photos_registered_min` - Minimum photos registered
- `total_photos_registered_max` - Maximum photos registered
- `registration_confidence` - Exact confidence score (0-1)
- `registration_confidence_min` - Minimum confidence score
- `registration_confidence_max` - Maximum confidence score

#### Search Fields
Search across: `student__user__email`, `student__roll_number`

**Query Parameter:** `?search=value`

#### Available Sort Fields
| Sort Alias | Field | Description |
|-----------|-------|-------------|
| `id` | id | Face data ID |
| `student_id` | student__id | Student ID |
| `student_email` | student__user__email | Student email |
| `student_roll_number` | student__roll_number | Student roll number |
| `is_enrolled` | is_enrolled | Enrollment status |
| `total_photos_registered` | total_photos_registered | Photo count |
| `registration_confidence` | registration_confidence | Confidence score |
| `created_at` | created_at | Created timestamp |
| `updated_at` | updated_at | Updated timestamp |

**Default Sort:** `-created_at` (latest first)

**Query Parameter:** `?sort=field1,-field2`

#### Examples
```bash
# Get all face data
GET /api/face-data/

# Filter enrolled students only
GET /api/face-data/?is_enrolled=true

# Filter students with minimum confidence
GET /api/face-data/?registration_confidence_min=0.8

# Filter by student roll number
GET /api/face-data/?student_roll_number=CS001

# Search by email
GET /api/face-data/?search=student@email.com

# Filter by photos count
GET /api/face-data/?total_photos_registered=5

# Complex query: Filter and sort
GET /api/face-data/?is_enrolled=true&registration_confidence_min=0.7&sort=-registration_confidence

# Filter by confidence range
GET /api/face-data/?registration_confidence_min=0.6&registration_confidence_max=0.95

# Filter enrolled and search
GET /api/face-data/?is_enrolled=true&search=CS001&sort=student_roll_number
```

---

### 2. Attendance Endpoint
**URL:** `/api/attendances/`

#### Available Filters
- `student` - Student ID (UUID)
- `student_email` - Student email (contains, case-insensitive)
- `student_roll_number` - Student roll number (contains, case-insensitive)
- `class_session` - Class session ID (UUID)
- `class_session_name` - Class session name (contains, case-insensitive)
- `subject` - Subject ID (UUID)
- `subject_code` - Subject code (exact match, case-insensitive)
- `status` - Attendance status (PRESENT/ABSENT)
- `marked_at` - Exact marked time (ISO format)
- `marked_at_after` - Marked from (ISO datetime)
- `marked_at_before` - Marked until (ISO datetime)
- `marked_at_range` - Date range (startDate,endDate format)
- `class_date` - Exact class date (YYYY-MM-DD)
- `class_date_after` - Class date from (YYYY-MM-DD)
- `class_date_before` - Class date until (YYYY-MM-DD)
- `class_date_range` - Class date range (startDate,endDate format)

#### Search Fields
Search across: `student__user__email`, `student__roll_number`, `class_session__class_name`

**Query Parameter:** `?search=value`

#### Available Sort Fields
| Sort Alias | Field | Description |
|-----------|-------|-------------|
| `id` | id | Attendance ID |
| `student_id` | student__id | Student ID |
| `student_email` | student__user__email | Student email |
| `student_roll_number` | student__roll_number | Student roll number |
| `class_session_id` | class_session__id | Class session ID |
| `class_session_name` | class_session__class_name | Class name |
| `class_date` | class_session__date | Class date |
| `status` | status | Attendance status |
| `marked_at` | marked_at | Marked timestamp |
| `created_at` | created_at | Created timestamp |
| `updated_at` | updated_at | Updated timestamp |

**Default Sort:** `-marked_at` (latest marked first)

**Query Parameter:** `?sort=field1,-field2`

#### Examples
```bash
# Get all attendance records
GET /api/attendances/

# Filter by status
GET /api/attendances/?status=PRESENT

# Filter by student roll number
GET /api/attendances/?student_roll_number=CS001

# Filter by date
GET /api/attendances/?class_date=2024-01-15

# Filter by date range
GET /api/attendances/?class_date_after=2024-01-01&class_date_before=2024-12-31

# Search by student
GET /api/attendances/?search=student@email.com

# Filter by subject
GET /api/attendances/?subject_code=CSE101

# Complex query: Filter by student, status, and date range
GET /api/attendances/?student_roll_number=CS001&status=PRESENT&class_date_range=2024-01-01,2024-12-31

# Sort by marked time descending
GET /api/attendances/?sort=-marked_at

# Filter present attendances by date range and sort
GET /api/attendances/?status=PRESENT&class_date_after=2024-06-01&sort=student_roll_number

# Filter by class session
GET /api/attendances/?class_session=550e8400-e29b-41d4-a716-446655440000

# Search and sort
GET /api/attendances/?search=Lab&sort=-class_date
```

---

### 3. Attendance Logs Endpoint
**URL:** `/api/attendance-logs/`

#### Available Filters
- `attendance` - Attendance ID (UUID)
- `student` - Student ID (UUID)
- `student_email` - Student email (contains, case-insensitive)
- `class_session` - Class session ID (UUID)
- `liveness_passed` - Liveness status (PASS/FAIL/UNKNOWN)
- `face_confidence` - Exact confidence score (0-1)
- `face_confidence_min` - Minimum face confidence
- `face_confidence_max` - Maximum face confidence
- `distance_to_nearest` - Exact distance
- `distance_to_nearest_min` - Minimum distance to nearest
- `distance_to_nearest_max` - Maximum distance to nearest
- `best_matching_photo_number` - Photo number used
- `distance_from_classroom` - Exact distance from classroom
- `distance_from_classroom_min` - Minimum distance from classroom
- `distance_from_classroom_max` - Maximum distance from classroom

#### Search Fields
Search across: `attendance__student__user__email`, `attendance__student__roll_number`

**Query Parameter:** `?search=value`

#### Available Sort Fields
| Sort Alias | Field | Description |
|-----------|-------|-------------|
| `id` | id | Log ID |
| `attendance_id` | attendance__id | Attendance ID |
| `student_id` | attendance__student__id | Student ID |
| `student_email` | attendance__student__user__email | Student email |
| `student_roll_number` | attendance__student__roll_number | Student roll number |
| `class_session_id` | attendance__class_session__id | Class session ID |
| `class_session_name` | attendance__class_session__class_name | Class name |
| `face_confidence` | face_confidence | Face confidence score |
| `distance_to_nearest` | distance_to_nearest | Distance to nearest |
| `liveness_passed` | liveness_passed | Liveness status |
| `created_at` | created_at | Created timestamp |
| `updated_at` | updated_at | Updated timestamp |

**Default Sort:** `-created_at` (latest first)

**Query Parameter:** `?sort=field1,-field2`

#### Examples
```bash
# Get all attendance logs
GET /api/attendance-logs/

# Filter by liveness status
GET /api/attendance-logs/?liveness_passed=PASS

# Filter by minimum face confidence
GET /api/attendance-logs/?face_confidence_min=0.8

# Filter by confidence range
GET /api/attendance-logs/?face_confidence_min=0.7&face_confidence_max=0.99

# Search by student email
GET /api/attendance-logs/?search=student@email.com

# Filter failed liveness checks
GET /api/attendance-logs/?liveness_passed=FAIL

# Filter by distance from classroom
GET /api/attendance-logs/?distance_from_classroom_max=100

# Complex query: Filter by liveness and confidence
GET /api/attendance-logs/?liveness_passed=PASS&face_confidence_min=0.8&sort=-face_confidence

# Sort by distance to nearest (ascending)
GET /api/attendance-logs/?sort=distance_to_nearest

# Filter suspicious patterns
GET /api/attendance-logs/?face_confidence_max=0.5&liveness_passed=FAIL&sort=-created_at

# Filter by best matching photo
GET /api/attendance-logs/?best_matching_photo_number=3

# Search and filter
GET /api/attendance-logs/?search=CS001&liveness_passed=PASS&sort=-created_at
```

---

## Query Parameter Guidelines

### General Rules
1. **Multiple filters** can be combined using `&` separator
2. **Search** and **filters** work together for refined results
3. **Sorting** can be applied independently or with filters/search
4. **Case-insensitive** lookups apply to text fields (name, email, etc.)
5. **Exact match** filters ignore case variations

### Parameter Types

#### Filter Parameters
- `filter_name=value` - Single value filter
- `filter_name_min=value&filter_name_max=value` - Range filter
- `filter_name_range=start,end` - Date/date-time range filter

#### Search Parameter
- `search=keyword` - Searches across configured search fields

#### Sort Parameter
- `sort=field` - Ascending order
- `sort=-field` - Descending order
- `sort=field1,-field2,field3` - Multiple fields

### Best Practices
1. **URL Encoding**: Encode special characters in parameters
2. **Date Format**: Use ISO 8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
3. **UUIDs**: Use full UUID format (550e8400-e29b-41d4-a716-446655440000)
4. **Boolean**: Use `true` or `false` (lowercase)
5. **Pagination**: Combine with `?page=n` for paginated results

### Common Query Patterns

#### Pattern 1: Simple Filter
```
GET /api/endpoint/?field=value
```

#### Pattern 2: Multiple Filters
```
GET /api/endpoint/?field1=value1&field2=value2
```

#### Pattern 3: Search with Filter
```
GET /api/endpoint/?field=value&search=keyword
```

#### Pattern 4: Range Filter
```
GET /api/endpoint/?field_min=10&field_max=100
```

#### Pattern 5: Filter with Sort
```
GET /api/endpoint/?field=value&sort=-created_at
```

#### Pattern 6: Complex Query
```
GET /api/endpoint/?field1=value1&field2_min=10&field2_max=100&search=keyword&sort=-field3,field4
```

---

## Response Format

All endpoints return JSON responses with pagination metadata:

```json
{
  "count": 100,
  "next": "https://api.example.com/api/endpoint/?page=2",
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "field1": "value1",
      "field2": "value2"
    }
  ]
}
```

---

## Error Handling

### Common Errors
- **400 Bad Request**: Invalid filter/sort parameter
- **401 Unauthorized**: Missing or invalid authentication
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Resource not found
- **500 Server Error**: Internal server error

### Error Response Format
```json
{
  "detail": "Error message describing the issue"
}
```

---

**Last Updated:** April 19, 2026  
**Version:** 1.0.0
