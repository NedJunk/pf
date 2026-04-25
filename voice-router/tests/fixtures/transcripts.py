"""
Example transcripts are the ground truth for this project's TDD.
Each turn with a `validates` list asserts a required Router behavior.
Add transcripts here as new behaviors are discovered in real sessions.
"""

EXAMPLE_TRANSCRIPTS = [
    {
        "session_id": "capture-habit-tracker",
        "turns": [
            {
                "actor": "User",
                "message": "I need to, um, I have this idea about building a habit tracker but I don't know where to start.",
            },
            {
                "actor": "Router",
                "message": "It sounds like you're at the very beginning of this. Let me ask — when you say habit tracker, is this for yourself, or are you thinking about something others would use?",
                "validates": ["asks_clarifying_question"],
            },
            {
                "actor": "User",
                "message": "For myself, definitely.",
            },
            {
                "actor": "Router",
                "message": "Got it. What's the one habit you most want to track? Don't overthink it.",
                "validates": ["prompts_for_specifics"],
            },
            {
                "actor": "User",
                "message": "Probably daily exercise.",
            },
            {
                "actor": "Whisper",
                "source": "ProjectManager",
                "message": "We have an existing 'wellness' project in the map.",
            },
            {
                "actor": "Router",
                "message": "The Project Manager is flagging that we have an existing 'wellness' project. Does this habit tracker belong there, or is this its own thing?",
                "validates": ["voices_whisper", "suggests_category"],
            },
            {
                "actor": "User",
                "message": "It should go under wellness.",
            },
            {
                "actor": "Router",
                "message": "Perfect. So we're capturing: a personal exercise habit tracker, under the wellness project. Anything else, or shall we wrap up?",
                "validates": ["summarizes_capture", "offers_closure"],
            },
        ],
    }
]

# Every behavior tag in `validates` above must appear here.
# The test verifies coverage: every REQUIRED_BEHAVIORS entry is claimed by at least one turn.
# Note: `validates` tags document *intended* behavior — they are not asserted by driving the Router
# with live speech. Integration tests against the real Gemini API are needed to verify the LLM
# actually exhibits these behaviors at runtime.
REQUIRED_BEHAVIORS = [
    "asks_clarifying_question",  # Router probes ambiguous input rather than accepting it passively
    "prompts_for_specifics",     # Router pushes the user to be concrete
    "voices_whisper",            # Router relays an expert injection naturally in conversation
    "suggests_category",         # Router helps connect input to known project structure
    "summarizes_capture",        # Router reflects back what was captured before closing
    "offers_closure",            # Router signals the session can end rather than running indefinitely
]
