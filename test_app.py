import httpx
from fastapi.testclient import TestClient
from app.main import app, db

client = TestClient(app)

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    print("Health passed!")

def test_list_employees():
    res = client.get("/employees")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 6
    assert data["items"][0]["emp_code"] == "EMP0001"
    assert "_id" not in data["items"][0]
    assert isinstance(data["items"][0]["created_at"], int)
    print("List employees passed!")

def test_create_employee():
    # Valid
    payload = {
        "emp_code": "EMP9999",
        "name": "Test User",
        "email": "test@example.com",
        "department": "Engineering",
        "shift_start": "09:30",
        "shift_end": "18:30",
        "joined_on": "2026-07-01"
    }
    # Clean up if exists
    db.employees.delete_one({"emp_code": "EMP9999"})
    res = client.post("/employees", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["emp_code"] == "EMP9999"
    assert isinstance(data["created_at"], int)

    # Duplicate -> 409
    res_dup = client.post("/employees", json=payload)
    assert res_dup.status_code == 409

    # Equal shift_start and shift_end -> 422
    payload_bad = dict(payload)
    payload_bad["emp_code"] = "EMP9998"
    payload_bad["shift_end"] = "09:30"
    res_bad = client.post("/employees", json=payload_bad)
    assert res_bad.status_code == 422

    # Clean up
    db.employees.delete_one({"emp_code": "EMP9999"})
    print("Create employee passed!")

def test_punch_in_and_out():
    # Clean up test attendance
    db.attendance_logs.delete_many({"emp_code": "EMP0001", "date": "2026-09-01"})

    # Punch in at 09:45 IST on 2026-09-01 -> late_minutes = 15
    # 09:45 IST = 04:15 UTC -> 2026-09-01T04:15:00Z
    # 2026-09-01 04:15:00 UTC epoch ms = 1788236100000
    punched_at_in = 1788236100000
    res_in = client.post("/attendance/punch-in", json={
        "emp_code": "EMP0001",
        "punched_at": punched_at_in,
        "status": "PRESENT"
    })
    assert res_in.status_code == 201
    in_data = res_in.json()
    assert in_data["emp_code"] == "EMP0001"
    assert in_data["date"] == "2026-09-01"
    assert in_data["late_minutes"] == 15
    assert in_data["punch_out"] is None
    assert in_data["work_hours"] is None
    assert in_data["history"] == []

    # Duplicate punch-in for same day -> 409
    res_dup = client.post("/attendance/punch-in", json={
        "emp_code": "EMP0001",
        "punched_at": punched_at_in,
        "status": "PRESENT"
    })
    assert res_dup.status_code == 409

    # Punch out at 19:10 IST -> 13:40 UTC -> 1788270000000
    # Overtime: shift end 18:30 IST, punch out 19:10 IST -> 40 min overtime
    # Work hours: 04:15 to 13:40 = 9h 25m = 9.42 hours
    punched_at_out = 1788270000000
    res_out = client.post("/attendance/punch-out", json={
        "emp_code": "EMP0001",
        "punched_at": punched_at_out
    })
    assert res_out.status_code == 200
    out_data = res_out.json()
    assert out_data["work_hours"] == 9.42
    assert out_data["overtime_minutes"] == 40
    assert out_data["half_day"] is False

    # Second punch out -> 409
    res_out2 = client.post("/attendance/punch-out", json={
        "emp_code": "EMP0001",
        "punched_at": punched_at_out
    })
    assert res_out2.status_code == 409

    # Clean up
    db.attendance_logs.delete_many({"emp_code": "EMP0001", "date": "2026-09-01"})
    print("Punch in and punch out passed!")

def test_regularize_patch():
    # Setup test record
    db.attendance_logs.delete_many({"emp_code": "EMP0001", "date": "2026-09-02"})
    client.post("/attendance/punch-in", json={
        "emp_code": "EMP0001",
        "punched_at": 1788322500000, # 09:45 IST
        "status": "PRESENT"
    })

    # Regularize punch_in to 09:28 IST (1788321480000)
    res_patch = client.patch("/attendance/EMP0001/2026-09-02", json={
        "punch_in": 1788321480000,
        "reason": "biometric malfunction",
        "regularized_by": "hr_manager"
    })
    assert res_patch.status_code == 200
    patch_data = res_patch.json()
    assert patch_data["late_minutes"] == 0
    assert len(patch_data["history"]) == 1
    assert patch_data["history"][0]["by"] == "hr_manager"
    assert "late_minutes" in patch_data["history"][0]["changes"]

    # Request changing nothing -> 422
    res_noop = client.patch("/attendance/EMP0001/2026-09-02", json={
        "reason": "noop attempt",
        "regularized_by": "hr_manager"
    })
    assert res_noop.status_code == 422

    # Clean up
    db.attendance_logs.delete_many({"emp_code": "EMP0001", "date": "2026-09-02"})
    print("Regularize passed!")

def test_analytics_endpoints():
    # Monthly
    res = client.get("/analytics/employees/EMP0001/monthly?month=2026-07")
    assert res.status_code == 200
    m_data = res.json()
    assert m_data["emp_code"] == "EMP0001"
    assert m_data["working_days"] == 23 # July 2026 weekdays
    assert m_data["present_days"] >= 2.0
    print("Monthly analytics passed!")

    # Department summary
    res_dept = client.get("/analytics/departments/summary?month=2026-07")
    assert res_dept.status_code == 200
    d_data = res_dept.json()
    assert len(d_data["items"]) >= 3
    print("Department summary passed!")

    # Leaderboard
    res_lead = client.get("/analytics/leaderboard/late?month=2026-07")
    assert res_lead.status_code == 200
    l_data = res_lead.json()
    assert "items" in l_data
    if l_data["items"]:
        assert l_data["items"][0]["rank"] == 1
    print("Leaderboard passed!")

    # Trend
    res_trend = client.get("/analytics/departments/Engineering/trend?from=2026-07-06&to=2026-07-10")
    assert res_trend.status_code == 200
    t_data = res_trend.json()
    assert len(t_data["items"]) == 5
    print("Trend passed!")

def test_explain_endpoints():
    for ep, params in [
        ("attendance_list", ""),
        ("employee_monthly", "?emp_code=EMP0001&month=2026-07"),
        ("department_summary", "?month=2026-07"),
        ("late_leaderboard", "?month=2026-07"),
        ("department_trend", "?department=Engineering&from=2026-07-06&to=2026-07-10")
    ]:
        res = client.get(f"/admin/explain/{ep}{params}")
        assert res.status_code == 200, f"Explain failed for {ep}: {res.text}"
        data = res.json()
        assert "explain" in data
        assert "collection" in data
        print(f"Explain {ep} passed on {data['collection']}!")

if __name__ == "__main__":
    test_health()
    test_list_employees()
    test_create_employee()
    test_punch_in_and_out()
    test_regularize_patch()
    test_analytics_endpoints()
    test_explain_endpoints()
    print("ALL TESTS PASSED SUCCESSFULLY!")
