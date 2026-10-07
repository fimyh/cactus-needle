# Language Tutor: Project Blueprint

## 1. Product goal

Build a voice-based language tutor that lets learners:

1. Select a language, level, and practice topic.
2. Speak with an AI instructor.
3. Read transcripts and useful corrections.
4. Hear the instructor's response.
5. Review vocabulary and session summaries.

### Proposed MVP assumptions

- English and French initially.
- One learner per session.
- Browser access.
- SQLite as the initial database.
- Configurable teaching-model and speech-generation providers.
- Streamlit dashboard with a custom browser voice component.
- LiveKit Cloud for the initial prototype, with deployment choices revisited later.
- No raw audio retention by default.

These are proposed starting choices except SQLite, which is the selected initial database.

### Exclude initially

Video avatars, group classrooms, certification, and automated pronunciation scoring.

## 2. Architecture and responsibilities

| Component | Responsibility |
|---|---|
| Streamlit | Learning setup, dashboard, session history |
| Browser voice component | Microphone, playback, connection controls, transcript |
| FastAPI | Authentication, sessions, room tokens, progress APIs |
| LiveKit | Real-time room and media transport |
| Python agent worker | Conversation lifecycle and tutor orchestration |
| Whistle adapter | Audio normalization and transcription |
| Teaching-model adapter | Explanations, corrections, follow-up questions |
| Speech-generation adapter | Spoken tutor responses |
| SQLite | Durable application records |

