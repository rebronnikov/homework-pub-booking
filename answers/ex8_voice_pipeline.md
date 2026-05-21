# Ex8 — Voice pipeline

## Your answer

I exercised both paths: text mode (`make ex8-text`, session
`sess_8536c73e7941`) and voice mode (`make ex8-voice`, session
`sess_4e97c9774230`) against real Speechmatics + Rime keys.

The text run was a scripted four-turn conversation with the
Llama-3.3-70B manager: booking confirmation, mid-conversation date
change, hold-time question, sign-off. Llama-3.3 stayed in character
throughout — Alasdair's gruff Scottish register survived all four
turns ("Aye, we can do that. I'll pencil you in for Saturday at
19:30." → corrected to Friday when I changed the date → "We'll
hold it till end of day, then it's first come first served." →
"Aye, look forward tae hearin' from ye."). The trace has four
`voice.utterance_in` + four `voice.utterance_out` events with
`payload.mode = "text"`.

The voice run opened the Speechmatics websocket and the sounddevice
microphone, then exited gracefully on silence detection — no
utterances captured because this terminal didn't pipe audio in.
Importantly, the path didn't crash: STT was wired up, the silence
threshold fired, and the session ended cleanly. I independently
validated the full TTS path by POSTing to Rime
(`https://users.rime.ai/v1/rime-tts`, speaker `luna`, model
`arcana`) with text "Aye, we can do that. Pencil ye in for Friday."
— Rime returned 61KB of MP3 audio in `audio/mp3`, confirming the
auth + endpoint + speaker selection all work end-to-end.

Graceful degradation is the load-bearing piece. `run_voice_mode`
checks for `SPEECHMATICS_KEY` AND the `speechmatics-python` import
before opening any websocket; if either fails, it logs a warning
and falls through to `run_text_mode`. The same `--voice` invocation
therefore works on a laptop without a mic, on CI without keys, and
on a workstation with full setup. The trace shape is identical in
either mode — only `payload.mode` differs.

One stale file I removed: `starter/voice_pipeline/requirements-
voice.txt` listed `elevenlabs` and the wrong numpy version. The
canonical extras live in `pyproject.toml [voice]` (Rime via httpx,
not ElevenLabs).

## Citations

- `sess_8536c73e7941/logs/trace.jsonl` — four `voice.utterance_in` + four `voice.utterance_out` events, mode=text
- `sess_4e97c9774230/` — voice-mode session, mic opened + silence exit
- `starter/voice_pipeline/voice_loop.py` — run_text_mode, run_voice_mode, graceful degradation
- `starter/voice_pipeline/manager_persona.py` — Llama-3.3 backed persona with hardcoded booking rules
- `tests/public/test_ex8_scaffold.py::test_voice_mode_falls_back_when_no_speechmatics_key` — passes
- `pyproject.toml [project.optional-dependencies] voice` — canonical voice deps (Rime via httpx)
