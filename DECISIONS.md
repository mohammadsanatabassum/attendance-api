# DECISIONS.md

1. **Indexes.**
   - `employees.emp_code` (unique): Guarantees unique employee codes and provides instant point lookups.
   - `employees.department` and `employees.joined_on`: Accelerates filtering by department and period-eligibility cutoffs (R9).
   - `attendance_logs.(emp_code, date)` (unique): Enforces at most one record per employee-day and guarantees concurrency safety.
   - `attendance_logs.(date, -1, emp_code, 1)`: Backs date-range filtering and deterministic pagination sort on `/attendance`.
   - `attendance_logs.(date, 1, late_minutes, 1, emp_code, 1)`: Enables `IXSCAN` coverage for the late-comers leaderboard.
   - `attendance_logs.(emp_code, 1, punch_in, -1)`: Quickly finds the latest open punch-in during punch-out.
   - *Considered and rejected:* A wide covering index on `attendance_logs` containing all derived fields. It would heavily penalize insert/update throughput and bloat RAM for marginal benefit.

2. **Punch-in race.**
   Both concurrent requests compute the attendance date and execute an `insert_one`. MongoDB's unique index on `(emp_code, date)` guarantees atomic serialization. Exactly one insert succeeds and receives HTTP 201. The second insert raises a `DuplicateKeyError` at the database level, which our code catches and translates into HTTP 409 Conflict without using unsafe application check-then-insert logic.

3. **Ties.**
   The query uses MongoDB's `$setWindowFields` with competition ranking (`$rank`). Tied employees receive the same rank number (e.g., two tied at rank 10). Because the requirement states `rank <= limit`, both employees are returned, expanding the response beyond `limit`, sorted by `total_late_minutes` descending and `emp_code` ascending.

4. **Headcount.**
   The aggregation pipeline starts on the `employees` collection (filtering `joined_on <= period_end`), then `$lookup`s matching `attendance_logs`. Grouping by department counts every eligible employee (`$sum: 1`), ensuring employees with zero attendance records are fully counted.

5. **One thing you would change at 100x scale.**
   I would maintain pre-aggregated daily/monthly rollups in an `attendance_rollups` collection updated asynchronously via MongoDB Change Streams or write triggers, replacing real-time multi-collection pipeline scans with simple indexed reads.
