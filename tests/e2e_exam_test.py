import os
import sys

# Force all client API config imports to use port 8005 during E2E test run
os.environ["API_BASE_URL"] = "http://localhost:8005"

import time
import requests
import json
import pytest
import asyncio
import threading
import subprocess

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

BASE_URL = "http://localhost:8005"

@pytest.fixture(scope="module")
def setup_test_data():
    # Call the setup script using the server's venv python to populate DB
    if sys.platform == "win32":
        server_python = os.path.join(os.path.dirname(__file__), "..", "server", ".venv", "Scripts", "python.exe")
    else:
        server_python = os.path.join(os.path.dirname(__file__), "..", "server", "venv", "bin", "python")
    setup_script = os.path.join(os.path.dirname(__file__), "e2e_setup.py")
    subprocess.run([server_python, setup_script], check=True)
    yield ("test_examiner@mail.com", "test_student@mail.com")

def test_e2e_exam_flow(qtbot, setup_test_data, monkeypatch):
    examiner_email, student_email = setup_test_data

    # =========================================================================
    # 1. Examiner API Flow (Setup Class & Exam)
    # =========================================================================
    start_time = time.time()
    resp = requests.post(f"{BASE_URL}/auth/login", data={"username": examiner_email, "password": "password"})
    assert resp.status_code == 200
    examiner_token = resp.json()["access_token"]
    assert (time.time() - start_time) < 30.0, f"Examiner login latency exceeded SLA: {time.time() - start_time}s"

    # Create Class
    resp = requests.post(f"{BASE_URL}/classes", json={"name": "E2E Test Class"}, headers={"Authorization": f"Bearer {examiner_token}"})
    assert resp.status_code == 201
    class_data = resp.json()
    class_id = class_data["class_id"]
    join_code = class_data["join_code"]

    # Create Exam
    resp = requests.post(f"{BASE_URL}/exams", json={
        "class_id": class_id,
        "title": "E2E Test Exam",
        "duration_minutes": 10,
        "require_liveness_check": True,
        "max_window_switches": 3
    }, headers={"Authorization": f"Bearer {examiner_token}"})
    assert resp.status_code == 201
    exam_id = resp.json()["exam_id"]

    # Add Question
    resp = requests.post(f"{BASE_URL}/exams/{exam_id}/questions", json={
        "question_type": "mcq",
        "text": "What is 2+2?",
        "options": ["3", "4", "5"],
        "correct_option": "4",
        "marks": 5
    }, headers={"Authorization": f"Bearer {examiner_token}"})
    assert resp.status_code == 201

    # Add Question 2
    resp = requests.post(f"{BASE_URL}/exams/{exam_id}/questions", json={
        "question_type": "essay",
        "text": "Write an essay about PySide6 E2E testing.",
        "marks": 10
    }, headers={"Authorization": f"Bearer {examiner_token}"})
    assert resp.status_code == 201

    # Publish Exam via API
    resp = requests.patch(f"{BASE_URL}/exams/{exam_id}/status", json={"status": "live"}, headers={"Authorization": f"Bearer {examiner_token}"})
    assert resp.status_code == 200

    def wait_until(condition, timeout_ms=5000):
        start = time.time()
        while time.time() - start < timeout_ms / 1000.0:
            if condition():
                return
            QApplication.processEvents()
            time.sleep(0.05)
        pytest.fail("Timeout waiting for condition")

    # =========================================================================
    # 2. Student UI Flow (pytest-qt)
    # =========================================================================
    from client.main_window import MainWindow
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    # Wait for rendering
    wait_until(lambda: window.isVisible(), timeout_ms=2000)

    # UI Login
    # Wait for StartupUI to finish
    wait_until(lambda: window.centralWidget().currentWidget().__class__.__name__ == "StartupUI", timeout_ms=5000)
    startup_ui = window.centralWidget().currentWidget()
    qtbot.mouseClick(startup_ui._login_btn, Qt.LeftButton)

    # Wait for LoginUI
    wait_until(lambda: window.centralWidget().currentWidget().__class__.__name__ == "LoginUI", timeout_ms=5000)
    login_ui = window.centralWidget().currentWidget()
    
    # Fill login form
    login_ui.username.setText(student_email)
    login_ui.pw_field.setText("password")
    login_ui.policy_checkbox.setChecked(True)
    
    start_ux_time = time.time()
    qtbot.mouseClick(login_ui.login_btn, Qt.LeftButton)
    
    # Wait until dashboard is active
    wait_until(lambda: window.centralWidget().currentWidget().__class__.__name__ == "DashboardPage", timeout_ms=10000)
    assert (time.time() - start_ux_time) < 10.0, "UX Latency for Login exceeded SLA"
    
    dashboard = window.centralWidget().currentWidget()

    # Join Class (API simulation for speed)
    resp = requests.post(f"{BASE_URL}/classes/join-by-code/{join_code}", headers={"Authorization": f"Bearer {dashboard._token}"})
    assert resp.status_code == 200
    enrollment_id = resp.json()["enrollment_id"]

    # Examiner Approves
    resp = requests.put(f"{BASE_URL}/classes/{class_id}/enrollments/{enrollment_id}/approve", headers={"Authorization": f"Bearer {examiner_token}"})
    assert resp.status_code == 200

    # Student refreshes exams
    dashboard.refresh_data()
    wait_until(lambda: dashboard._upcoming_list.count() > 0 if hasattr(dashboard, "_upcoming_list") else True, timeout_ms=3000)

    # Start Exam
    from client.student_exam_screen.services.api_client import StudentExamApiClient
    from client.modules.proctoring.camera_monitor import CameraMonitor

    def mock_student_verify_face(self, image_bytes):
        return {"status": "success", "message": "Face verified", "verified": True}

    monkeypatch.setattr(StudentExamApiClient, "verify_face", mock_student_verify_face)

    def mock_start_entry(self):
        if self.on_liveness_pass:
            self.on_liveness_pass(b"dummy_image")
    monkeypatch.setattr(CameraMonitor, "start_entry", mock_start_entry)

    # Trigger internal start exam logic via MainWindow
    window._on_exam_check_in_requested(exam_id)
    
    def check_exam_window():
        for widget in QApplication.topLevelWidgets():
            if widget.__class__.__name__ == "InfoDialog":
                from PySide6.QtWidgets import QLabel
                body_label = widget.findChild(QLabel)
                texts = [child.text() for child in widget.findChildren(QLabel)]
                pytest.fail(f"InfoDialog blocked execution! Texts: {texts}")
        
        current_widget = window.centralWidget().currentWidget()
        if current_widget.__class__.__name__ == "ExamWindow":
            return current_widget
        return None

    wait_until(lambda: check_exam_window() is not None, timeout_ms=5000)
    exam_window = check_exam_window()
    # qtbot.addWidget(exam_window)  # Managed by MainWindow lifecycle

    # Wait for exam to become active
    def wait_exam_active():
        active = getattr(exam_window, "_liveness_passed", False)
        print(f"ExamWindow _liveness_passed={active}")
        return active

    wait_until(wait_exam_active, timeout_ms=10000)

    # =========================================================================
    # 3. Answer Submission & Navigation
    # =========================================================================
    # Select Option B on Question 1
    mcq_widget = exam_window.question_widgets[0]
    option_b_btn = mcq_widget._buttons["B"]
    qtbot.mouseClick(option_b_btn, Qt.LeftButton)
    
    # Verify local cache updated
    exam_window._save_current_answer()
    q1_id = exam_window.questions[0]["id"]
    assert exam_window.cache.get_answer(q1_id)["selected_option"] == "B"

    # Click Next
    next_btn = exam_window.exam_ui.main_screen.nav.next_button
    qtbot.mouseClick(next_btn, Qt.LeftButton)
    
    # Wait for Q2 to become visible
    wait_until(lambda: exam_window.exam_ui.main_screen.question_area.current_index() == 1, timeout_ms=2000)
    
    # Type answer in Q2
    essay_widget = exam_window.question_widgets[1]
    essay_widget.editor.setPlainText("This is an automated E2E test answer.")
    exam_window._save_current_answer()

    # =========================================================================
    # 4. Termination State 2 (Connection Loss / Local Save)
    # =========================================================================
    # Simulate network dropout
    exam_window.heartbeat.connection_lost.emit()
    wait_until(lambda: getattr(exam_window, "_in_lockdown", False) == True, timeout_ms=5000)
    assert exam_window.lockdown_overlay.isVisible()
    
    # Verify answers are preserved in local cache during lockdown
    q2_id = exam_window.questions[1]["id"]
    assert exam_window.cache.get_answer(q2_id)["answer_text"] == "This is an automated E2E test answer."
    
    # Simulate connection restored
    exam_window.heartbeat.connection_restored.emit()
    wait_until(lambda: getattr(exam_window, "_in_lockdown", False) == False, timeout_ms=5000)
    assert not exam_window.lockdown_overlay.isVisible()

    # =========================================================================
    # 5. Termination State 1 (Examiner Terminated) & API Latency
    # =========================================================================
    api_latencies = []
    original_request = exam_window.api._request
    
    def mocked_request(method, path, **kwargs):
        start_req_time = time.time()
        res = original_request(method, path, **kwargs)
        if "finalize" in path:
            api_latencies.append(time.time() - start_req_time)
        return res
        
    monkeypatch.setattr(exam_window.api, "_request", mocked_request)
    
    # Examiner terminates the session via API
    resp = requests.post(
        f"{BASE_URL}/sessions/{exam_window.session_id}/terminate", 
        json={"reason": "Test Termination"}, 
        headers={"Authorization": f"Bearer {examiner_token}"}
    )
    assert resp.status_code == 200

    # Wait for TERMINATE to be handled by UI and session to finalize
    wait_until(lambda: getattr(exam_window, "_terminated", False) == True, timeout_ms=10000)
    
    assert len(api_latencies) > 0, "Finalize API was not called!"
    finalize_latency = api_latencies[0]
    print(f"API Latency for Submission/Finalize: {finalize_latency:.3f}s")
    assert finalize_latency < 5.0, f"Submission API Latency exceeded SLA: {finalize_latency}s"

    # Cleanup the window so pytest-qt can finish cleanly
    exam_window.close()


