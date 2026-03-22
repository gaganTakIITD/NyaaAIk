# Nyaya Dhwani — App Design Specification
**न्याय ध्वनि · Voice of Justice**  
*Legal AI Assistant for India · Powered by Sarvam AI*

---

## Overview

Nyaya Dhwani is a multilingual legal assistance app built on Gradio, using Sarvam AI's language models for speech-to-text, translation, and text-to-speech across 22 Indian languages. Users can ask legal questions by text or voice and receive answers in the same language they used — spoken back to them if they prefer.

The app is structured around six screens, a clean input → processing → output pipeline, and a Gradio component layer that maps directly to each UI element.

---

## Design Language

| Attribute | Value |
|---|---|
| Primary palette | Deep navy (`#0D1B3E`) + saffron gold (`#C87B2A`) |
| Background (light) | Warm parchment (`#F7F3ED`) |
| Accent | Amber (`#E8A135`), muted blue (`#2A5297`) |
| Typography | Serif for brand name, sans-serif for UI |
| Tone | Trustworthy, accessible, calm — not corporate |

---

## Screen 01 — Welcome & Language Selection

### Purpose
First contact. The user picks their language before anything else. This sets the session language for all STT, LLM responses, and TTS output.

### Layout & UI Components

| Component | Role |
|---|---|
| Balance scale icon + Devanagari subtitle | Brand identity — न्याय ध्वनि |
| Language pill grid | 22 Sarvam-supported languages displayed as selectable chips (Hindi, Tamil, Bengali, Telugu, Marathi, Kannada, Malayalam, English, etc.) |
| Primary CTA button | "Begin / शुरू करें" — bilingual label, always |
| Disclaimer footer | "Not a substitute for legal counsel · Powered by Sarvam AI" |

### Gradio Mapping

```python
with gr.Blocks(theme=custom_theme) as app:
    language = gr.State("hi")  # default Hindi

    with gr.Column():
        gr.HTML("<h1>Nyaya Dhwani · न्याय ध्वनि</h1>")
        selected_lang = gr.Radio(
            choices=SARVAM_LANGUAGES,   # list of 22 language codes + display names
            label="Select your language / अपनी भाषा चुनें",
            value="hi"
        )
        begin_btn = gr.Button("Begin / शुरू करें", variant="primary")
        gr.HTML("<small>Not a substitute for legal counsel</small>")
```

### Key Behaviour
- Selecting a language sets `gr.State` for the session.
- All subsequent API calls (STT, LLM system prompt locale, TTS voice) inherit this value.
- Language can be changed from Settings at any time; the chat history is preserved.

---

## Screen 02 — Chat Query Screen

### Purpose
The primary interface. The user types or speaks a legal question. Topic chips help first-time users who don't know where to start.

### Layout & UI Components

| Component | Role |
|---|---|
| App header bar | Logo + current language indicator (changeable) |
| Topic chips (horizontal scroll) | Quick-start shortcuts: Tenant rights, Divorce law, Consumer cases, Property law, Labour rights, FIR / Police, Domestic violence, RTI |
| Chat thread | Conversation history, alternating user and assistant bubbles |
| Text input field | Freeform typing in any script |
| Mic button (prominent, circular) | Tap to start voice recording |

### Gradio Mapping

```python
with gr.Tab("Chat"):
    topic_chips = gr.Radio(
        choices=["Tenant rights", "Divorce law", "Consumer cases",
                 "Property law", "Labour rights", "FIR / Police"],
        label="Common topics",
        interactive=True
    )

    chatbot = gr.Chatbot(
        label="Nyaya Dhwani",
        bubble_full_width=False,
        avatar_images=("user_avatar.png", "scale_avatar.png")
    )

    with gr.Row():
        text_input = gr.Textbox(
            placeholder="Type your question / अपना सवाल लिखें...",
            show_label=False,
            scale=8
        )
        mic_btn = gr.Audio(
            sources=["microphone"],
            type="numpy",
            show_label=False,
            scale=1
        )
```

### Key Behaviour
- Clicking a topic chip pre-fills the text input with a seed question in the selected language.
- The mic button is always visible and one tap away — no buried menus.
- The chatbot maintains full conversation history in `gr.State` for multi-turn context.

---

## Screen 03 — Voice Input Active

### Purpose
Active recording state. The user sees a live waveform and a rolling transcript so they know the app is listening and understanding them.

### Layout & UI Components

| Component | Role |
|---|---|
| Status label | "Listening… · हिंदी" — shows detected language |
| Waveform visualisation | Animated bars responding to microphone amplitude |
| Live transcript card | Real-time Devanagari (or relevant script) text as Sarvam STT processes audio |
| Language detection label | "Detected language: Hindi" — auto-detected from speech, can be overridden |
| Cancel button | Discards recording |
| Send button | Submits transcript to the LLM pipeline |

### Gradio Mapping

