# Product Backlog

Items are ordered by priority within each epic. Security and scalability are explicitly deferred until the system is working well for a single user. Local deployment is a long-term goal; provider independence is the path toward it.

---

## Epic 1 — Evaluation Framework

*How we know the system is working and getting better.*

- [ ] **Design: expert selection evalset** — spec and schema for labeled conversation test cases (in progress)
- [ ] **Build: evalset runner** — pytest-based evaluator that scores orchestrator routing decisions against labeled ground truth
- [ ] **Tooling: human labeling workflow** — lightweight process for reviewing transcripts and adding labeled turns to the evalset
- [ ] **CI: eval regression gate** — add evalset runner to GitHub Actions so routing regressions are caught automatically

---

## Epic 2 — Knowledge Layer

*The core value proposition: the system accumulates what it learns about your work and surfaces it at the right moment.*

- [ ] **Design: session knowledge extraction** — how transcripts are processed into durable knowledge after a session ends
- [ ] **Design: knowledge retrieval strategy** — how stored knowledge is selected and injected into a new session at the right moment
- [ ] **Build: knowledge store** — persistent store for extracted session knowledge, keyed by project
- [ ] **Build: knowledge injection into session context** — surface relevant knowledge at session start and on turn events
- [ ] **Eval: extend evalset for knowledge retrieval quality** — did the right knowledge surface? precision/recall for retrieval

---

## Epic 3 — Provider Independence

*Protect the ability to run fully locally and avoid deepening platform lock-in.*

- [ ] **SPIKE: evaluate local voice alternatives** — time-boxed research into replacing Gemini Live API with a local model. Primary candidate: [Moshi](https://github.com/kyutai-labs/moshi) (Kyutai real-time speech-to-speech). Also evaluate modular approach (Whisper ASR + local LLM + local TTS). Deliverable: a short written assessment covering capability gap, hardware requirements, integration cost, and recommended abstraction boundary.
- [ ] **Design: LLM/voice provider abstraction** — informed by the spike; define the interface boundary that lets the voice model be swapped without touching Router or Orchestrator logic. Note: expert agent wiki design currently names Gemini directly in whisper/ingest prompts — this abstraction should cover the expert agent LLM as well as the realtime voice conversation agent, so neither is hardcoded.
- [ ] **Build: provider abstraction layer** — implement the boundary so Gemini Live and a local alternative can coexist behind the same interface

---

## Epic 4 — Expert Ecosystem

*More agents means more value. Each agent should be independently deployable and testable.*

- [ ] **Design: second expert agent** — define domain, whisper contract, and evaluation criteria (candidate: architecture / decision-log awareness)
- [ ] **Build: second expert agent**
- [ ] **Design: agent routing improvements** — smarter orchestrator routing beyond broadcast-all; LLM-assisted relevance scoring
- [ ] **Build: improved routing**

---

## Epic 5 — Telephony

*The primary client per the system spec. Deferred until the knowledge layer is useful enough to justify a phone interface.*

- [ ] **Design: telephony adapter** — provider-agnostic inbound audio WebSocket; first implementation candidate: Twilio
- [ ] **Build: telephony adapter**
- [ ] **Test: end-to-end voice call session**

---

## Epic 6 — Security & Scalability

*Explicitly deferred. Revisit when the system is working well for a single user and sharing it with others becomes relevant.*

- [ ] Authentication and session authorization
- [ ] Rate limiting and abuse protection
- [ ] Multi-user session isolation
- [ ] Horizontal scaling of Router and Orchestrator services
