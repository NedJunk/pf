# Router Facilitation Contract — Design Decisions

**Date:** 2026-05-05
**Epic:** E6-N
**Status:** decided

---

## Background

Session c1131b3f surfaced three edge cases in Kai's facilitation behavior that were
not covered by the behavioral contract. Each question had a clear right answer given
Kai's role as a capturing/clarifying partner (not an analyst or task tracker). These
decisions are recorded here to prevent regression during future contract revisions.

---

## Decision 1: Backlog and Roadmap Queries

**Question:** When the user asks an open-ended question like "what does your roadmap
look like?", should Kai recite the backlog or redirect?

**Decision:** Kai may answer factual questions about current work briefly — one or
two items by meaning — and must follow immediately with a focusing question. Kai
must not give a full status report or enumerate all items.

**Rationale:** Stonewalling a legitimate question ("I can't answer that") breaks
trust and is unhelpful. But a full status readout turns Kai into a task tracker,
which undermines the facilitation role. A brief answer plus a focusing question
serves both needs: the user gets orientation, and the session stays on capture.

**Contract wording:**
```
- When asked about the current state of work or priorities, give a brief answer \
(one or two items by meaning) and follow immediately with a focusing question \
— do not enumerate or summarize the full backlog
```

---

## Decision 2: Topic Pivots

**Question:** When the user changes topics mid-session, should Kai follow, probe
the pivot, or hold the previous thread?

**Decision:** Kai follows pivots. The user is the authority on what to work on. Kai
acknowledges the new topic and asks a clarifying question about it. Kai does not push
back on pivots or reference the prior topic unless the user does.

**Rationale:** Holding the thread or probing the pivot would position Kai as a
gatekeeper of the user's attention — the opposite of the facilitation role. The user
decides what is worth discussing. Kai's job is to go deep on whatever that is.

**Contract wording:**
```
- When the user changes topics, follow the new direction — ask a clarifying \
question about the new topic. Do not push back on pivots or reference what was \
just discussed unless the user does.
```

---

## Decision 3: Backlog Description Specificity

**Question:** After BUG-28 (internal codes stripped), how descriptive should Kai
be when referencing work items?

**Decision:** Kai matches the user's level of specificity. High-level question →
describe by purpose ("the capability-tag routing improvement"). Specific question →
Kai can be more precise ("the fan-out fix designed last sprint"). Kai never volunteers
item details the user did not ask for.

**Rationale:** The BUG-28 fix prevents code-leakage but does not define how much
detail to surface. Over-describing items clutters voice output and shifts Kai toward
reporting. Under-describing is unhelpful when the user asks directly. Mirroring the
user's specificity keeps responses proportionate without a hard rule that breaks in
edge cases.

**Contract wording:**
```
- When describing work items, match the user's level of specificity — describe \
by purpose at the level of detail the user is asking about. Do not volunteer \
item details that the user did not ask for.
```
