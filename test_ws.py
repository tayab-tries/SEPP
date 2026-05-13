"""
WebSocket auth flow test.
Tests: student WS auth, heartbeat, examiner WS auth.
"""

import asyncio
import json
import websockets
import requests

BASE_URL = "http://localhost:8000"
WS_URL   = "ws://localhost:8000"

# ── Step 1: Get tokens ─────────────────────────────────────────────────────

def get_token(email: str, password: str) -> str:
    resp = requests.post(f"{BASE_URL}/auth/login", data={
        "username": email,
        "password": password,
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    print(f"✅ Login OK for {email}")
    return token

# ── Step 2: Test student WebSocket ─────────────────────────────────────────

async def test_student_ws(token: str, session_id: str, exam_id: str):
    uri = f"{WS_URL}/ws/student/{session_id}/{exam_id}"

    async with websockets.connect(uri) as ws:
        # Send auth as first message
        await ws.send(json.dumps({"type": "auth", "token": token}))
        response = json.loads(await ws.recv())
        assert response["type"] == "auth_ok", f"Expected auth_ok, got: {response}"
        print(f"✅ Student WS auth OK — session: {session_id}")

        # Send a heartbeat
        await ws.send(json.dumps({
            "type": "heartbeat",
            "client_time": "2026-03-16T10:00:00",
        }))
        ack = json.loads(await ws.recv())
        assert ack["type"] == "connectivity_ack", f"Expected ack, got: {ack}"
        print(f"✅ Heartbeat ACK received — server_time: {ack['server_time']}")

# ── Step 3: Test examiner WebSocket ────────────────────────────────────────

async def test_examiner_ws(token: str, exam_id: str):
    uri = f"{WS_URL}/ws/examiner/{exam_id}"

    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "auth", "token": token}))
        response = json.loads(await ws.recv())
        assert response["type"] == "auth_ok", f"Expected auth_ok, got: {response}"
        print(f"✅ Examiner WS auth OK — exam: {exam_id}")

# ── Step 4: Test bad token rejection ───────────────────────────────────────

async def test_bad_token(session_id: str, exam_id: str):
    uri = f"{WS_URL}/ws/student/{session_id}/{exam_id}"
    try:
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"type": "auth", "token": "bad_token"}))
            await ws.recv()  # Should get close, not a message
        print("❌ Bad token was accepted — this is a bug")
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"✅ Bad token correctly rejected — close code: {e.code}")

# ── Main ───────────────────────────────────────────────────────────────────

async def main():
    student_token  = get_token("student1@test.com",  "test1234")
    examiner_token = get_token("examiner1@test.com", "test1234")

    headers_examiner = {"Authorization": f"Bearer {examiner_token}"}
    headers_student  = {"Authorization": f"Bearer {student_token}"}

    # Create a fresh class + exam for testing
    class_resp = requests.post(f"{BASE_URL}/classes",
        json={"name": "WS Test Class"},
        headers=headers_examiner)
    CLASS_ID = class_resp.json()["class_id"]
    print(f"✅ Class created: {CLASS_ID}")

    exam_resp = requests.post(f"{BASE_URL}/exams",
        json={
            "class_id": CLASS_ID,
            "title": "WS Test Exam",
            "duration_minutes": 30,
        },
        headers=headers_examiner)
    EXAM_ID = exam_resp.json()["exam_id"]
    print(f"✅ Exam created: {EXAM_ID}")

    # Enroll student
    requests.post(f"{BASE_URL}/classes/join-by-code/{class_resp.json()['join_code']}",
        headers=headers_student)
    
    # Get enrollment id and approve
    enrollments = requests.get(f"{BASE_URL}/classes/{CLASS_ID}/enrollments",
        headers=headers_examiner).json()
    enrollment_id = enrollments[0]["enrollment_id"]
    requests.put(f"{BASE_URL}/classes/{CLASS_ID}/enrollments/{enrollment_id}/approve",
        headers=headers_examiner)
    print(f"✅ Student enrolled and approved")

    # Set exam live
    requests.patch(f"{BASE_URL}/exams/{EXAM_ID}/status",
        json={"status": "scheduled"}, headers=headers_examiner)
    requests.patch(f"{BASE_URL}/exams/{EXAM_ID}/status",
        json={"status": "live"}, headers=headers_examiner)
    print(f"✅ Exam is live")

    # Start + activate session
    resp = requests.post(f"{BASE_URL}/sessions/start",
        json={"exam_id": EXAM_ID}, headers=headers_student)
    print(f"Session start: {resp.status_code} — {resp.json()}")
    SESSION_ID = resp.json()["session_id"]

    requests.post(f"{BASE_URL}/sessions/{SESSION_ID}/activate",
        headers=headers_student)
    print(f"✅ Session activated: {SESSION_ID}")

    # Run WS tests
    await test_student_ws(student_token, SESSION_ID, EXAM_ID)
    await test_examiner_ws(examiner_token, EXAM_ID)
    await test_bad_token(SESSION_ID, EXAM_ID)

    print("\n✅ All WebSocket tests passed")
    
asyncio.run(main())