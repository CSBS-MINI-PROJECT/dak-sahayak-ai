import re
import asyncio
import io
import threading
import edge_tts

# Voice mapping for Indian accents and regional Indian languages
INDIAN_VOICE_MAP = {
    'English': 'en-IN-NeerjaNeural',      # Natural Indian English (Female)
    'English-Male': 'en-IN-PrabhatNeural',# Natural Indian English (Male)
    'Hindi': 'hi-IN-SwaraNeural',          # Hindi (Female)
    'Hindi-Male': 'hi-IN-MadhurNeural',    # Hindi (Male)
    'Kannada': 'kn-IN-SapnaNeural',        # Kannada (Female)
    'Kannada-Male': 'kn-IN-GaganNeural',   # Kannada (Male)
    'Tamil': 'ta-IN-PallaviNeural',        # Tamil (Female)
    'Tamil-Male': 'ta-IN-ValluvarNeural',  # Tamil (Male)
    'Telugu': 'te-IN-ShrutiNeural',        # Telugu (Female)
    'Telugu-Male': 'te-IN-MohanNeural',    # Telugu (Male)
    'Marathi': 'mr-IN-AarohiNeural',       # Marathi (Female)
    'Marathi-Male': 'mr-IN-ManoharNeural', # Marathi (Male)
    'Bengali': 'bn-IN-TanishaaNeural',     # Bengali - India (Female)
    'Bengali-Male': 'bn-IN-BashkarNeural'  # Bengali - India (Male)
}

def clean_markdown_for_speech(text: str) -> str:
    """
    Cleans markdown formatting, emojis, special characters, and table lines
    to make the text sound completely natural when spoken aloud.
    """
    if not text:
        return ""

    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Remove inline code
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Replace markdown links [text](url) with just text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove images ![alt](url)
    text = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', text)
    # Remove headers (### Header -> Header)
    text = re.sub(r'#{1,6}\s*', '', text)
    # Remove bold/italic markers (*, **, _, __)
    text = re.sub(r'[\*_]{1,3}', '', text)
    # Remove blockquotes
    text = re.sub(r'^\s*>\s*', '', text, flags=re.MULTILINE)
    # Remove bullet markers at the beginning of lines (- , * , + )
    text = re.sub(r'^\s*[\-\*\+]\s+', '', text, flags=re.MULTILINE)
    # Remove numbered list markers at the beginning of lines (1. , 2. )
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    # Remove markdown table dividers (|---|---|)
    text = re.sub(r'\|[\-\:\s\|]+\|', '', text)
    # Remove table pipe characters
    text = re.sub(r'\|', ' ', text)
    # Remove emoji-like characters (common Unicode emoji ranges)
    text = re.sub(r'[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]', '', text)
    # Remove multiple spaces/newlines
    text = re.sub(r'\n{2,}', '\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)

    return text.strip()

def _run_async_in_thread(coro):
    """
    Runs an async coroutine in a fresh event loop on a new thread.
    This avoids conflicts with Flask's existing event loop.
    """
    result = [None]
    error = [None]

    def runner():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result[0] = loop.run_until_complete(coro)
            finally:
                loop.close()
        except Exception as e:
            error[0] = e

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join(timeout=60)  # 60 second timeout

    if error[0]:
        raise error[0]
    return result[0]

async def _synthesize_edge_tts(text: str, voice: str) -> bytes:
    """Async edge-tts synthesis coroutine."""
    communicate = edge_tts.Communicate(text, voice)
    audio_stream = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_stream.write(chunk["data"])
    audio_bytes = audio_stream.getvalue()
    print(f"[TTS] Synthesized {len(audio_bytes)} bytes with voice {voice}")
    return audio_bytes

def generate_indian_speech(text: str, language: str = 'English', gender: str = 'female') -> bytes:
    """
    Synthesizes speech from text using Microsoft Edge Neural Indian voices.
    Returns MP3 audio bytes.
    """
    clean_text = clean_markdown_for_speech(text)
    if not clean_text:
        print("[TTS] No text remaining after markdown cleanup")
        return b""

    # Automatically detect actual language from text unicode script if language is passed as default/English
    actual_lang = language
    if not language or language == 'English' or language == 'auto':
        if re.search(r'[ಀ-೿]', clean_text):      # Kannada
            actual_lang = 'Kannada'
        elif re.search(r'[ऀ-ॿ]', clean_text):    # Hindi / Devanagari
            actual_lang = 'Hindi'
        elif re.search(r'[஀-௿]', clean_text):    # Tamil
            actual_lang = 'Tamil'
        elif re.search(r'[ఀ-౿]', clean_text):    # Telugu
            actual_lang = 'Telugu'
        elif re.search(r'[ঀ-৿]', clean_text):    # Bengali
            actual_lang = 'Bengali'
        else:
            actual_lang = 'English'

    # Determine voice key based on language and gender
    is_male = str(gender).lower() == 'male'
    key = f"{actual_lang}-Male" if is_male else actual_lang
    voice = INDIAN_VOICE_MAP.get(key) or INDIAN_VOICE_MAP.get(actual_lang) or INDIAN_VOICE_MAP['English']

    # Limit maximum text length for single synthesis (edge-tts can handle ~5000 chars well)
    if len(clean_text) > 4000:
        clean_text = clean_text[:4000] + "..."

    print(f"[TTS] Generating speech: lang={language}, voice={voice}, text_len={len(clean_text)}")

    try:
        audio_bytes = _run_async_in_thread(_synthesize_edge_tts(clean_text, voice))
        if audio_bytes and len(audio_bytes) > 0:
            return audio_bytes
        print("[TTS] Warning: synthesis returned empty audio")
        return b""
    except Exception as e:
        print(f"[TTS Error] Synthesis failed with voice {voice}: {e}")
        # Fallback to English Indian voice if regional voice encounters an issue
        if voice != INDIAN_VOICE_MAP['English']:
            try:
                print(f"[TTS] Falling back to English Indian voice...")
                return _run_async_in_thread(_synthesize_edge_tts(clean_text, INDIAN_VOICE_MAP['English']))
            except Exception as fallback_err:
                print(f"[TTS Fallback Error]: {fallback_err}")
        raise e
