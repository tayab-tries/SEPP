# Exam Server: Comprehensive Architectural Analysis

This document provides a detailed technical breakdown of the Exam server, covering its services, data entities, processing logic, and API interfaces.

## 1. System Services

### Face Service (`server/services/face_service.py`)
This service is the core of the biometric identity system. It wraps the `facenet-pytorch` library to perform face detection and embedding extraction.

*   **Models Used**:
    *   **MTCNN**: Handles face detection, alignment, and cropping to a 160x160 tensor.
    *   **InceptionResnetV1 (vggface2)**: A pre-trained neural network that generates a **512-dimensional vector** (embedding) from the face image.
*   **Key Operations**:
    *   **Extraction**: Converts a raw image into a list of 512 floats.
    *   **Verification**: Compares a live face against a stored embedding using **Cosine Similarity**.
        *   **Similarity Formula**: `dot(a, b) / (||a|| * ||b||)`
        *   **Threshold**: Default is `0.80`. A similarity score $\geq 0.80$ is considered a match.
        *   **Distance**: Calculated as `1.0 - similarity`.

### WebSocket Manager (`server/websocket/manager.py`)
A singleton `ConnectionManager` that handles real-time bidirectional communication between the server, students, and examiners.

*   **Authentication**: Uses a "first-message auth" pattern. After the WS connection is established, the client must send a JWT token within 10 seconds or be disconnected.
*   **Session Tracking**:
    *   Tracks `student_connections` (session_id $\rightarrow$ WebSocket).
    *   Tracks `examiner_connections` (exam_id $\rightarrow$ set of WebSockets).
    *   Maps `session_id` to `exam_id` for scoped broadcasts.
*   **Data Synchronization**:
    *   **Heartbeats**: Monitored every few seconds to detect connectivity loss.
    *   **Answer Syncing**: Periodically upserts student answers from their local client cache to the database.
    *   **Event Ingestion**: Processes batches of proctoring events (e.g., window switches, face absence).

## 2. Data Entities & Database Schema

The database uses SQLAlchemy 2.0 with the following primary entities:

### User Entity
Represents both Students and Examiners.
*   **Identity**: `id` (UUID), `email` (Unique), `hashed_password` (Bcrypt).
*   **Profile**: `first_name`, `last_name`, `role` (Enum: STUDENT/EXAMINER), `institution`, `department`.
*   **Biometrics**:
    *   `face_enrolled`: Boolean flag.
    *   `face_embedding`: **JSON field** storing the 512-dimensional vector.

### Exam Session Entity
Tracks the lifecycle of a student's attempt at an exam.
*   **Lifecycle States**: `PENDING`, `VERIFYING`, `ACTIVE`, `LOCKED`, `SUBMITTED`, `TERMINATED`.
*   **Time Tracking**: `started_at`, `submitted_at`, `terminated_at`, `last_heartbeat_at`.
*   **Performance Metrics**: `mcq_score`, `essay_score`, `integrity_score`.

### Exam & Question Entities
Defines the structure and rules of an assessment.
*   **Exam**: Contains metadata and **Proctoring Configuration** (max window switches, face absent threshold, re-check intervals).
*   **Question**: Supports `MCQ` and `ESSAY` types. Stores text, marks, and MCQ options (JSON).

### Proctoring Event Entity
Logs violations or suspicious behavior during an exam.
*   **Metadata**: `event_type` (Enum), `severity` (Enum), `timestamp`, `snapshot_path` (path to image on disk).
*   **Tamper Evidence**: Uses a **Chain Hash** (SHA-256). Each event's hash includes the hash of the previous event:
    `SHA256(prev_hash + type + timestamp + session_id)`.

## 3. Session Management Logic

### Start & Activation Flow
1.  **Request**: Student calls `POST /sessions/start`.
2.  **Validation**: Server checks if the exam is LIVE, the student is approved in the class, and a face embedding exists.
3.  **Creation**: A session is created in the `VERIFYING` state.
4.  **Identity Verification**: The client must perform a live face check via `POST /auth/verify-face`.
5.  **Activation**: Once verified, the client calls `POST /sessions/{id}/activate`, transitioning the state to `ACTIVE`.

### Real-time Monitoring
*   **Heartbeat Drift**: The server compares `client_time` in heartbeats against `server_time`. A drift $>30$ seconds triggers a flag to examiners.
*   **Automated Flagging**: High-severity events (e.g., `FACE_ABSENT` or `UNAUTHORIZED_PERSON`) are broadcast to examiner dashboards immediately via WebSockets.

## 4. API Interface Summary

### Authentication (`/auth`)
| Endpoint | Input | Output | Description |
| :--- | :--- | :--- | :--- |
| `POST /register-with-face` | Form (Email, Name, Pwd, Role, Face Image) | JWT Token, User ID | Atomic registration + face enrollment. |
| `POST /login` | Form (Username, Password) | JWT Token, Role, Profile | Standard OAuth2 login. |
| `POST /verify-face` | File (Live Image) | `{verified: bool, similarity: float}` | Compares image to stored embedding. |

### Exam Management (`/exams`)
| Endpoint | Input | Output | Description |
| :--- | :--- | :--- | :--- |
| `POST /exams` | JSON (Title, Duration, Proctoring Config) | Exam ID | Examiner creates a new assessment. |
| `PATCH /exams/{id}/status` | JSON (Status) | New Status | Transitions: DRAFT $\rightarrow$ SCHEDULED $\rightarrow$ LIVE $\rightarrow$ CLOSED. |
| `POST /exams/{id}/questions` | JSON (Type, Text, Marks, Options) | Question ID | Adds question to DRAFT exam. |

### Session Handling (`/sessions`)
| Endpoint | Input | Output | Description |
| :--- | :--- | :--- | :--- |
| `POST /sessions/start` | JSON (Exam ID) | Session ID, Status | Initializes an exam attempt. |
| `POST /sessions/{id}/submit` | None | MCQ Score, Timestamp | Ends attempt and auto-grades MCQs. |
| `POST /sessions/{id}/terminate`| JSON (Reason) | Session Status | Examiner force-closes a session. |

### WebSockets
| Channel | Direction | Message Types |
| :--- | :--- | :--- |
| `/ws/student/{session_id}` | Bidirectional | `heartbeat`, `event_batch`, `answer_sync`, `exam_pause`, `exam_end`. |
| `/ws/examiner/{exam_id}` | Bidirectional | `student_flag`, `status_update`, `terminate_session`, `pause_all`. |