def test_e2e_liveness_failure(qtbot, setup_test_data, monkeypatch):
    """
    Simulates a failure during the camera liveness verification to ensure the
    application does not crash and handles the failure gracefully.
    """
    from client.main_window import MainWindow
    from client.student_exam_screen.services.api_client import StudentExamApiClient
    from client.modules.proctoring.camera_monitor import CameraMonitor
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton
    import time

    examiner_email, student_email = setup_test_data

    # Login to get student token
    from client.config import BASE_URL
    import requests
    resp = requests.post(f"{BASE_URL}/auth/login", data={"username": student_email, "password": "password"})
    assert resp.status_code == 200
    student_token = resp.json()["access_token"]

    # Mock face verify (just API, we want to fail the local camera check)
    def mock_student_verify_face(self, image_bytes):
        return {"status": "success", "message": "Face verified", "verified": True}
    monkeypatch.setattr(StudentExamApiClient, "verify_face", mock_student_verify_face)

    # Simulating a liveness timeout / failure
    def mock_start_entry_fail(self):
        if self.on_liveness_fail:
            self.on_liveness_fail("Simulated Liveness Timeout: No blink detected.")
    monkeypatch.setattr(CameraMonitor, "start_entry", mock_start_entry_fail)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    def wait_until(condition, timeout_ms=5000):
        start = time.time()
        while time.time() - start < timeout_ms / 1000.0:
            if condition():
                return
            QApplication.processEvents()
            time.sleep(0.05)
        import pytest
        pytest.fail("Timeout waiting for condition")

    wait_until(lambda: window.isVisible(), timeout_ms=2000)

    # Login examiner and create exam via API
    resp = requests.post(f"{BASE_URL}/auth/login", data={"username": examiner_email, "password": "password"})
    assert resp.status_code == 200
    examiner_token = resp.json()["access_token"]
    
    resp = requests.post(f"{BASE_URL}/classes", json={"name": "Liveness Fail Class"}, headers={"Authorization": f"Bearer {examiner_token}"})
    class_id = resp.json()["class_id"]
    join_code = resp.json()["join_code"]
    
    resp = requests.post(f"{BASE_URL}/exams", json={
        "class_id": class_id,
        "title": "Liveness Fail Exam",
        "duration_minutes": 10,
        "require_liveness_check": True,
        "max_window_switches": 3
    }, headers={"Authorization": f"Bearer {examiner_token}"})
    exam_id = resp.json()["exam_id"]
    
    # Add a dummy question so the exam can transition to live status
    resp = requests.post(f"{BASE_URL}/exams/{exam_id}/questions", json={
        "question_type": "mcq",
        "text": "What is 2+2?",
        "options": ["3", "4", "5"],
        "correct_option": "4",
        "marks": 5
    }, headers={"Authorization": f"Bearer {examiner_token}"})
    assert resp.status_code == 201

    resp = requests.patch(f"{BASE_URL}/exams/{exam_id}/status", json={"status": "live"}, headers={"Authorization": f"Bearer {examiner_token}"})
    
    # Student joins class
    resp = requests.post(f"{BASE_URL}/classes/join-by-code/{join_code}", headers={"Authorization": f"Bearer {student_token}"})
    enrollment_id = resp.json()["enrollment_id"]
    
    # Examiner approves
    requests.put(f"{BASE_URL}/classes/{class_id}/enrollments/{enrollment_id}/approve", headers={"Authorization": f"Bearer {examiner_token}"})

    # Wait for StartupUI to finish
    wait_until(lambda: window.centralWidget().currentWidget().__class__.__name__ == "StartupUI", timeout_ms=5000)
    startup_ui = window.centralWidget().currentWidget()
    qtbot.mouseClick(startup_ui._login_btn, Qt.LeftButton)

    # Wait for LoginUI
    wait_until(lambda: window.centralWidget().currentWidget().__class__.__name__ == "LoginUI", timeout_ms=5000)
    login_ui = window.centralWidget().currentWidget()
    
    # Fill login form
    login_ui.username.setText(student_email)
    login_ui.pw_field.setText("password")
    login_ui.policy_checkbox.setChecked(True)
    qtbot.mouseClick(login_ui.login_btn, Qt.LeftButton)
    
    def check_dashboard():
        current = window.centralWidget().currentWidget()
        return current.__class__.__name__ == "DashboardPage"
    wait_until(check_dashboard, timeout_ms=10000)

    # Request exam check-in
    window._on_exam_check_in_requested(exam_id)

    def check_exam_window():
        current_widget = window.centralWidget().currentWidget()
        if current_widget.__class__.__name__ == "ExamWindow":
            return current_widget
        return None

    wait_until(lambda: check_exam_window() is not None, timeout_ms=5000)
    exam_window = check_exam_window()
    # qtbot.addWidget(exam_window)  # Managed by MainWindow lifecycle

    # The mocked start_entry will immediately trigger a failure.
    # The app should show an InfoDialog with the failure reason.
    def check_info_dialog():
        for widget in QApplication.topLevelWidgets():
            if widget.__class__.__name__ == "InfoDialog":
                return widget
        from PySide6.QtWidgets import QWidget
        for child in window.findChildren(QWidget):
            if child.__class__.__name__ == "InfoDialog":
                return child
        return None

    wait_until(lambda: check_info_dialog() is not None, timeout_ms=5000)
    dialog = check_info_dialog()
    
    # Assert dialog contains the failure reason
    texts = [child.text() for child in dialog.findChildren(QLabel)]
    assert any("Simulated Liveness Timeout" in t for t in texts)

    # Click OK to dismiss the dialog
    ok_btn = dialog.findChild(QPushButton)
    qtbot.mouseClick(ok_btn, Qt.LeftButton)

    # After dismissing, it should call _finish_exam and mark session as terminated.
    wait_until(lambda: getattr(exam_window, "_terminated", False) == True, timeout_ms=5000)
    
    # Clean exit without crashes!
    exam_window.close()