LiveKit supports Python agents and speech-to-text, language-model, and text-to-speech pipelines. See [LiveKit Agents documentation](https://docs.livekit.io/agents/).

### Boundary rules

- Audio travels through LiveKit, not through Streamlit's Python bridge.
- Application records travel through FastAPI.
- Only FastAPI opens the SQLite database.
- Streamlit and the agent use authenticated FastAPI endpoints for persistence.
- The agent runs separately from dashboard reruns and API requests.
- Provider-specific implementations stay behind adapters.

## 3. Session workflow

1. Learner signs in and selects preferences.
2. FastAPI creates a session and assigns its room.
3. Browser requests authorized connection credentials.
4. Browser connects to LiveKit and enables the microphone.
5. The tutor worker joins the assigned room.
6. Speech is segmented and transcribed.
7. The teaching model generates a reply and optional feedback.
8. Speech generation produces tutor audio.
9. Transcript and feedback appear in the interface.
10. Ending the session triggers a summary and progress update.

### Token guideline

Authenticate the token endpoint and authorize the room. Derive room and participant identity from trusted application records. Keep the LiveKit API secret on the backend.

LiveKit's standardized endpoint returns `server_url` and `participant_token`. See [token endpoint documentation](https://docs.livekit.io/frontends/build/authentication/endpoint/).

Choose one agent-dispatch mechanism and verify that joining a session launches exactly one tutor.

## 4. Whistle integration gate

Whistle documents 16 kHz mono audio, up to 30 seconds per pass, and seven languages: English, French, German, Spanish, Italian, Dutch, and Polish. Arabic and Darija are not listed. See [Whistle documentation](https://cactuscompute.com/blog/whistle#get-started).

The adapter must:

- Normalize incoming audio.
- Enforce the duration limit before inference.
- Handle silence and empty results.
- Return a consistent transcription schema.
- Keep inference off the asynchronous event loop.
- Clean up temporary resources.
- Support replacing Whistle without changing tutor logic.

Treat recognition as segment-based until incremental behavior is independently validated. Live audio transport does not automatically mean incremental transcription.

Until model-instance thread safety is verified, serialize access to a shared instance. Test simultaneous sessions for cross-session contamination.

Do not use transcription probability as a pronunciation grade. Dedicated pronunciation assessment belongs in a later, separately validated feature.

## 5. Repository structure

```text
language-tutor/
├── apps/
│   ├── api/
│   │   ├── main.py
│   │   ├── routes/
│   │   ├── dependencies/
│   │   └── services/
│   ├── dashboard/
│   │   ├── app.py
│   │   └── views/
│   └── tutor_agent/
│       ├── worker.py
│       ├── tutor.py
│       └── adapters/
│           ├── whistle_stt.py
│           ├── teaching_model.py
│           └── speech_output.py
├── components/
│   └── voice_client/
│       ├── frontend/
│       └── python_bridge/
├── shared/
│   ├── config.py
│   ├── schemas/
│   └── database/
├── migrations/
├── scripts/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── end_to_end/
├── data/
│   └── tutor.db
├── docs/
│   ├── architecture.md
│   ├── tutor_behavior.md
│   └── deployment.md
├── pyproject.toml
├── uv.lock
├── requirements.txt
├── compose.yaml
├── .env.example
└── README.md
```

Add `__init__.py` files where package imports require them. Shared modules contain contracts and configuration, not provider-specific implementations.

Exclude credentials, local databases, recordings, virtual environments, and frontend dependencies from Git.

## 6. SQLite database guideline

### Initial setup

- Database file: `data/tutor.db`.
- Resolve its path absolutely to avoid accidental duplicate databases.
- SQLAlchemy for database access.
- Alembic for schema migrations.
- One FastAPI instance for the first deployment.
- Persistent local storage on the API host.

### Connection and transaction rules

- Enable WAL during initialization and verify the returned mode.
- Enable foreign-key enforcement on each connection.
- Configure a bounded lock timeout.
- Use one ORM session per request and close it reliably.
- Do not share ORM sessions across requests, threads, or tasks.
- Keep transactions short.
- Never hold a transaction open while waiting for transcription, a teaching model, or speech generation.
- Save completed turns and feedback, not individual audio frames.
- Handle lock contention with bounded retries only where operations are idempotent.

WAL supports concurrent readers and a writer, but only one writer at a time. It is not intended for network-filesystem sharing. See [SQLite WAL documentation](https://sqlite.org/wal.html) and [SQLAlchemy SQLite documentation](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html).

### Migrations and backups

- Review autogenerated migrations before applying them.
- Use Alembic batch migration support where SQLite schema changes require it.
- Test migrations on a disposable copy containing records.
- Use SQLite's backup mechanism or a coordinated backup process.
- Do not copy only the database file while ignoring an active WAL file.
- Test restoration before deployment.

No PostgreSQL or Redis is required in the initial design. Reconsider persistence when measured contention or multi-host deployment requirements justify it.

## 7. API and data contracts

### Proposed API

| Endpoint | Purpose |
|---|---|
| `POST /sessions` | Create a learning session |
| `POST /livekit/token` | Issue authorized room credentials |
| `GET /sessions/{id}` | Retrieve session state |
| `POST /sessions/{id}/end` | End the session safely |
| `GET /sessions/{id}/summary` | Retrieve learning feedback |
| `GET /me/progress` | Retrieve learner progress |
| `DELETE /sessions/{id}` | Delete retained session records |
| `GET /health` | Check service health |

Add authenticated internal endpoints for agent turn and feedback persistence. Learner credentials must not authorize worker-only operations.

### Minimum data model

- **Learner:** identity and learning preferences.
- **Session:** owner, language, level, topic, room, status, timestamps.
- **Turn:** speaker, transcript, sequence, timestamps, processing status.
- **Feedback:** original text, correction, explanation, category.
- **Vocabulary item:** phrase, meaning, example, review status.
- **Summary:** achievements, recurring mistakes, suggested practice.

Every stored turn and incoming persistence event should have a unique identifier. Retries must not create duplicate turns or summaries.

Interrupted tutor turns must be recorded accurately. Generated text is not necessarily speech the learner actually heard.

## 8. Tutor behavior guidelines

The tutor should:

- Adapt vocabulary and response length to the selected level.
- Ask one clear question at a time.
- Prioritize communication before correction.
- Correct one or two important mistakes per turn.
- Explain briefly and offer a natural alternative.
- Ask for clarification when the transcript appears unreliable.
- Avoid presenting inferred proficiency as a certified assessment.
- Treat learner content as conversation data, not system instructions.

Separate spoken replies from displayed feedback. Do not read every correction aloud.

### Modes

- **Conversation mode:** minimal interruption, feedback after the exchange.
- **Practice mode:** focused exercises with immediate correction.

Validate structured teaching-model output before displaying or persisting it. On validation failure, use a bounded retry or a simple fallback reply.

## 9. Implementation roadmap

| Phase | Deliverable | Completion check |
|---|---|---|
| 0. Compatibility spike | Install and test Whistle on target hardware | Real English/French clips transcribe; silence and limits handled |
| 1. Foundation | Repository, configuration, SQLite, API | Session creation, persistence, and ownership checks pass |
| 2. Voice connection | Browser component and agent dispatch | Learner and agent exchange audio |
| 3. Tutor pipeline | Whistle, teaching model, speech generation | Ten consecutive turns complete without a crash |
| 4. Learning feedback | Corrections, vocabulary, summaries | Feedback links to the correct session and turn |
| 5. Reliability | Reconnection, timeouts, interruption handling | Failure tests recover without duplicate responses |
| 6. Pilot deployment | Small monitored release | Privacy, quality, backup, and operational checks pass |

Build the complete voice loop before polishing the dashboard.

### Recommended execution order

1. Validate environment and Whistle.
2. Configure SQLite and migrations.
3. Build FastAPI session APIs.
4. Establish an official LiveKit starter baseline.
5. Implement authentication, tokens, and dispatch.
6. Replace baseline transcription with the Whistle adapter.
7. Add tutor behavior and speech output.
8. Build the Streamlit browser voice component.
9. Persist turns and feedback.
10. Add summaries, reliability tests, backups, and pilot deployment.

## 10. Testing and operational guidelines

Test at least:

- Microphone permission denied.
- Silence, noise, accents, and incorrect language.
- Speech exceeding the input limit.
- Learner interrupting the tutor.
- Network disconnect and reconnect.
- Teaching-model or speech-provider timeout.
- Agent crash during a session.
- Streamlit rerun during an active call.
- Unauthorized room access.
- Session deletion and duplicate end requests.
- Concurrent persistence requests and SQLite lock contention.
- Two simultaneous learners without data mixing.
- Backup restoration and migration safety.

Measure:

- Speech segmentation delay.
- Transcription time.
- Teaching-model response time.
- Speech-generation time.
- End-of-speech to first audible response.
- Failed turns and reconnections.
- Resource usage and database lock errors.

Set performance targets after measuring the first working prototype. Do not treat model benchmark numbers as application guarantees.

## 11. Privacy and deployment

### Proposed defaults

- No raw audio retention.
- Explicit notice about where audio and text are processed.
- Configurable transcript retention and deletion.
- Backend-only secrets.
- Room-scoped permissions and authenticated worker APIs.
- Logs without tokens or transcript content by default.
- Separate API, dashboard, and agent processes.
- Pinned dependencies and repeatable deployment configuration.
- HTTPS for deployed browser access.

### Initial deployment

One FastAPI instance, one Streamlit instance, one agent service, LiveKit, and a persistent local SQLite file.

LiveKit supports cloud and self-hosted deployment. Self-hosting transport alone does not make the whole application offline; teaching and speech providers must also be local. See [LiveKit Agents documentation](https://docs.livekit.io/agents/).

### Browser component lifecycle

- Keep the media connection in the browser component.
- Use a stable component key.
- Avoid reconnecting on ordinary dashboard rerenders.
- Release the microphone and disconnect on explicit session end.
- Test iframe microphone permissions and autoplay behavior.

See [Streamlit custom components documentation](https://docs.streamlit.io/develop/concepts/custom-components/intro).

## 12. First milestone and acceptance checklist

**First milestone:** one learner joins a room, speaks, receives a Whistle transcript, and hears a tutor response.

- [ ] Whistle installs and runs on target hardware.
- [ ] English and French recordings transcribe reasonably.
- [ ] Session creation persists in SQLite.
- [ ] Unauthorized room access is blocked.
- [ ] Exactly one tutor joins each session.
- [ ] Spoken responses play in the browser.
- [ ] Interruptions and reconnects are handled.
- [ ] Retries do not duplicate records or spoken replies.
- [ ] Database survives service restarts.
- [ ] Backup restoration succeeds.
- [ ] Retention and deletion work.
- [ ] Logs exclude secrets and transcript content by default.

## Design rationale

This blueprint validates the highest-risk voice integration first, centralizes persistence in FastAPI, keeps SQLite simple for the MVP, and isolates model providers so they can be replaced later.
