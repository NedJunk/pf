# Voice-First Development Partner Design Spec

## 1. Overview
The Voice-First Development Partner is an interactive, speech-driven system designed to handle the high-friction "capture and refinement" phase of personal development and project management. It acts as a "Smart Entry Point," allowing the user to brain-dump, untangle tasks, and refine requirements through natural conversation, without the need to be at a keyboard.

## 2. Core Architecture

The system is built around three distinct phases: Capture, Context, and Artifacts.

### 2.1 Capture (The Router Layer)
- **Voice Interface:** The primary interaction model is speech. It must support mobile/on-the-go usage to capture thoughts when overwhelm hits or ideas arise away from the desk.
- **The "Thin" Router:** The user interacts with a single conversational facilitator. This Router is "thin"—it does not perform deep reasoning itself but is highly context-aware.
- **Interaction Style:** The Router is an *Active Facilitator*. It asks clarifying questions, suggests categories, and prompts the user to dig deeper, rather than acting as a passive dictation tool.

### 2.2 Context & Dynamic Injection
- **State Management:** The Router maintains a live awareness of three critical context areas:
  1. *Project Map / Knowledge Graph:* How current and past projects relate.
  2. *Active High-Level Goals:* The overarching *why* driving the work.
  3. *Recent Conversation State:* The immediate history of the interaction.
- **The "Whisperer" Model:** During a live voice session, more powerful, asynchronous models acting as specialized "Experts" (e.g., Project Manager, System Architect) analyze the conversation in the background. They inject insights back into the Router via a back-channel. The Router then voices these insights to the user (e.g., "The PM is reminding me that we already have a task for this...").

### 2.3 Artifacts & Async Reasoning
- **Deep Thinking Offload:** Once a session concludes, the heavy-duty reasoning is handed off entirely to powerful LLMs (e.g., Claude, GPT-4).
- **Document Generation:** These async models process the full session and update or generate artifacts (e.g., Markdown specs, prioritized task lists, or structured logs) directly into the user's workspace/file system.

## 3. Observability & Refinement

To ensure continuous improvement and alignment with the user's expectations, the system must support rigorous observability.

- **Verbatim Transcripts:** Every conversation must be captured as a raw, verbatim transcript.
- **Traceability:** These transcripts serve as the foundation for Test-Driven Development (TDD). They provide the necessary data to analyze interaction patterns, identify where the Router missed a cue, or where an injected Expert provided poor context.

## 4. Key Constraints & Non-Goals
- **No Early Tech Commitments:** Specific frameworks (e.g., React, Next.js, specific audio APIs) are intentionally deferred until the interaction model is fully validated. The focus is strictly on architectural flow and user experience.
- **Router Boundaries:** The Router must *not* attempt deep project analysis or code generation; it must stick to facilitating capture and communicating injected context.