```python
audio_input = gr.Audio(
    sources=["microphone"],
    type="numpy",
    streaming=True,               # enables live waveform feedback
    label="Speak your question"
)

live_transcript = gr.Textbox(
    label="Live transcript",
    interactive=False,
    placeholder="Transcription will appear here..."
)

detected_lang_label = gr.Markdown("Detected language: —")

with gr.Row():
    cancel_btn = gr.Button("Cancel")
    send_voice_btn = gr.Button("Send ↗", variant="primary")

# STT call via Sarvam API
def transcribe_audio(audio_data, language_code):
    response = sarvam_client.speech_to_text(
        audio=audio_data,
        language_code=language_code,   # or "auto" for detection
        model="saaras-v2"
    )
    return response.transcript, response.detected_language
```

### Key Behaviour
- Sarvam's `saaras-v2` model handles STT. If language is set to "auto", the detected language updates the session `gr.State`.
- The transcript card updates in near-real-time using Gradio's streaming audio support.
- On "Send", the transcript string is passed directly into the chat pipeline exactly as typed text would be.

---

## Screen 04 — AI Response + Audio Playback

### Purpose
Delivers the legal answer in text and optionally as spoken audio in the user's language. Includes citations, a mandatory disclaimer, and follow-up prompt chips.

### Layout & UI Components

| Component | Role |
|---|---|
| Assistant bubble | Full Markdown-rendered response in user's language |
| Legal citation tag | Highlighted pill showing referenced Act + section (e.g., "Rent Control Act, 1948 · Sec 14") |
| Disclaimer banner | "This is general legal information, not legal advice. Consult a qualified lawyer for your specific case." — auto-appended to every response |
| Audio player | Playback of the TTS-generated response with progress bar and duration |
| "Listen in [language]" label | Confirms which language the audio is in |
| Follow-up chips | Contextually generated quick replies, e.g., "कहाँ शिकायत करें?", "Lawyer find करें", "नमूना नोटिस बनाएं" |
| Text input + mic | Always available for the next question |

### Gradio Mapping

```python
response_text = gr.Markdown(label="Legal Assistant")

audio_response = gr.Audio(
    label="Listen to response",
    autoplay=False,              # respect user preference from Settings
    interactive=False
)

followup_chips = gr.Radio(
    choices=[],                  # populated dynamically after each response
    label="Follow up",
    interactive=True
)

# LLM call (with RAG context)
def get_legal_response(user_query, chat_history, language_code):
    context = rag_retriever.query(user_query)    # fetch relevant Acts, sections
    system_prompt = build_system_prompt(language_code, context)
    llm_response = llm_client.chat(
        messages=chat_history + [{"role": "user", "content": user_query}],
        system=system_prompt
    )
    answer = llm_response.text + "\n\n---\n*" + DISCLAIMER[language_code] + "*"
    return answer

# TTS call via Sarvam
def text_to_speech(text, language_code):
    audio = sarvam_client.text_to_speech(
        text=text,
        language_code=language_code,
        model="bulbul-v1",
        speaker="auto"
    )
    return audio.audio_bytes
```

### Key Behaviour
- The disclaimer is appended programmatically — it cannot be omitted.
- Legal citations are extracted from RAG context and formatted as highlighted inline tags.
- TTS is triggered automatically or on demand (configurable in Settings).
- Follow-up chips are generated by a secondary LLM call asking for 3 contextual next questions in the user's language.

---

## Screen 05 — Lawyer Connect

### Purpose
Escalation path. When the AI answer is insufficient or the user wants professional help, this screen surfaces nearby advocates filtered by specialty and language. It also checks NALSA free legal aid eligibility.

### Layout & UI Components

| Component | Role |
|---|---|
| Filter bar | "Nearest", "Speciality", "Language: हिं" — three quick filters |
| Lawyer cards | Name, speciality, star rating, languages spoken, distance, city |
| Connect button per card | Opens contact/appointment flow |
| NALSA free aid box | Highlighted panel: "NALSA eligible? Check if you qualify for free legal counsel" |
| Case summary card | Auto-generated summary: topic, relevant law, language used |
| Export PDF button | Generates a PDF of the conversation for the lawyer |

### Gradio Mapping

```python
with gr.Tab("Find a Lawyer"):
    with gr.Row():
        filter_nearest = gr.Checkbox(label="Nearest", value=True)
        filter_specialty = gr.Dropdown(
            choices=LEGAL_SPECIALITIES,
            label="Speciality"
        )
        filter_language = gr.Dropdown(
            choices=SARVAM_LANGUAGES,
            label="Language"
        )

    lawyer_results = gr.Dataframe(
        headers=["Name", "Speciality", "Languages", "Rating", "Distance"],
        interactive=False
    )

    nalsa_check = gr.Button("Check NALSA eligibility →")
    nalsa_result = gr.Markdown(visible=False)

    case_summary = gr.Markdown(label="Your case summary")

    export_btn = gr.Button("Export conversation as PDF")
    pdf_output = gr.File(label="Download PDF", visible=False)
```

