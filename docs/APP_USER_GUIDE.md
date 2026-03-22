# Nyaya Dhwani — App User Guide

Nyaya Dhwani is a multilingual legal information assistant for Indian law. It answers questions about the **Bharatiya Nyaya Sanhita (BNS)**, its predecessor the **Indian Penal Code (IPC)**, and the mappings between them. It is **not** a substitute for professional legal counsel.

## Getting started

1. Open the app URL provided by your Databricks workspace admin.
2. **Select your language** from the welcome screen — 13 languages are supported:
   - English, Hindi, Bengali, Kannada, Tamil, Telugu, Malayalam, Marathi, Gujarati, Odia, Punjabi, Assamese, Urdu
3. Click **Begin**.

## Asking questions

You can ask questions in two ways:

- **Type** your question in the text box in any supported language
- **Speak** your question using the microphone (requires Sarvam STT)

Then click **Send** or press Enter.

### Example questions

| Topic | Example |
|-------|---------|
| Theft | "What is theft under BNS? Give me the applicable IPC and BNS sections." |
| Tenant rights | "What are my basic rights as a tenant in India regarding eviction?" |
| Divorce | "What are the grounds for mutual consent divorce under Indian law?" |
| Consumer cases | "How do I file a consumer complaint for defective goods?" |
| RTI | "How do I file an RTI application and what fees apply?" |
| IPC to BNS mapping | "Explain IPC Section 378 and its related BNS Section." |

You can also click a **topic chip** on the chat screen to pre-fill an example question.

## Understanding the response

Each response contains:

1. **Answer in your selected language** (if non-English) — translated from the English RAG answer using Sarvam Mayura
2. **Answer in English** — the original LLM response for reference, so you can verify the translation
3. **Sources (retrieval)** — the BNS sections, IPC mappings, or other documents that were retrieved from the knowledge base
4. **Disclaimer** — a reminder that this is general information, not legal advice

If you selected English, only one version of the answer is shown.

### How it works behind the scenes

```
Your question (any language)
        │
        ▼
Translated to English (Sarvam Mayura)
        │
        ▼
Semantic search over 900+ legal text chunks (FAISS)
        │
        ▼
Top 5 relevant chunks sent to Databricks Llama Maverick LLM
        │
        ▼
English answer generated with citations
        │
        ▼
Translated back to your selected language (Sarvam Mayura)
        │
        ▼
Displayed as bilingual response + sources + disclaimer
```

## Voice features

### Speech-to-text (input)

- Click the **microphone** icon to record your question
- The audio is transcribed and translated to English using Sarvam Saaras STT
- The transcribed text appears in the chat as "🎤 ..."
- If you type text and also have a recording, the **typed text takes priority**

### Text-to-speech (output)

- Check **"Read answer aloud"** before sending your question
- The app reads the answer in your selected language using Sarvam Bulbul TTS
- Only the translated-language portion is read (not the English reference)

## Limitations

- **Not legal advice.** Nyaya Dhwani provides general legal information based on publicly available legal texts. Always consult a qualified lawyer for your specific situation.
- **Knowledge scope:** the current knowledge base covers BNS 2023 sections, IPC-to-BNS mappings, and select government schemes. It does not cover all Indian laws.
- **Translation quality:** translations are powered by Sarvam Mayura. Legal terminology may not always translate perfectly — use the English reference to verify.
- **Without Sarvam API key:** if the Sarvam key is not configured, the app works in English-only mode (no translation, no voice input, no TTS).