### Key Behaviour
- Lawyer data is fetched from a backend directory API filtered by geolocation (via browser `gr.BrowserState` for location), specialty, and language.
- The case summary is auto-generated from chat history: topic, cited law, language, key facts mentioned.
- PDF export uses `fpdf2` or `reportlab` to render the chat thread with citations into a downloadable file.
- NALSA eligibility is a simple form flow — income threshold, category (SC/ST/women/disabled/child) — returning a yes/no with the nearest legal aid centre address.

---

## Screen 06 — Settings

### Purpose
User control over language, voice, and privacy. Designed to be set once and forgotten.

### Layout & UI Components

| Component | Role |
|---|---|
| Interface language | Changes UI labels and LLM system prompt locale |
| Response language | "Same as input" (default) or a fixed override language |
| Voice responses toggle | On/off for TTS playback |
| Auto-play toggle | Whether audio plays immediately or waits for a tap |
| Voice speed slider | 0.75× to 1.5× playback speed |
| Save chat history toggle | Off by default for privacy |
| Anonymous mode toggle | On by default — no PII sent to backend |
| Clear all data button | Wipes session state and history |
| About | Version, legal disclaimer, data policy link |

### Gradio Mapping

```python
with gr.Tab("Settings"):
    interface_lang = gr.Dropdown(
        choices=SARVAM_LANGUAGES,
        label="Interface language",
        value="hi"
    )
    response_lang = gr.Dropdown(
        choices=["Same as input"] + SARVAM_LANGUAGES,
        label="Response language",
        value="Same as input"
    )
    voice_on = gr.Checkbox(label="Voice responses", value=True)
    autoplay = gr.Checkbox(label="Auto-play responses", value=False)
    voice_speed = gr.Slider(
        minimum=0.75, maximum=1.5, step=0.25,
        value=1.0,
        label="Voice speed"
    )
    save_history = gr.Checkbox(label="Save chat history", value=False)
    anonymous_mode = gr.Checkbox(label="Anonymous mode", value=True)
    clear_btn = gr.Button("Clear all data", variant="stop")

    # Persist settings to gr.State
    settings_state = gr.State({
        "interface_lang": "hi",
        "response_lang": "auto",
        "voice_on": True,
        "autoplay": False,
        "voice_speed": 1.0,
        "anonymous": True
    })
```

### Key Behaviour
- All settings are stored in `gr.State` (session-scoped) and optionally in `gr.BrowserState` for persistence across sessions.
- Anonymous mode prevents any user message text from being logged server-side.
- Voice speed is passed as a parameter to the Sarvam TTS `bulbul-v1` call.

---

## Full Gradio Component Map

| Screen | Gradio Component | Sarvam API |
|---|---|---|
| Language selector | `gr.Radio` / `gr.Dropdown` | — |
| Text input | `gr.Textbox` | — |
| Voice input | `gr.Audio(sources=["microphone"])` | `saaras-v2` (STT) |
| Live transcript | `gr.Textbox(interactive=False)` | `saaras-v2` streaming |
| Chat thread | `gr.Chatbot` | LLM (via translated prompt) |
| Text response | `gr.Markdown` | `mayura` (translation) |
| Audio response | `gr.Audio(interactive=False)` | `bulbul-v1` (TTS) |
| Topic chips | `gr.Radio(horizontal=True)` | — |
| Follow-up chips | `gr.Radio` (dynamically updated) | — |
| Lawyer results | `gr.Dataframe` | — |
| Case summary | `gr.Markdown` | LLM summary call |
| PDF export | `gr.File` | — |
| Settings state | `gr.State` + `gr.BrowserState` | — |
| Session language | `gr.State("hi")` | Passed to all API calls |

---

## Sarvam API Pipeline

```
User input (text or voice)
        │
        ▼
[If voice] saaras-v2 → transcript text
        │
        ▼
[If not Hindi] mayura → translate to English for LLM reasoning
        │
        ▼
LLM + RAG (Indian Acts, IPC, CPC, state-specific laws)
        │
        ▼
Response in English + citations
        │
        ▼
[If not English output] mayura → translate back to user's language
        │
        ▼
Render as gr.Markdown  +  bulbul-v1 → gr.Audio playback
```

---

## Supported Languages (Sarvam AI)

Hindi · Bengali · Telugu · Marathi · Tamil · Gujarati · Kannada · Malayalam · Odia · Punjabi · Assamese · Maithili · Sanskrit · Urdu · Konkani · Sindhi · Dogri · Kashmiri · Manipuri · Bodo · Santali · English

---

## Mandatory Disclaimers

Every response must append the following in the user's language:

> *This information is provided for general awareness only and does not constitute legal advice. For advice specific to your situation, please consult a qualified lawyer registered with the Bar Council of India. Nyaya Dhwani is not responsible for actions taken based on this information.*

The Hindi version (sample):
> *यह जानकारी केवल सामान्य जागरूकता के लिए है और कानूनी सलाह नहीं है। अपनी स्थिति के लिए बार काउंसिल ऑफ इंडिया में पंजीकृत वकील से परामर्श लें।*

---

*Nyaya Dhwani · न्याय ध्वनि · v1.0 Design Spec*