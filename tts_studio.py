#!/usr/bin/env python3
"""TTS Studio — генерация озвучки через OpenRouter Audio Speech API (ElevenLabs v4 / v4-turbo)."""
import hashlib, html, json, os, random, re, shutil, subprocess, sys, time, traceback, uuid
from pathlib import Path
from string import Template
import math
import requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QMimeData, QTimer, QRegularExpression, QByteArray, QPointF, QRectF
from PyQt6.QtGui import (QColor, QDesktopServices, QDrag, QIcon, QImage, QKeySequence, QLinearGradient, QPainter, QPainterPath,
                         QPalette, QPixmap, QShortcut, QRegularExpressionValidator)
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QGroupBox,
                             QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                             QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSlider, QSplitter, QToolButton, QVBoxLayout,
                             QWidget, QLayout)
try:  # нормализация громкости (numpy + miniaudio для декодирования + lameenc для MP3)
    import numpy as np, miniaudio, lameenc
    AUDIO_OK, AUDIO_ERR = True, ""
except Exception as _e:
    AUDIO_OK, AUDIO_ERR = False, f"{type(_e).__name__}: {_e}"

APP_VERSION = "1.0.0"  # должна совпадать с git-тегом релиза (v1.0.0): это проверяет сборка в GitHub Actions
RELEASE_API = "https://api.github.com/repos/FreeSize83/tts-studio/releases/latest"
RELEASE_ASSET = "TTS-Studio.exe"
FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
PREVIEW_DIR = APP_DIR / "voice_previews"
CACHE_DIR = APP_DIR / "cache_takes"
INDEX_PATH = CACHE_DIR / "takes_index.json"
PLAYBACK_FILES = (CACHE_DIR / "_active_playback.mp3", CACHE_DIR / "_active_playback_alt.mp3")
MODELS_URL = "https://openrouter.ai/api/v1/models?output_modalities=speech"
SPEECH_URL = "https://openrouter.ai/api/v1/audio/speech"
EL_VOICES_URL = "https://api.elevenlabs.io/v1/voices"
EXTRA_HEADERS = {"HTTP-Referer": "https://localhost/tts-studio", "X-Title": "TTS Studio"}
PRIORITY_MODELS = ["elevenlabs/eleven-v4-turbo", "elevenlabs/eleven-v4"]
FALLBACK_MODELS = PRIORITY_MODELS + ["elevenlabs/eleven-v3"]
DEFAULT_VOICES = ["george", "sarah", "alice", "brian", "lily", "daniel", "aria", "river", "roger", "charlie", "callum",
                  "liam", "will", "jessica", "eric", "chris", "matilda", "bill", "adam", "rachel", "domi"]
# Справочник оформления + прямые ссылки Google Cloud (работают без VPN). Это НЕ фильтр списка голосов.
VOICE_DB = {
    "aria": {"gender": "female", "age": "Средний", "accent": "US", "desc": "Экспрессивный, живой, универсальный", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/9BWtsMINqrJLrRacOk9x/405766b8-1f4e-4d3c-aba1-6f25333823ec.mp3"},
    "Sarah": {"gender": "female", "age": "Молодой", "accent": "US", "desc": "Мягкий, спокойный, новостной", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/EXAVITQu4vr4xnSDxMaL/01a3e33c-6e99-4ee7-8543-ff2216a32186.mp3"},
    "laura": {"gender": "female", "age": "Молодой", "accent": "US", "desc": "Бодрый, четкий, динамичный", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/FGY2WhTYpPnrIDTdsKH5/67341759-ad08-41a5-be6e-de12fe448618.mp3"},
    "alice": {"gender": "female", "age": "Средний", "accent": "UK", "desc": "Уверенный, холодный, строгий (отлично под роботов/ИИ)", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/Xb7hH8MSUJpSbSDYk0k2/d10f7534-11f6-41fe-a012-2de1e482d336.mp3"},
    "matilda": {"gender": "female", "age": "Средний", "accent": "US", "desc": "Теплый, ровный рассказчик", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/XrExE9yKIg1WjnnlVkGX/b930e18d-6b4d-466e-bab2-0ae97c6d8535.mp3"},
    "jessica": {"gender": "female", "age": "Молодой", "accent": "US", "desc": "Выразительный, звонкий, разговорный", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/cgSgspJ2msm6clMCkdW9/56a97bf8-b69b-448f-846c-c3a11683d45a.mp3"},
    "lily": {"gender": "female", "age": "Средний", "accent": "UK", "desc": "Бархатный, сдержанный, низкий женский", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/pFZP5JQG7iQjIQuC4Bku/89b68b35-b3dd-4348-a84a-a3c13a3c2b30.mp3"},
    "rachel": {"gender": "female", "age": "Молодой", "accent": "US", "desc": "Ровный, классический женский диктор", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/21m00Tcm4TlvDq8ikWAM/df6788f9-5c96-470d-8312-aab3b3d8f50a.mp3"},
    "domi": {"gender": "female", "age": "Молодой", "accent": "US", "desc": "Плотный, напористый, четкий", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/AZnzlk1XvdvUeBnXmlld/53bd2f5f-bb59-4146-9922-245b2a466c80.mp3"},
    "river": {"gender": "neutral", "age": "Средний", "accent": "US", "desc": "Спокойный, ровный, синтетически-нейтральный", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/SAz9YHcvj6GT2YYXdXww/e6c95f0b-2227-491a-b3d7-2249240decb7.mp3"},
    "brian": {"gender": "male", "age": "Средний", "accent": "US", "desc": "Глубокий, мощный баритон (трейлеры, нарратив)", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/nPczCjzI2devNBz1zQrb/2dd3e72c-4fd3-42f1-93ea-abc5d4e5aa1d.mp3"},
    "george": {"gender": "male", "age": "Средний", "accent": "UK", "desc": "Густой, британский рассказчик", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/JBFqnCBsd6RMkjVDRZzb/e6206d1a-0721-4787-aafb-06a6e705cac5.mp3"},
    "daniel": {"gender": "male", "age": "Средний", "accent": "UK", "desc": "Строгий, авторитетный, документальный диктор", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/onwK4e9ZLuTAKqWW03F9/7eee0236-1a72-4b86-b303-5dcadc007ba9.mp3"},
    "callum": {"gender": "male", "age": "Средний", "accent": "US/UK", "desc": "Мрачный, хрипловатый, игровой персонаж", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/N2lVS1w4EtoT3dr4eOWO/ac833bd8-ffda-4938-9ebc-b0f99ca25481.mp3"},
    "roger": {"gender": "male", "age": "Средний", "accent": "US", "desc": "Уверенный, плотный мужской", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/CwhRBWXzGAHq8TQ4Fs17/58ee3ff5-f6f2-4628-93b8-e38eb31806b0.mp3"},
    "charlie": {"gender": "male", "age": "Средний", "accent": "AU", "desc": "Естественный, легкий разговорный", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/IKne3meq5aSn9XLyUdCD/102de6f2-22ed-43e0-a1f1-111fa75c5481.mp3"},
    "liam": {"gender": "male", "age": "Молодой", "accent": "US", "desc": "Четкий, молодой диктор", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/TX3LPaxmHKxFdv7VOQHJ/63148076-6363-42db-aea8-31424308b92c.mp3"},
    "will": {"gender": "male", "age": "Молодой", "accent": "US", "desc": "Мягкий, дружелюбный молодой", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/bIHbv24MWmeRgasZH58o/8caf8f3d-ad29-4980-af41-53f20c72d7a4.mp3"},
    "eric": {"gender": "male", "age": "Средний", "accent": "US", "desc": "Ровный, спокойный баритон", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/cjVigY5qzO86Huf0OWal/d098fda0-6456-4030-b3d8-63aa048c9070.mp3"},
    "chris": {"gender": "male", "age": "Средний", "accent": "US", "desc": "Повседневный, живой разговорный", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/iP95p4xoKVk53GoZ742B/3f4bde72-cc48-40dd-829f-57fbf906f4d7.mp3"},
    "bill": {"gender": "male", "age": "Пожилой", "accent": "US", "desc": "Зрелый, с хрипотцой, рассказчик", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/pqHfZKP75CvOlQylNhV4/d782b3ff-84ba-4029-848c-acf01285524d.mp3"},
    "adam": {"gender": "male", "age": "Средний", "accent": "US", "desc": "Классический глубокий закадровый голос", "url": "https://storage.googleapis.com/eleven-public-prod/premade/voices/pNInz6obpgDQGcFmaJgB/38a69695-2ca9-4b9e-b9ec-f07ced494a58.mp3"}
}
VOICE_DB = {k.lower(): v for k, v in VOICE_DB.items()}  # ключи в нижнем регистре ("Sarah" → "sarah")
GENDERS = {"female": ("♀", "#7a3b5e", "Женский"), "male": ("♂", "#2f5a7a", "Мужской"),
           "neutral": ("◐", "#4a5a3a", "Нейтральный"), "unknown": ("🎙", "#3a4a5e", "Другие / API")}
GENDER_ORDER = {"female": 0, "male": 1, "neutral": 2, "unknown": 3}
UNKNOWN_DESC = "Штатный голос модели (из API OpenRouter)"
QUICK_TAGS = ["[monotone]", "[cold]", "[flat delivery]", "[robotic]", "[whispering]", "[sighs]", "[short pause]", "[long pause]"]
RU_PREVIEW_TEXT = "[monotone, cold] Проверка тембра голоса. Система активна."
MAX_AGE = 7 * 24 * 3600
UPDATE_TEXT = "Обновить"
# Темы оформления: цвета + радиус скругления (разный «характер» стиля)
THEMES = {
    "DaVinci Studio": dict(bg="#1b1b1d", panel="#232326", card="#26262a", input="#141416", raised="#2e2e32", hover="#38383d", border="#333337",
                           border_hi="#55555b", text="#d4d4d6", dim="#8f8f96", faint="#5e5e64", accent="#e8833a", accent2="#c4452f",
                           on_accent="#111111", ok="#3fb950", soft="#3b2a1a", soft_text="#ffb27a", r=6),
    "Midnight Pro": dict(bg="#0d111a", panel="#141a26", card="#182030", input="#0a0e16", raised="#1d2536", hover="#253047", border="#232c3f",
                         border_hi="#3a4a6b", text="#dbe3f1", dim="#8390a8", faint="#4f5970", accent="#5b9dff", accent2="#8b5cf6",
                         on_accent="#ffffff", ok="#34d399", soft="#1b2a4a", soft_text="#9cc3ff", r=10),
    "Nord Frost": dict(bg="#2e3440", panel="#3b4252", card="#3f4758", input="#272c36", raised="#434c5e", hover="#4c566a", border="#4c566a",
                       border_hi="#6b7891", text="#eceff4", dim="#aeb6c4", faint="#727c8f", accent="#88c0d0", accent2="#81a1c1",
                       on_accent="#2e3440", ok="#a3be8c", soft="#3d5260", soft_text="#b5dfe9", r=8),
    "Neon Synthwave": dict(bg="#110a1c", panel="#1a1029", card="#1f1331", input="#0b0613", raised="#261839", hover="#33204c", border="#2f1f47",
                           border_hi="#5a3a85", text="#efe7ff", dim="#a493c4", faint="#5f5080", accent="#ff3ea5", accent2="#7b2cff",
                           on_accent="#ffffff", ok="#2de2a6", soft="#3a1236", soft_text="#ff8fcb", r=12),
    "Emerald": dict(bg="#0f1512", panel="#16201b", card="#1a2620", input="#0b100d", raised="#1f2c25", hover="#28392f", border="#24332b",
                    border_hi="#3d5a4a", text="#dcebe2", dim="#86a091", faint="#4f6458", accent="#34d399", accent2="#0ea5a4",
                    on_accent="#06140d", ok="#4ade80", soft="#143326", soft_text="#8ff0c6", r=10),
    "Graphite Mono": dict(bg="#121212", panel="#1a1a1a", card="#1e1e1e", input="#0e0e0e", raised="#262626", hover="#303030", border="#2a2a2a",
                          border_hi="#4a4a4a", text="#e6e6e6", dim="#8a8a8a", faint="#555555", accent="#f2f2f2", accent2="#9e9e9e",
                          on_accent="#111111", ok="#8bd17c", soft="#2a2a2a", soft_text="#ffffff", r=3),
    "Studio Light": dict(bg="#eef0f3", panel="#ffffff", card="#ffffff", input="#f6f7f9", raised="#f1f3f6", hover="#e6e9ee", border="#d8dce3",
                         border_hi="#b4bcc8", text="#1d2330", dim="#667085", faint="#b0b6c0", accent="#f76707", accent2="#e03131",
                         on_accent="#ffffff", ok="#2f9e44", soft="#fff0e6", soft_text="#c2410c", r=10),
}
DEFAULT_THEME = "DaVinci Studio"
CURRENT_THEME = DEFAULT_THEME
def th(): return THEMES.get(CURRENT_THEME, THEMES[DEFAULT_THEME])
WIN_FORBIDDEN = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
WIN_RESERVED = {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}
VOWELS = set("аеёиоуыэюяАЕЁИОУЫЭЮЯaeiouyAEIOUY")

# ---------------------------------------------------------------- helpers
def load_json(p, default):
    try:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        return data if isinstance(data, type(default)) else default
    except Exception:
        return default

def save_json(p, data):
    p = Path(p); tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"); os.replace(tmp, p)

def esc(s): return html.escape(str(s))
def safe_id(s): return re.sub(r"[^\w.-]+", "_", str(s)).strip("_") or "x"
def fmt_ms(ms): s = max(0, int(ms)) // 1000; return f"{s // 60:02d}:{s % 60:02d}"
def human_size(b): return f"{b / 1048576:.1f} МБ" if b >= 1048576 else f"{b / 1024:.0f} КБ"

def sanitize_filename(name):
    name = WIN_FORBIDDEN.sub("", name or "").strip(" .")
    if name.lower().endswith(".mp3"): name = name[:-4]
    name = name.strip(" .")[:120].strip(" .")
    if name.split(".")[0].upper() in WIN_RESERVED: name = "_" + name
    return name

def auto_name(text, n=4):
    t = re.sub(r"\[[^\]]*\]", " ", (text or "").replace("\u0301", ""))
    return sanitize_filename("_".join(re.findall(r"\w+", t)[:n]).lower()[:60]) or time.strftime("take_%H%M%S")

def unique_path(folder, base):
    p, i = folder / f"{base}.mp3", 2
    while p.exists(): p, i = folder / f"{base}_v{i}.mp3", i + 1
    return p

def norm_voices(v):
    out = []
    for x in v or []:
        k = x if isinstance(x, str) else (x.get("id") or x.get("voice_id") or x.get("name")) if isinstance(x, dict) else None
        if k and str(k) not in out: out.append(str(k))
    return out

def voice_meta(voice, model):
    """Оформление голоса. Неизвестный голос (нет в VOICE_DB или не ElevenLabs) → безопасная заглушка, без KeyError."""
    m = VOICE_DB.get(str(voice).lower()) if str(model).startswith("elevenlabs/") else None
    return dict(m) if m else {"gender": "unknown", "age": "—", "accent": "—", "desc": UNKNOWN_DESC, "url": ""}

def set_busy(btn, on):
    """Переключает кнопку в режим ожидания; молча игнорирует уже удалённые кнопки (закрытый диалог)."""
    try:
        if on: btn._orig = btn.text(); btn.setText("⏳ …"); btn.setEnabled(False)
        else: btn.setText(getattr(btn, "_orig", btn.text())); btn.setEnabled(True)
    except RuntimeError: pass

def parse_api_error(r):
    try:
        j = r.json(); e = j.get("error", j) if isinstance(j, dict) else j
        if isinstance(e, dict):
            msg = str(e.get("message") or json.dumps(e, ensure_ascii=False)); meta = e.get("metadata")
            if meta:
                raw = meta.get("raw") if isinstance(meta, dict) else None
                msg += "\n\nДетали: " + (raw if isinstance(raw, str) else json.dumps(meta, ensure_ascii=False))[:1500]
        else: msg = str(e)
    except Exception:
        msg = r.text[:1500] or "(пустой ответ)"
    hint = {401: "\n\nПроверьте API-ключ OpenRouter.", 402: "\n\nНедостаточно кредитов на балансе OpenRouter.",
            429: "\n\nСлишком много запросов — подождите немного."}.get(r.status_code, "")
    return f"HTTP {r.status_code}: {msg}{hint}"

def build_payload(model, text, voice, p, extended=True):
    body = {"model": model, "input": text, "voice": voice, "response_format": "mp3", "speed": round(float(p.get("speed", 1.0)), 2)}
    if extended and model.startswith("elevenlabs/"):
        el = {}
        if p.get("language") and p["language"] != "auto": el["language_code"] = p["language"]
        el["output_format"] = "mp3_44100_192"
        if str(p.get("seed", "")).strip(): el["seed"] = min(int(p["seed"]), 4294967295)
        for k in ("previous_text", "next_text"):
            if str(p.get(k, "")).strip(): el[k] = p[k].strip()
        el["voice_settings"] = {"stability": round(p["stability"], 2), "similarity_boost": round(p["similarity"], 2),
                                "style": round(p["style"], 2), "use_speaker_boost": True}
        body["provider"] = {"options": {"elevenlabs": el}}
    return body

# ---------------------------------------------------------------- loudness (EBU R128 / ITU-R BS.1770)
LOUDNESS_TARGETS = [("-14 LUFS · YouTube / соцсети", -14.0), ("-16 LUFS · голос / подкаст", -16.0),
                    ("-18 LUFS · спокойный диалог", -18.0), ("-23 LUFS · ТВ (EBU R128)", -23.0)]
PEAK_CEILING = -1.0  # dBFS: запас против клиппинга после MP3-кодирования

def _k_weighting(n, fs):
    """АЧХ K-фильтра BS.1770 (high-shelf + high-pass) для rfft-спектра длины n."""
    z1 = np.exp(-2j * np.pi * np.fft.rfftfreq(n, 1 / fs) / fs); z2 = z1 * z1
    bq = lambda b, a: (b[0] + b[1] * z1 + b[2] * z2) / (a[0] + a[1] * z1 + a[2] * z2)
    K, Q = math.tan(math.pi * 1681.974450955533 / fs), 0.7071752369554196
    Vh = 10 ** (3.999843853973347 / 20); Vb = Vh ** 0.4996667741545416
    shelf = bq((Vh + Vb * K / Q + K * K, 2 * (K * K - Vh), Vh - Vb * K / Q + K * K), (1 + K / Q + K * K, 2 * (K * K - 1), 1 - K / Q + K * K))
    K, Q = math.tan(math.pi * 38.13547087602444 / fs), 0.5003270373238773
    return shelf * bq((1, -2, 1), (1 + K / Q + K * K, 2 * (K * K - 1), 1 - K / Q + K * K)) * (1 + K / Q + K * K)

def integrated_lufs(x, fs):
    """Интегральная громкость: блоки 400 мс с шагом 100 мс, абсолютный (-70) и относительный (-10 LU) гейт."""
    n = len(x); y = np.fft.irfft(np.fft.rfft(x, axis=0) * _k_weighting(n, fs)[:, None], n=n, axis=0)
    blk, hop = int(0.4 * fs), int(0.1 * fs)
    if n < blk: z = np.array([(y ** 2).mean(axis=0).sum()])
    else:
        cs = np.vstack([np.zeros((1, y.shape[1])), np.cumsum(y ** 2, axis=0)]); st = np.arange(0, n - blk + 1, hop)
        z = ((cs[st + blk] - cs[st]) / blk).sum(axis=1)
    lk = lambda v: -0.691 + 10 * np.log10(np.maximum(v, 1e-12))
    z = z[lk(z) > -70]
    if not len(z): return -70.0
    z2 = z[lk(z) > lk(z.mean()) - 10]
    return float(lk((z2 if len(z2) else z).mean()))

def _soft_limit(y, ceil_lin, fs):
    """Мягкий пиковый лимитер: огибающая = скользящий минимум нужного ослабления, сглаженный окном 10 мс (без щелчков)."""
    need = np.minimum(1.0, ceil_lin / np.maximum(np.abs(y).max(axis=1), 1e-12))
    if need.min() >= 1: return y, False
    L = int(fs * 0.01) | 1; pad = L // 2
    mn = np.lib.stride_tricks.sliding_window_view(np.pad(need, pad, mode="edge"), L).min(axis=1)
    g = np.convolve(np.pad(mn, pad, mode="edge"), np.ones(L) / L, mode="valid")
    return y * np.minimum(g, need)[:, None], True

def normalize_mp3(src, dst, target=-16.0, ceiling=PEAK_CEILING, bitrate=192):
    """Декодирует MP3, приводит к целевой громкости (LUFS) с мягким лимитером на потолке пика и кодирует обратно в MP3."""
    d = miniaudio.decode(Path(src).read_bytes(), output_format=miniaudio.SampleFormat.FLOAT32)
    ch, fs = d.nchannels, d.sample_rate; x = np.frombuffer(d.samples, dtype=np.float32).astype(np.float64).reshape(-1, ch)
    before = integrated_lufs(x, fs); ceil_lin = 10 ** (ceiling / 20); gain = 0.0 if before <= -70 else min(target - before, 20.0)
    y, limited = _soft_limit(x * 10 ** (gain / 20), ceil_lin, fs); after = integrated_lufs(y, fs)
    for _ in range(3):  # лимитер слегка снижает громкость — догоняем цель
        if before <= -70 or abs(after - target) < 0.15 or gain >= 20: break
        gain = min(gain + target - after, 20.0); y, limited = _soft_limit(x * 10 ** (gain / 20), ceil_lin, fs); after = integrated_lufs(y, fs)
    pcm = (np.clip(y, -1, 1) * 32767).round().astype("<i2").tobytes()
    enc = lameenc.Encoder(); enc.set_bit_rate(bitrate); enc.set_in_sample_rate(fs); enc.set_channels(ch); enc.set_quality(2)
    data = enc.encode(pcm) + enc.flush(); dst = Path(dst); tmp = dst.with_name(dst.name + ".part")
    tmp.write_bytes(data); os.replace(tmp, dst)
    return {"before": before, "after": after, "gain": gain, "limited": limited}

# ---------------------------------------------------------------- app icon (рисуется кодом — без внешних файлов)
def make_icon_image(S=256):
    img = QImage(S, S, QImage.Format.Format_ARGB32_Premultiplied); img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setPen(Qt.PenStyle.NoPen)
    def grad(x0, y0, x1, y1):
        g = QLinearGradient(x0, y0, x1, y1)
        for pos, col in ((0, "#ffb03a"), (0.45, "#ff3d7f"), (1, "#5b2cff")): g.setColorAt(pos, QColor(col))
        return g
    m = S * 0.03; bg = QPainterPath(); bg.addRoundedRect(QRectF(m, m, S - 2 * m, S - 2 * m), S * 0.24, S * 0.24)
    p.fillPath(bg, grad(0, 0, S, S))
    gl = QLinearGradient(0, m, 0, S * 0.6); gl.setColorAt(0, QColor(255, 255, 255, 80)); gl.setColorAt(1, QColor(255, 255, 255, 0))
    p.fillPath(bg, gl)
    bx, by, bw, bh = S * 0.15, S * 0.28, S * 0.6, S * 0.42                       # облачко речи
    bub = QPainterPath(); bub.addRoundedRect(QRectF(bx, by, bw, bh), bh * 0.34, bh * 0.34)
    tail = QPainterPath(); tail.moveTo(bx + bw * 0.2, by + bh - 2); tail.lineTo(bx + bw * 0.1, by + bh + S * 0.14)
    tail.lineTo(bx + bw * 0.44, by + bh - 2); tail.closeSubpath(); bub = bub.united(tail)
    p.fillPath(bub.translated(0, S * 0.02), QColor(40, 0, 70, 70)); p.fillPath(bub, QColor("#ffffff"))
    hs = [0.45, 1.0, 0.7] if S <= 24 else [0.3, 0.62, 1.0, 0.72, 0.46, 0.84, 0.36]  # звуковая волна внутри
    step = bw * 0.74 / len(hs); w = step * 0.56; x0 = bx + bw * 0.13 + (step - w) / 2
    for i, h in enumerate(hs):
        r = QPainterPath(); hh = bh * 0.66 * h; r.addRoundedRect(QRectF(x0 + i * step, by + (bh - hh) / 2, w, hh), w / 2, w / 2)
        p.fillPath(r, grad(bx, by, bx + bw, by + bh))
    if S > 24:                                                                    # искра «ИИ»
        for cx, cy, rr in ((S * 0.81, S * 0.2, S * 0.085), (S * 0.9, S * 0.36, S * 0.04)):
            st = QPainterPath()
            for k in range(8):
                a = k * math.pi / 4 - math.pi / 2; d = rr if k % 2 == 0 else rr * 0.3
                (st.moveTo if k == 0 else st.lineTo)(QPointF(cx + d * math.cos(a), cy + d * math.sin(a)))
            st.closeSubpath(); p.fillPath(st, QColor("#ffffff"))
    p.end(); return img

def app_icon():
    ic = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256): ic.addPixmap(QPixmap.fromImage(make_icon_image(s)))
    return ic

def mkbtn(text, slot=None, tip=None, obj=None, w=None):
    b = QPushButton(text); b.setCursor(Qt.CursorShape.PointingHandCursor)
    if slot: b.clicked.connect(lambda _=False: slot())
    if tip: b.setToolTip(tip)
    if obj: b.setObjectName(obj)
    if w: b.setFixedWidth(w)
    return b

def _fill(lay, items):
    for it in items:
        if isinstance(it, int): lay.addStretch(it)
        elif isinstance(it, tuple): (lay.addLayout if isinstance(it[0], QLayout) else lay.addWidget)(it[0], it[1])
        elif isinstance(it, QLayout): lay.addLayout(it)
        else: lay.addWidget(it)
    return lay

def hbox(*items, m=0, s=6):
    l = QHBoxLayout(); l.setContentsMargins(m, m, m, m); l.setSpacing(s); return _fill(l, items)

def vbox(*items, m=0, s=6):
    l = QVBoxLayout(); l.setContentsMargins(m, m, m, m); l.setSpacing(s); return _fill(l, items)

def label(text, obj=None, tip=None, wrap=False):
    l = QLabel(text)
    if obj: l.setObjectName(obj)
    if tip: l.setToolTip(tip)
    l.setWordWrap(wrap); return l

# ---------------------------------------------------------------- workers (QThread)
class ModelsWorker(QThread):
    ok = pyqtSignal(list); fail = pyqtSignal(str)
    def __init__(self, key): super().__init__(); self.key = key
    def run(self):
        try:
            h = dict(EXTRA_HEADERS)
            if self.key: h["Authorization"] = f"Bearer {self.key}"
            r = requests.get(MODELS_URL, headers=h, timeout=25)
            if r.status_code != 200: return self.fail.emit(parse_api_error(r))
            self.ok.emit([m for m in (r.json().get("data") or []) if isinstance(m, dict)])
        except Exception as e: self.fail.emit(f"{type(e).__name__}: {e}")

class ElVoicesWorker(QThread):
    ok = pyqtSignal(dict); fail = pyqtSignal(str)
    def run(self):
        try:
            r = requests.get(EL_VOICES_URL, timeout=25)
            if r.status_code != 200: return self.fail.emit(f"HTTP {r.status_code}")
            m = {}
            for v in r.json().get("voices") or []:
                nm, url = (v.get("name") or "").strip().lower(), v.get("preview_url")
                if nm and url:
                    m.setdefault(re.split(r"[\s\-–(,]", nm, maxsplit=1)[0], url); m.setdefault(nm, url)
            self.ok.emit(m)
        except Exception as e: self.fail.emit(f"{type(e).__name__}: {e}")

class DownloadWorker(QThread):
    ok = pyqtSignal(str); fail = pyqtSignal(str)
    def __init__(self, url, path): super().__init__(); self.url, self.path = url, Path(path)
    def run(self):
        try:
            r = requests.get(self.url, timeout=(10, 60))
            if r.status_code != 200 or not r.content: return self.fail.emit(f"HTTP {r.status_code}")
            tmp = self.path.with_name(self.path.name + ".part"); tmp.write_bytes(r.content); os.replace(tmp, self.path)
            self.ok.emit(str(self.path))
        except Exception as e: self.fail.emit(f"{type(e).__name__}: {e}")

def version_tuple(v): return tuple(int(x) for x in re.findall(r"\d+", str(v))[:3])

def cleanup_update_files():
    if not FROZEN: return
    exe = Path(sys.executable)
    for p in (exe.with_name(exe.name + ".old"), exe.with_name(exe.name + ".new")):
        try: p.unlink(missing_ok=True)
        except OSError: pass  # старая версия ещё завершается — повторим позже

class UpdateWorker(QThread):
    """ok(tag, path): tag пуст — версия актуальна; path пуст — только проверка, без скачивания."""
    ok = pyqtSignal(str, str); fail = pyqtSignal(str); progress = pyqtSignal(int)
    def __init__(self, download): super().__init__(); self.download = download
    def run(self):
        try:
            r = requests.get(RELEASE_API, headers={"Accept": "application/vnd.github+json", "User-Agent": "TTS-Studio"}, timeout=(10, 25))
            if r.status_code != 200: return self.fail.emit(f"GitHub ответил HTTP {r.status_code}")
            rel = r.json(); tag = rel.get("tag_name") or ""
            if version_tuple(tag) <= version_tuple(APP_VERSION): return self.ok.emit("", "")
            if not self.download: return self.ok.emit(tag, "")
            urls = {a.get("name"): a.get("browser_download_url") for a in rel.get("assets") or []}
            url, sum_url = urls.get(RELEASE_ASSET), urls.get(RELEASE_ASSET + ".sha256")
            if not url or not sum_url: return self.fail.emit(f"В релизе {tag} нет файла {RELEASE_ASSET}")
            s = requests.get(sum_url, timeout=(10, 25)); s.raise_for_status(); want = s.text.split()[0].lower()
            exe = Path(sys.executable); new = exe.with_name(exe.name + ".new"); h = hashlib.sha256(); got = 0
            with requests.get(url, stream=True, timeout=(10, 60)) as d:
                d.raise_for_status(); total = int(d.headers.get("Content-Length") or 0)
                with open(new, "wb") as f:
                    for chunk in d.iter_content(1 << 18):
                        f.write(chunk); h.update(chunk); got += len(chunk)
                        if total: self.progress.emit(got * 100 // total)
            if h.hexdigest() != want:
                new.unlink(missing_ok=True); return self.fail.emit("Файл скачался повреждённым (не совпала контрольная сумма).")
            self.ok.emit(tag, str(new))
        except Exception as e: self.fail.emit(f"{type(e).__name__}: {e}")

class TTSWorker(QThread):
    ok = pyqtSignal(str, str); fail = pyqtSignal(str)
    def __init__(self, key, payload, out): super().__init__(); self.key, self.payload, self.out = key, payload, Path(out)
    def _post(self, body):
        h = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json", **EXTRA_HEADERS}
        return requests.post(SPEECH_URL, headers=h, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), timeout=(15, 240))
    def run(self):
        try:
            r, note = self._post(self.payload), ""
            if r.status_code in (400, 422) and "provider" in self.payload:
                code = r.status_code
                r = self._post({k: self.payload[k] for k in ("model", "input", "voice", "response_format", "speed")})
                note = f"⚠ Расширенные параметры ElevenLabs отклонены (HTTP {code}) — дубль сгенерирован без блока provider"
            if r.status_code != 200: return self.fail.emit(parse_api_error(r))
            data, ct = r.content, r.headers.get("Content-Type", "").lower()
            if not data or "json" in ct or data[:1] in (b"{", b"["):
                return self.fail.emit("API вернул 200, но в ответе не аудио:\n" + r.text[:1500])
            tmp = self.out.with_name(self.out.name + ".part"); tmp.write_bytes(data); os.replace(tmp, self.out)
            self.ok.emit(str(self.out), note)
        except requests.Timeout: self.fail.emit("Превышено время ожидания ответа от OpenRouter.")
        except Exception as e: self.fail.emit(f"{type(e).__name__}: {e}")

# ---------------------------------------------------------------- widgets
class TextEdit(QPlainTextEdit):
    submit = pyqtSignal()
    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            return self.submit.emit()
        super().keyPressEvent(e)

class ClickLabel(QLabel):
    clicked = pyqtSignal()
    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit()
        super().mouseReleaseEvent(e)

class DragButton(QPushButton):
    def __init__(self, text):
        super().__init__(text); self.path, self._p = None, None; self.setEnabled(False)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Зажмите и перетащите сохранённый файл на таймлайн DaVinci Resolve (или в любую папку)")
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self._p = e.position().toPoint()
        super().mousePressEvent(e)
    def mouseMoveEvent(self, e):
        if (self._p is not None and self.path and Path(self.path).is_file() and e.buttons() & Qt.MouseButton.LeftButton
                and (e.position().toPoint() - self._p).manhattanLength() >= QApplication.startDragDistance()):
            self._p = None; self.setDown(False)
            md = QMimeData(); md.setUrls([QUrl.fromLocalFile(self.path)])
            d = QDrag(self); d.setMimeData(md); d.setPixmap(self.grab()); d.exec(Qt.DropAction.CopyAction)
            return
        super().mouseMoveEvent(e)
    def mouseReleaseEvent(self, e): self._p = None; super().mouseReleaseEvent(e)

class AudioPlayer(QFrame):
    """Плеер всегда играет КОПИЮ файла (_active_playback.mp3) — оригиналы в кэше/проекте никогда не блокируются."""
    def __init__(self, status):
        super().__init__(); self.setObjectName("player"); self.status = status
        self.player, self.audio = QMediaPlayer(self), QAudioOutput(self)
        self.player.setAudioOutput(self.audio); self.audio.setVolume(0.9)
        self.title = label("— ничего не загружено —", "ptitle")
        self.btn_play, self.btn_stop = mkbtn("▶", self.toggle, "Play / Pause", "playbtn"), mkbtn("■", self.stop, "Stop", "roundbtn")
        self.btn_play.setFixedSize(44, 44); self.btn_stop.setFixedSize(34, 34)
        self.slider = QSlider(Qt.Orientation.Horizontal); self.slider.setRange(0, 0)
        self.slider.actionTriggered.connect(lambda _a: self.player.setPosition(self.slider.sliderPosition()))
        self.time = label("00:00 / 00:00", "ptime")
        self.vol = QSlider(Qt.Orientation.Horizontal); self.vol.setRange(0, 100); self.vol.setValue(90); self.vol.setFixedWidth(90)
        self.vol.valueChanged.connect(lambda v: self.audio.setVolume(v / 100)); self.vol.setToolTip("Громкость")
        self.autoplay = QCheckBox("Автовоспроизведение нового дубля"); self.autoplay.setChecked(True)
        self.setLayout(vbox(self.title, hbox(self.btn_play, self.btn_stop, (self.slider, 1), self.time),
                            hbox(self.autoplay, 1, label("🔊"), self.vol), m=10, s=8))
        self.player.positionChanged.connect(self._pos); self.player.durationChanged.connect(self._dur)
        self.player.playbackStateChanged.connect(lambda s: self.btn_play.setText("❚❚" if s == QMediaPlayer.PlaybackState.PlayingState else "▶"))
        self.player.errorOccurred.connect(lambda _e, msg: msg and self.status(f"Ошибка плеера: {msg}"))
    def _pos(self, p):
        if not self.slider.isSliderDown(): self.slider.setValue(p)
        self.time.setText(f"{fmt_ms(p)} / {fmt_ms(self.player.duration())}")
    def _dur(self, d): self.slider.setRange(0, max(0, d)); self.time.setText(f"{fmt_ms(self.player.position())} / {fmt_ms(d)}")
    def release(self): self.player.stop(); self.player.setSource(QUrl())
    def play_file(self, path, title=""):
        src = Path(path)
        if not src.is_file(): return self.status(f"Файл не найден: {src.name}")
        self.release(); dst = None
        for cand in PLAYBACK_FILES:
            try: shutil.copyfile(src, cand); dst = cand; break
            except OSError: continue
        if not dst: return self.status("Не удалось подготовить файл для воспроизведения (файл занят?)")
        self.title.setText(title or src.name); self.title.setToolTip(str(src))
        self.player.setSource(QUrl.fromLocalFile(str(dst))); self.player.play()
    def toggle(self):
        if self.player.source().isEmpty(): return
        self.player.pause() if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState else self.player.play()
    def stop(self): self.player.stop()

class TakeCard(QFrame):
    play = pyqtSignal(object); load = pyqtSignal(object); save = pyqtSignal(object); delete = pyqtSignal(object)
    def __init__(self, take):
        super().__init__(); self.take = take; self.setObjectName("card"); p = take.get("params", {})
        ts = time.strftime("%d.%m.%Y  %H:%M:%S", time.localtime(take.get("created", 0)))
        char = take.get("character") or ""
        head = hbox(label(f"<b>{ts}</b>"), label(esc(take.get("model", "")), "chip"), label(f"🎤 {esc(take.get('voice', ''))}", "chip" if char else "chipacc"),
                    *([label(f"🎭 {esc(char)}", "chipacc")] if char else []), 1, s=8)
        meta = f"Stab {p.get('stability', 0):.2f} · Sim {p.get('similarity', 0):.2f} · Style {p.get('style', 0):.2f} · " \
               f"Speed {p.get('speed', 1):.2f} · Seed {p.get('seed') or '—'} · Lang {p.get('language', '—')}"
        if not take.get("model", "").startswith("elevenlabs/") or not p.get("extended", True): meta += " · базовые параметры"
        if p.get("fallback"): meta += " · ⚠ без расширенных (fallback)"
        text = take.get("text", "")
        txt = ClickLabel(text if len(text) <= 420 else text[:420] + "…"); txt.setObjectName("taketext")
        txt.setTextFormat(Qt.TextFormat.PlainText); txt.setWordWrap(True); txt.setCursor(Qt.CursorShape.PointingHandCursor)
        txt.setToolTip("Клик — вернуть текст и все настройки этого дубля в редактор"); txt.clicked.connect(lambda: self.load.emit(self.take))
        self.ed_name = QLineEdit(Path(take["exported_name"]).stem if take.get("exported_name") else auto_name(f"{char} {text}", 5 if char else 4))
        self.ed_name.setPlaceholderText("Название файла"); self.ed_name.returnPressed.connect(lambda: self.save.emit(self))
        self.b_drag = DragButton("✋ Drag to DaVinci")
        self.lbl_saved = label("", "saved"); self.lbl_saved.hide()
        self.setLayout(vbox(
            hbox((head, 1), mkbtn("🗑", lambda: self.delete.emit(self), "Удалить дубль из кэша", w=34)),
            label(meta, "meta"), txt,
            hbox(mkbtn("▶ Прослушать", lambda: self.play.emit(self.take)), mkbtn("✎ В редактор", lambda: self.load.emit(self.take),
                 "Вернуть текст и настройки в левую панель"), 1, self.b_drag),
            hbox(label("Название файла:"), (self.ed_name, 1),
                 mkbtn("💾 Сохранить в папку", lambda: self.save.emit(self), "Скопировать дубль в папку проекта (Enter в поле имени)")),
            self.lbl_saved, m=10, s=6))
        if take.get("saved") and take.get("exported_path"): self.mark_saved()
    def mark_saved(self):
        path = self.take.get("exported_path", ""); ok = Path(path).is_file()
        lufs = self.take.get("export_lufs")
        self.lbl_saved.setText(f"✓ Сохранено как: {self.take.get('exported_name', '')}" + (f"   ·   {lufs:.1f} LUFS" if lufs is not None else "")
                               + ("" if ok else "   (файл в папке проекта не найден)"))
        self.lbl_saved.setToolTip(path); self.lbl_saved.show()
        self.b_drag.path = path if ok else None; self.b_drag.setEnabled(ok)

# ---------------------------------------------------------------- voice picker
class VoiceCard(QFrame):
    picked = pyqtSignal(str)
    def __init__(self, voice, meta, en_url, owner, current, on_add=None):
        super().__init__(); self.voice, self.meta, self.owner = voice, meta, owner
        self.setObjectName("vcard"); self.setProperty("current", current); self.setMinimumHeight(150)
        ico, col, gname = GENDERS.get(meta.get("gender"), GENDERS["unknown"])
        icon = QLabel(ico); icon.setFixedSize(46, 46); icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(f"background: {col}; border-radius: 23px; font-size: 18pt; color: #fff;")
        sub = f"{gname} · {meta['age']} · {meta['accent']}" if meta["gender"] != "unknown" else "Другие / API · пол не указан"
        name = f"<b style='font-size:12pt'>{esc(voice)}</b>" + (f" &nbsp;<span style='color:{th()['accent']}'>● выбран</span>" if current else "")
        self.dot = label("●"); self.refresh_dot()
        self.b_en = mkbtn("▶ EN (Free)", lambda: owner.preview_en(voice, self.b_en), "Бесплатный сэмпл (Google Cloud, без VPN)") if en_url else None
        self.b_ru = mkbtn("▶ Тест RU (Кэш)", lambda: owner.preview_ru(voice, self.b_ru, self.refresh_dot),
                          "Русская фраза через OpenRouter API — генерируется 1 раз и кэшируется навсегда")
        self.setLayout(vbox(hbox(icon, (vbox(label(name), label(sub, "meta"), s=2), 1)), (label(meta["desc"], "vdesc", wrap=True), 1),
                            hbox(*([self.b_en] if self.b_en else []), self.b_ru, self.dot, 1,
                                 *([mkbtn("🎭", lambda: on_add(voice), "Добавить в профиль как персонажа", w=38)] if on_add else []),
                                 mkbtn("✓ Выбрать", lambda: self.picked.emit(voice), obj="pickbtn")), m=10, s=8))
        self.setToolTip(f"ID для API: {voice}\nДвойной клик — выбрать")
    def refresh_dot(self):
        try:
            ok = self.owner.ru_path(self.owner.model(), self.voice).is_file()
            self.dot.setStyleSheet(f"color: {th()['ok'] if ok else th()['faint']}; font-size: 13pt;")
            self.dot.setToolTip("RU-превью уже в кэше" if ok else "RU-превью ещё не создано")
        except RuntimeError: pass
    def mouseDoubleClickEvent(self, e): self.picked.emit(self.voice)

class CharacterDialog(QDialog):
    """Добавление / редактирование персонажа: имя + голос + (опционально) снимок настроек голоса."""
    def __init__(self, parent, voice, name="", has_settings=False, edit=False):
        super().__init__(parent); self.setWindowTitle("Изменить персонажа" if edit else "Новый персонаж"); self.setMinimumWidth(440)
        self.ed_name = QLineEdit(name); self.ed_name.setPlaceholderText("например: Капитан, Рассказчик, ИИ-ассистент")
        self.ed_voice = QLineEdit(voice)
        txt = ("Заменить сохранённые настройки текущими" if has_settings else "Запомнить текущие настройки голоса") if edit else "Запомнить текущие настройки голоса"
        self.chk = QCheckBox(f"{txt}\n(Stability, Similarity, Style, Speed, язык)"); self.chk.setChecked(not edit)
        self.ed_name.returnPressed.connect(self._ok)
        self.setLayout(vbox(label("Имя персонажа:"), self.ed_name, label("Голос (имя или ID):"), self.ed_voice, self.chk,
                            hbox(1, mkbtn("Отмена", self.reject), mkbtn("✓ Сохранить", self._ok, obj="pickbtn")), m=16, s=8))
        self.ed_name.setFocus()
    def _ok(self):
        if self.ed_name.text().strip() and self.ed_voice.text().strip(): self.accept()
        else: self.ed_name.setFocus()
    def data(self): return self.ed_name.text().strip(), self.ed_voice.text().strip(), self.chk.isChecked()

class VoicePickerDialog(QDialog):
    FILTERS = (("all", "Все"), ("female", "♀ Женские"), ("male", "♂ Мужские"), ("neutral", "◐ Нейтральные"), ("unknown", "🎙 Другие / API"))
    def __init__(self, owner, voices, current, model):
        super().__init__(owner); self.selected, self.filter, self.cols = None, "all", 0
        self.owner, self.model, self.selected_char = owner, model, None
        self.setWindowTitle(f"Выбор голоса — {model}"); self.resize(1340, 780)
        items = sorted(((v, voice_meta(v, model)) for v in voices), key=lambda x: (GENDER_ORDER.get(x[1]["gender"], 3), x[0].lower()))
        self.grid_w = QWidget(); self.grid = QGridLayout(); self.grid.setSpacing(10)
        self.grid_w.setLayout(vbox(self.grid, 1))
        self.cards = []
        for v, m in items:
            c = VoiceCard(v, m, owner.en_url(v, model), owner, v == current, self.add_character); c.setParent(self.grid_w); c.hide()
            c.picked.connect(self._pick); self.cards.append(c)
        self.search = QLineEdit(); self.search.setPlaceholderText("🔍 Поиск: имя, ID, описание, акцент…"); self.search.textChanged.connect(self.apply_filter)
        group = QButtonGroup(self); fbtns = []
        for key, text in self.FILTERS:
            n = len(self.cards) if key == "all" else sum(c.meta["gender"] == key for c in self.cards)
            b = QPushButton(f"{text} ({n})"); b.setObjectName("filt"); b.setCheckable(True); b.setChecked(key == "all")
            b.setCursor(Qt.CursorShape.PointingHandCursor); b.clicked.connect(lambda _=False, k=key: self._set_filter(k)); group.addButton(b); fbtns.append(b)
        self.count = label("", "meta")
        self.sc = sc = QScrollArea(); sc.setWidgetResizable(True); sc.setWidget(self.grid_w)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.manual = QLineEdit(); self.manual.setPlaceholderText("например: george, 21m00Tcm4TlvDq8ikWAM, Kore")
        self.manual.returnPressed.connect(self._manual)
        # --- боковая панель: профили и персонажи
        self.cb_prof = QComboBox(); self.cb_prof.currentTextChanged.connect(self._prof_changed)
        self.char_list = QListWidget(); self.char_list.setObjectName("charlist"); self.char_list.itemDoubleClicked.connect(lambda _it: self._char_pick())
        self.char_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.char_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.side_hint = label("", "hint", wrap=True)
        side = QFrame(); side.setObjectName("sidebar"); side.setFixedWidth(290)
        side.setLayout(vbox(label("ПРОФИЛИ", "sidehead"),
                            hbox((self.cb_prof, 1), mkbtn("＋", self._prof_new, "Новый профиль (проект)", w=34),
                                 mkbtn("✎", self._prof_rename, "Переименовать профиль", w=34), mkbtn("🗑", self._prof_delete, "Удалить профиль", w=34), s=4),
                            label("ПЕРСОНАЖИ", "sidehead"), (self.char_list, 1),
                            hbox(mkbtn("✎", self._char_edit, "Изменить имя, голос или настройки", w=34),
                                 mkbtn("🗑", self._char_remove, "Убрать персонажа из профиля", w=34), 1,
                                 mkbtn("✓ Выбрать персонажа", self._char_pick, obj="pickbtn"), s=4),
                            self.side_hint, m=12, s=8))
        self.setLayout(vbox(hbox(side, (vbox(self.search, hbox(*fbtns, 1, self.count), (sc, 1), s=10), 1), s=12),
                            hbox(label("Ввести имя или ID голоса вручную:"), (self.manual, 1), mkbtn("Применить", self._manual),
                                 mkbtn("⏹ Стоп", owner.player.stop, "Остановить превью"), mkbtn("Закрыть", self.reject)), m=12, s=10))
        self.refresh_side(); self.apply_filter(); self.search.setFocus()

    # --- профили / персонажи
    def refresh_side(self, select=None):
        P, o = self.owner.profiles, self.owner
        self.cb_prof.blockSignals(True); self.cb_prof.clear(); self.cb_prof.addItems(list(P))
        if o.active_profile in P: self.cb_prof.setCurrentText(o.active_profile)
        self.cb_prof.blockSignals(False); self.cb_prof.setEnabled(bool(P)); self.char_list.clear()
        for ch in P.get(o.active_profile, []):
            ico = GENDERS.get(voice_meta(ch["voice"], self.model)["gender"], GENDERS["unknown"])[0]
            mark = "   ● выбран" if ch["name"] == o.cur_character else ""
            it = QListWidgetItem(f"🎭  {ch['name']}{mark}\n        {ico} {ch['voice']}" + ("  ·  свои настройки" if ch.get("settings") else ""))
            it.setData(Qt.ItemDataRole.UserRole, ch["name"]); it.setToolTip(f"Голос: {ch['voice']}\nДвойной клик — выбрать"); self.char_list.addItem(it)
            if ch["name"] == select: self.char_list.setCurrentItem(it)
        self.side_hint.setText("Создайте профиль кнопкой «＋» или сразу нажмите 🎭 на карточке голоса." if not P else
                               "Нажмите 🎭 на карточке голоса, чтобы добавить персонажа в профиль." if not P.get(o.active_profile) else
                               "Двойной клик по персонажу — выбрать голос и его настройки.")
    def _ask(self, title, text, val=""):
        s, ok = QInputDialog.getText(self, title, text, QLineEdit.EchoMode.Normal, val); return s.strip() if ok else ""
    def _commit(self, select=None): self.owner.save_cfg(); self.owner.refresh_profile_ui(); self.refresh_side(select)
    def _prof_changed(self, name):
        if name in self.owner.profiles: self.owner.active_profile = name; self._commit()
    def _prof_new(self):
        n = self._ask("Новый профиль", "Название профиля (например, проекта или видео):")
        if not n: return
        if n in self.owner.profiles: return QMessageBox.information(self, "Профиль", f"Профиль «{n}» уже существует.")
        self.owner.profiles[n] = []; self.owner.active_profile = n; self._commit()
    def _prof_rename(self):
        old = self.owner.active_profile; n = self._ask("Переименовать профиль", "Новое название:", old) if old else ""
        if not n or n == old: return
        if n in self.owner.profiles: return QMessageBox.information(self, "Профиль", f"Профиль «{n}» уже существует.")
        self.owner.profiles = {(n if k == old else k): v for k, v in self.owner.profiles.items()}; self.owner.active_profile = n; self._commit()
    def _prof_delete(self):
        old = self.owner.active_profile
        if not old or QMessageBox.question(self, "Удалить профиль", f"Удалить профиль «{old}» со всеми персонажами?") != QMessageBox.StandardButton.Yes: return
        del self.owner.profiles[old]; self.owner.active_profile = next(iter(self.owner.profiles), ""); self.owner.cur_character = ""; self._commit()
    def add_character(self, voice):
        o = self.owner
        if not o.profiles: o.profiles["Мой проект"] = []; o.active_profile = "Мой проект"
        dlg = CharacterDialog(self, voice)
        if dlg.exec():
            name, v, keep = dlg.data(); chars = o.profiles[o.active_profile]
            entry = {"name": name, "voice": v, "settings": o.character_settings() if keep else None}
            i = next((k for k, c in enumerate(chars) if c["name"] == name), None)
            if i is None: chars.append(entry)
            else: chars[i] = entry
            self._commit(name); o.status(f"Персонаж «{name}» ({v}) добавлен в профиль «{o.active_profile}»")
        dlg.deleteLater()
    def _cur_char(self):
        it = self.char_list.currentItem(); return self.owner.get_character(it.data(Qt.ItemDataRole.UserRole)) if it else None
    def _char_pick(self):
        ch = self._cur_char()
        if ch: self.selected, self.selected_char = ch["voice"], ch; self.accept()
    def _char_edit(self):
        ch = self._cur_char()
        if not ch: return
        dlg = CharacterDialog(self, ch["voice"], ch["name"], bool(ch.get("settings")), edit=True)
        if dlg.exec():
            name, v, upd = dlg.data(); chars = self.owner.profiles[self.owner.active_profile]
            if name != ch["name"] and any(c["name"] == name for c in chars):
                return QMessageBox.information(self, "Персонаж", f"Персонаж «{name}» уже есть в профиле.")
            if self.owner.cur_character == ch["name"]: self.owner.cur_character = name
            ch.update(name=name, voice=v, settings=self.owner.character_settings() if upd else ch.get("settings")); self._commit(name)
        dlg.deleteLater()
    def _char_remove(self):
        ch = self._cur_char()
        if not ch or QMessageBox.question(self, "Убрать персонажа", f"Убрать «{ch['name']}» из профиля?") != QMessageBox.StandardButton.Yes: return
        self.owner.profiles[self.owner.active_profile].remove(ch)
        if self.owner.cur_character == ch["name"]: self.owner.cur_character = ""
        self._commit()

    def _set_filter(self, k): self.filter = k; self.apply_filter()
    def _calc_cols(self): return max(1, min(4, (self.width() - 350) // 420))
    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._calc_cols() != self.cols: self.apply_filter()
    def apply_filter(self):
        q = self.search.text().strip().lower(); shown = 0; self.cols = cols = self._calc_cols()
        while self.grid.count(): self.grid.takeAt(0)
        for i in range(4): self.grid.setColumnStretch(i, 1 if i < cols else 0)
        for c in self.cards:
            m = c.meta; hay = f"{c.voice} {m['desc']} {m['accent']} {m['age']} {GENDERS.get(m['gender'], GENDERS['unknown'])[2]}".lower()
            if (self.filter == "all" or m["gender"] == self.filter) and (not q or q in hay):
                self.grid.addWidget(c, shown // cols, shown % cols); c.show(); shown += 1
            else: c.hide()
        self.count.setText(f"Показано: {shown} из {len(self.cards)}")
    def _pick(self, v): self.selected = v; self.accept()
    def _manual(self):
        v = self.manual.text().strip()
        if v: self.selected = v; self.accept()

# ---------------------------------------------------------------- main window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("TTS Studio — OpenRouter × ElevenLabs v4"); self.resize(1500, 940)
        for d in (PREVIEW_DIR, CACHE_DIR): d.mkdir(parents=True, exist_ok=True)
        self.cfg = load_json(CONFIG_PATH, {}); self.takes = [t for t in load_json(INDEX_PATH, []) if isinstance(t, dict) and t.get("file")]
        self.models, self.en_previews, self.en_state = {}, {}, "loading"
        self.workers, self.cards, self.custom_tags = set(), {}, list(self.cfg.get("custom_tags", []))
        self.cur_voice, self.voice_list, self.custom_voices = "", [], [str(v) for v in self.cfg.get("custom_voices", []) if str(v).strip()]
        self.wanted_model = self.cfg.get("model") or PRIORITY_MODELS[0]; self.wanted_voice = self.cfg.get("voice") or "george"
        self.gen_started = 0.0; self.gen_timer = QTimer(self); self.gen_timer.setInterval(500); self.gen_timer.timeout.connect(self._tick)
        self.cache_lbl = label("", "cachelbl"); self.statusBar().addPermanentWidget(self.cache_lbl)
        self.profiles = {str(k): [c for c in v if isinstance(c, dict) and c.get("name") and c.get("voice")]
                         for k, v in (self.cfg.get("profiles") or {}).items() if isinstance(v, list)}
        self.active_profile = self.cfg.get("active_profile") if self.cfg.get("active_profile") in self.profiles else next(iter(self.profiles), "")
        self.cur_character = str(self.cfg.get("character") or "")
        self._loading = True; self._build_ui(); self._apply_config(); self._loading = False
        self.setWindowIcon(app_icon())
        self._fill_models({m: {"id": m, "name": m} for m in FALLBACK_MODELS})
        removed = self.cleanup_cache()
        for t in sorted(self.takes, key=lambda t: t.get("created", 0)): self.add_card(t)
        self.update_cache_status()
        self.status(f"Автоочистка: удалено старых дублей (> 7 дней): {removed}" if removed else "Готово к работе")
        self.refresh_models(); self.fetch_en_previews()
        self.restart_exe = None
        draft = self.cfg.pop("update_draft", "")  # текст из редактора, сохранённый перед обновлением
        if draft: self.txt.setPlainText(draft)
        for ms in (0, 4000, 15000): QTimer.singleShot(ms, cleanup_update_files)
        if FROZEN: self._start(UpdateWorker(False), lambda tag, _p: self._update_offer(tag))

    # ---------- UI
    def _build_ui(self):
        sp = QSplitter(Qt.Orientation.Horizontal); sp.setChildrenCollapsible(False)
        left = QScrollArea(); left.setWidgetResizable(True); left.setMinimumWidth(470); left.setWidget(self._build_left())
        sp.addWidget(left); sp.addWidget(self._build_right()); sp.setSizes([600, 900]); self.splitter = sp
        top = QFrame(); top.setObjectName("topbar")
        self.cb_theme = QComboBox(); self.cb_theme.setMinimumWidth(190); self.cb_theme.setToolTip("Стиль оформления — применяется сразу")
        for name, t in THEMES.items(): self.cb_theme.addItem(theme_icon(t), name)
        self.cb_theme.setCurrentText(CURRENT_THEME); self.cb_theme.currentTextChanged.connect(self.set_theme)
        self.btn_update = mkbtn(UPDATE_TEXT, self.update_app, f"Установлена версия {APP_VERSION}. Скачивает новую версию и сразу перезапускает программу — настройки и дубли сохраняются")
        top.setLayout(hbox(label("🎙", "logoicon"), vbox(label("TTS Studio", "logo"), label("OpenRouter  ×  ElevenLabs v4", "logosub"), s=0), 1,
                           label(f"v{APP_VERSION}", "logosub"), self.btn_update, label("Стиль:", "logosub"), self.cb_theme, m=0, s=10))
        top.layout().setContentsMargins(16, 8, 16, 8)
        c = QWidget(); c.setLayout(vbox(top, (sp, 1), s=0)); self.setCentralWidget(c)
        for seq in ("Ctrl+Return", "Ctrl+Enter"): QShortcut(QKeySequence(seq), self, activated=self.generate)

    # ---------- обновление программы
    def _update_offer(self, tag):
        if not tag or not self.btn_update.isEnabled(): return
        self.btn_update.setText(f"↑ Обновить до {tag}"); self.btn_update.setObjectName("accentbtn")
        self.btn_update.style().unpolish(self.btn_update); self.btn_update.style().polish(self.btn_update)

    def update_app(self):
        if not FROZEN: return QMessageBox.information(self, "Обновление", "Обновление работает только в собранной программе (.exe).")
        self.btn_update.setEnabled(False); self.btn_update.setText("Проверка…")
        w = UpdateWorker(True); w.progress.connect(lambda p: self.btn_update.setText(f"Скачивание {p}%"))
        self._start(w, self._on_update_ready, self._on_update_fail)

    def _on_update_fail(self, msg):
        self.btn_update.setEnabled(True); self.btn_update.setText(UPDATE_TEXT)
        QMessageBox.warning(self, "Обновление", f"Не удалось обновить программу:\n{msg}")

    def _on_update_ready(self, tag, path):
        if not tag:
            self.btn_update.setText("✓ Последняя версия"); self.status(f"У вас последняя версия: {APP_VERSION}")
            def reset(): self.btn_update.setEnabled(True); self.btn_update.setText(UPDATE_TEXT)
            return QTimer.singleShot(4000, reset)
        if self.gen_timer.isActive():  # не обрываем идущую генерацию
            self.btn_update.setText("Ждём генерацию…"); return QTimer.singleShot(1000, lambda: self._on_update_ready(tag, path))
        exe = Path(sys.executable); old = exe.with_name(exe.name + ".old")
        try:  # Windows не даёт перезаписать запущенный exe, но позволяет его переименовать
            old.unlink(missing_ok=True); exe.rename(old)
            try: os.replace(path, exe)
            except OSError: old.rename(exe); raise
        except OSError as e: return self._on_update_fail(f"{e}\nПроверьте, что папка программы доступна для записи.")
        self.cfg["update_draft"] = self.txt.toPlainText(); self.restart_exe = exe; self.close()

    def set_theme(self, name):
        if name not in THEMES: return
        apply_theme(QApplication.instance(), name); self.update_cost(); self.update_ru_dot(); self.save_cfg()
        self.status(f"Стиль: {name}")

    def _build_left(self):
        w = QWidget(); L = QVBoxLayout(w); L.setContentsMargins(10, 6, 6, 10); L.setSpacing(8)
        # 1. ключ + папка
        g = QGroupBox("Доступ и проект"); gl = QGridLayout(g)
        self.ed_key = QLineEdit(); self.ed_key.setEchoMode(QLineEdit.EchoMode.Password); self.ed_key.setPlaceholderText("sk-or-v1-…")
        self.ed_key.editingFinished.connect(self.save_cfg)
        eye = QToolButton(); eye.setText("👁"); eye.setCheckable(True); eye.setToolTip("Показать / скрыть ключ")
        eye.toggled.connect(lambda on: self.ed_key.setEchoMode(QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
        self.ed_folder = QLineEdit(); self.ed_folder.setPlaceholderText("Не выбрана — например C:/Projects/Video1/Audio")
        self.ed_folder.editingFinished.connect(self.save_cfg)
        gl.addWidget(label("API-ключ:"), 0, 0); gl.addWidget(self.ed_key, 0, 1); gl.addWidget(eye, 0, 2)
        gl.addWidget(label("Папка сохранения:"), 1, 0); gl.addWidget(self.ed_folder, 1, 1)
        gl.addLayout(hbox(mkbtn("Обзор…", self.choose_folder), mkbtn("📂", self.open_folder, "Открыть папку в Проводнике", w=36)), 1, 2)
        self.chk_norm = QCheckBox("Нормализовать при сохранении")
        self.cb_norm = QComboBox(); self.cb_norm.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.cb_norm.setMinimumContentsLength(10)
        for t, v in LOUDNESS_TARGETS: self.cb_norm.addItem(t, v)
        tip = ("Приводит громкость сохраняемого файла к стандарту LUFS (EBU R128) с мягким лимитером пиков ≤ −1 dBFS.\n"
               "Оригинал в кэше не меняется." if AUDIO_OK else f"Недоступно: не загрузились numpy / miniaudio / lameenc\n({AUDIO_ERR})")
        for wd in (self.chk_norm, self.cb_norm): wd.setToolTip(tip); wd.setEnabled(AUDIO_OK)
        self.chk_norm.toggled.connect(lambda on: (self.cb_norm.setEnabled(on and AUDIO_OK), self.save_cfg()))
        self.cb_norm.currentIndexChanged.connect(lambda _i: self.save_cfg())
        gl.addWidget(label("Громкость:"), 2, 0); gl.addLayout(hbox(self.chk_norm, (self.cb_norm, 1)), 2, 1, 1, 2)
        gl.setColumnStretch(1, 1); L.addWidget(g)
        # 2. модель + голос
        g = QGroupBox("Модель и голос"); gl = QGridLayout(g)
        self.cb_model = QComboBox(); self.cb_model.currentIndexChanged.connect(self._on_model_user)
        self.cb_model.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon); self.cb_model.setMinimumContentsLength(16)
        self.btn_refresh = mkbtn("⟳", self.refresh_models, "Обновить список моделей с OpenRouter", w=36)
        self.btn_voice = mkbtn("", self.open_voice_picker, "Открыть каталог голосов (фильтры, превью, ручной ввод ID)", "voicebtn")
        self.btn_voice.setMinimumHeight(52); self.btn_voice.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.btn_en = mkbtn("▶ EN (Free)", self.preview_en, "Бесплатный англ. сэмпл голоса (Google Cloud, без VPN)")
        self.btn_ru = mkbtn("▶ RU (Кэш)", self.preview_ru, "Русский сэмпл: генерируется 1 раз через API и навсегда кэшируется")
        self.ru_dot = label("●", "rudot")
        gl.addWidget(label("Модель:"), 0, 0); gl.addWidget(self.cb_model, 0, 1, 1, 3); gl.addWidget(self.btn_refresh, 0, 4)
        gl.addWidget(label("Голос:"), 1, 0); gl.addWidget(self.btn_voice, 1, 1, 1, 4)
        gl.addLayout(hbox(1, self.btn_en, self.btn_ru, self.ru_dot), 2, 1, 1, 4)
        self.cb_profile, self.cb_char = QComboBox(), QComboBox()
        for cb in (self.cb_profile, self.cb_char):
            cb.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon); cb.setMinimumContentsLength(8)
        self.cb_profile.setToolTip("Профиль (проект) с персонажами — создаётся в окне выбора голоса")
        self.cb_char.setToolTip("Персонаж: выбирает его голос и сохранённые настройки")
        self.cb_profile.currentTextChanged.connect(self._on_profile_main); self.cb_char.activated.connect(self._on_char_main)
        gl.addWidget(label("Персонаж:"), 3, 0); gl.addLayout(hbox((self.cb_profile, 2), (self.cb_char, 3)), 3, 1, 1, 4)
        gl.setColumnStretch(1, 1); L.addWidget(g)
        # 3. настройки ElevenLabs
        self.grp_el = QGroupBox("Настройки ElevenLabs"); gv = QVBoxLayout(self.grp_el)
        self.el_box = QWidget(); eg = QGridLayout(self.el_box); eg.setContentsMargins(0, 0, 0, 0)
        self.sl_stab = self._slider(eg, 0, "Stability", 0, 1, 0.95, "Выше = монотоннее, ниже = эмоциональнее")
        eg.addWidget(label("Выше = монотоннее, ниже = эмоциональнее", "hint"), 1, 1, 1, 2)
        self.sl_sim = self._slider(eg, 2, "Similarity Boost", 0, 1, 0.75, "Насколько точно держаться исходного тембра")
        self.sl_style = self._slider(eg, 3, "Style Exaggeration", 0, 1, 0.0, "Усиление стиля/эмоций (повышает задержку)")
        self.cb_lang = QComboBox(); self.cb_lang.addItems(["ru", "en", "auto"])
        self.ed_seed = QLineEdit(); self.ed_seed.setPlaceholderText("необязательно")
        self.ed_seed.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,10}"), self))
        eg.addWidget(label("Язык:"), 4, 0); eg.addWidget(self.cb_lang, 4, 1, 1, 2)
        eg.addWidget(label("Seed:"), 5, 0)
        eg.addLayout(hbox((self.ed_seed, 1), mkbtn("🎲", lambda: self.ed_seed.setText(str(random.randint(0, 4294967295))), "Случайный seed", w=36),
                          mkbtn("Взять Seed из последнего дубля", self.seed_from_last)), 5, 1, 1, 2)
        self.chk_ext = QCheckBox("Отправлять расширенные параметры ElevenLabs (Stability/Seed)"); self.chk_ext.setChecked(True)
        eg.addWidget(self.chk_ext, 6, 0, 1, 3)
        self.btn_ctx = QToolButton(); self.btn_ctx.setObjectName("ctxbtn"); self.btn_ctx.setText("Контекст соседних фраз (для бесшовной склейки)")
        self.btn_ctx.setCheckable(True); self.btn_ctx.setArrowType(Qt.ArrowType.RightArrow)
        self.btn_ctx.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.ed_prev, self.ed_next = QPlainTextEdit(), QPlainTextEdit()
        for e, ph in ((self.ed_prev, "Previous Text — текст, который звучит ДО этой фразы"), (self.ed_next, "Next Text — текст, который звучит ПОСЛЕ")):
            e.setPlaceholderText(ph); e.setFixedHeight(56)
        self.ctx_box = QWidget(); self.ctx_box.setLayout(vbox(label("Previous Text:"), self.ed_prev, label("Next Text:"), self.ed_next, s=4))
        self.ctx_box.hide()
        self.btn_ctx.toggled.connect(lambda on: (self.ctx_box.setVisible(on), self.btn_ctx.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)))
        eg.addWidget(self.btn_ctx, 7, 0, 1, 3); eg.addWidget(self.ctx_box, 8, 0, 1, 3); eg.setColumnStretch(1, 1)
        sg = QGridLayout(); sg.setContentsMargins(0, 0, 0, 0)
        self.sl_speed = self._slider(sg, 0, "Speed", 0.5, 2.0, 1.0, "Скорость речи (0.50 – 2.00)"); sg.setColumnStretch(1, 1)
        gv.addWidget(self.el_box); gv.addLayout(sg); L.addWidget(self.grp_el)
        # 4. теги + текст
        g = QGroupBox("Текст для озвучки"); tv = QVBoxLayout(g)
        self.tag_grid = QGridLayout(); self.tag_grid.setSpacing(4)
        self.base_tag_btns = [self._tag_btn(t) for t in QUICK_TAGS]; self._relayout_tags()
        self.ed_custom = QLineEdit(); self.ed_custom.setPlaceholderText("свой тег, напр. sarcastic"); self.ed_custom.returnPressed.connect(self.add_custom_tag)
        tv.addLayout(hbox(mkbtn("Поставить ударение  ́ ", self.insert_accent, "Вставить комбинируемый акут U+0301 в позицию курсора (ставьте курсор сразу после ударной гласной)", "accentbtn"),
                          1, label("Свой тег:"), self.ed_custom, mkbtn("＋ тег", self.add_custom_tag, "Добавить кнопку с тегом (ПКМ по кнопке — удалить)")))
        tv.addLayout(self.tag_grid)
        self.txt = TextEdit(); self.txt.setMinimumHeight(230); self.txt.setPlaceholderText("[monotone, cold] Введите текст для озвучки…")
        self.txt.textChanged.connect(self.update_cost); self.txt.submit.connect(self.generate)
        self.lbl_cost = label("", "cost"); tv.addWidget(self.txt, 1); tv.addWidget(self.lbl_cost); L.addWidget(g, 1)
        self.btn_gen = mkbtn("🎙  СГЕНЕРИРОВАТЬ ОЗВУЧКУ  (Ctrl + Enter)", self.generate, obj="gen"); L.addWidget(self.btn_gen)
        return w

    def _build_right(self):
        w = QWidget(); L = QVBoxLayout(w); L.setContentsMargins(6, 6, 10, 10); L.setSpacing(8)
        self.player = AudioPlayer(self.status); L.addWidget(self.player)
        L.addLayout(hbox(label("Лента дублей  ·  временный кэш (7 дней), новые сверху", "section"), 1,
                         mkbtn("🧹 Очистить старый кэш", self.manual_cleanup, "Удалить дубли старше 7 дней (превью голосов не трогаются)")))
        self.list_w = QWidget(); self.list_l = QVBoxLayout(self.list_w); self.list_l.setContentsMargins(0, 0, 4, 0); self.list_l.setSpacing(8)
        self.list_l.addStretch(1)
        self.list_scroll = QScrollArea(); self.list_scroll.setWidgetResizable(True); self.list_scroll.setWidget(self.list_w)
        L.addWidget(self.list_scroll, 1); return w

    def _slider(self, grid, row, title, lo, hi, val, tip=""):
        s = QSlider(Qt.Orientation.Horizontal); s.setRange(round(lo * 100), round(hi * 100)); s.setValue(round(val * 100))
        v = label(f"{val:.2f}", "sval"); v.setFixedWidth(42); v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        s.valueChanged.connect(lambda x: v.setText(f"{x / 100:.2f}")); t = label(title, tip=tip); s.setToolTip(tip)
        grid.addWidget(t, row, 0); grid.addWidget(s, row, 1); grid.addWidget(v, row, 2); return s

    def _tag_btn(self, tag, custom=False):
        b = mkbtn(tag, lambda: self.insert_tag(tag), "ПКМ — удалить тег" if custom else "Вставить тег в позицию курсора", "tag")
        if custom:
            b.setProperty("custom", True); b.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            b.customContextMenuRequested.connect(lambda _p: self.remove_custom_tag(tag))
        return b

    def _relayout_tags(self):
        while self.tag_grid.count():
            wd = self.tag_grid.takeAt(0).widget()
            if wd is not None and wd.property("custom"): wd.deleteLater()
        for i, b in enumerate(self.base_tag_btns + [self._tag_btn(t, True) for t in self.custom_tags]):
            self.tag_grid.addWidget(b, i // 4, i % 4)

    # ---------- config
    def _apply_config(self):
        c = self.cfg
        self.ed_key.setText(c.get("api_key", "") or os.environ.get("OPENROUTER_API_KEY", "")); self.ed_folder.setText(c.get("export_folder", ""))
        for s, k in ((self.sl_stab, "stability"), (self.sl_sim, "similarity"), (self.sl_style, "style"), (self.sl_speed, "speed")):
            if isinstance(c.get(k), (int, float)): s.setValue(round(c[k] * 100))
        i = self.cb_lang.findText(c.get("language", "ru")); self.cb_lang.setCurrentIndex(max(i, 0))
        self.ed_seed.setText(str(c.get("seed", "") or "")); self.chk_ext.setChecked(c.get("extended", True))
        self.chk_norm.setChecked(bool(c.get("normalize", True)) and AUDIO_OK); self.cb_norm.setEnabled(self.chk_norm.isChecked())
        i = self.cb_norm.findData(c.get("norm_target", -16.0)); self.cb_norm.setCurrentIndex(i if i >= 0 else 1)
        self.player.autoplay.setChecked(c.get("autoplay", True))
        try:
            if c.get("geometry"): self.restoreGeometry(QByteArray.fromHex(c["geometry"].encode()))
            if c.get("splitter"): self.splitter.restoreState(QByteArray.fromHex(c["splitter"].encode()))
        except Exception: pass

    def save_cfg(self):
        if self._loading: return
        self.cfg.update(normalize=self.chk_norm.isChecked(), norm_target=self.cb_norm.currentData(), profiles=self.profiles,
                        active_profile=self.active_profile, character=self.cur_character)
        self.cfg.update(api_key=self.ed_key.text().strip(), export_folder=self.ed_folder.text().strip(), model=self.wanted_model,
                        voice=self.voice(), custom_voices=self.custom_voices, theme=CURRENT_THEME, language=self.cb_lang.currentText(), seed=self.ed_seed.text().strip(),
                        extended=self.chk_ext.isChecked(), autoplay=self.player.autoplay.isChecked(), custom_tags=self.custom_tags,
                        geometry=bytes(self.saveGeometry().toHex()).decode(), splitter=bytes(self.splitter.saveState().toHex()).decode(),
                        **{k: s.value() / 100 for k, s in (("stability", self.sl_stab), ("similarity", self.sl_sim), ("style", self.sl_style), ("speed", self.sl_speed))})
        try: save_json(CONFIG_PATH, self.cfg)
        except OSError as e: self.status(f"Не удалось сохранить config.json: {e}")

    def save_index(self):
        try: save_json(INDEX_PATH, self.takes)
        except OSError as e: self.status(f"Не удалось сохранить takes_index.json: {e}")

    def current_params(self):
        return {"stability": self.sl_stab.value() / 100, "similarity": self.sl_sim.value() / 100, "style": self.sl_style.value() / 100,
                "speed": self.sl_speed.value() / 100, "language": self.cb_lang.currentText(), "seed": self.ed_seed.text().strip(),
                "previous_text": self.ed_prev.toPlainText().strip(), "next_text": self.ed_next.toPlainText().strip(), "extended": self.chk_ext.isChecked()}

    # ---------- infra
    def status(self, msg, ms=9000): self.statusBar().showMessage(msg, ms)
    def _start(self, w, ok=None, fail=None):
        if ok: w.ok.connect(ok)
        if fail: w.fail.connect(fail)
        self.workers.add(w); w.finished.connect(lambda: self.workers.discard(w)); w.start(); return w
    def model(self): return self.cb_model.currentData() or ""
    def voice(self): return self.cur_voice.strip()
    def ru_path(self, model, voice): return PREVIEW_DIR / f"ru_{safe_id(model)}_{safe_id(voice)}.mp3"

    # ---------- models / voices
    def refresh_models(self):
        self.btn_refresh.setEnabled(False); self.status("Загрузка списка аудио-моделей OpenRouter…")
        self._start(ModelsWorker(self.ed_key.text().strip()), self._on_models, self._on_models_fail)

    def _on_models(self, data):
        self.btn_refresh.setEnabled(True); models = {m["id"]: m for m in data if m.get("id")}
        if not models: return self.status("OpenRouter вернул пустой список моделей — используется встроенный список")
        self._fill_models(models); self.status(f"Загружено аудио-моделей: {len(models)}")

    def _on_models_fail(self, msg):
        self.btn_refresh.setEnabled(True); self.status(f"Список моделей не загружен ({msg.splitlines()[0]}) — используется встроенный", 15000)

    def _fill_models(self, models):
        self.models = models
        order = [m for m in PRIORITY_MODELS if m in models] + sorted(m for m in models if m not in PRIORITY_MODELS)
        self.cb_model.blockSignals(True); self.cb_model.clear()
        for mid in order:
            nm = str(models[mid].get("name") or mid); star = "★ " if mid in PRIORITY_MODELS else ""
            self.cb_model.addItem(f"{star}{nm}   [{mid}]" if nm != mid else f"{star}{mid}", mid)
        i = self.cb_model.findData(self.wanted_model)
        self.cb_model.setCurrentIndex(i if i >= 0 else 0); self.cb_model.blockSignals(False); self.on_model_changed()

    def _on_model_user(self): self.wanted_model = self.model(); self.on_model_changed()

    def on_model_changed(self):
        mid = self.model(); self.voice_list = self.voices_for_model(mid); want = self.wanted_voice
        match = next((v for v in self.voice_list if v.lower() == want.lower()), None)
        if match: self.cur_voice = match
        elif want and want in self.custom_voices: self.cur_voice = want
        else: self.cur_voice = next((v for v in self.voice_list if v.lower() == "george"), self.voice_list[0] if self.voice_list else want)
        is_el = mid.startswith("elevenlabs/"); self.el_box.setEnabled(is_el)
        self.grp_el.setTitle("Настройки ElevenLabs" if is_el else "Настройки ElevenLabs (недоступны для этой модели — активна только скорость)")
        self.update_cost(); self.update_voice_ui()

    def voices_for_model(self, mid):
        """Полный список supported_voices из API; для elevenlabs/* — объединение с VOICE_DB. Ничего не отбрасывается."""
        api = norm_voices(self.models.get(mid, {}).get("supported_voices"))
        if not mid.startswith("elevenlabs/"): return api or list(DEFAULT_VOICES)
        out, seen = [], set()
        for v in api + list(VOICE_DB):
            if v.lower() not in seen: seen.add(v.lower()); out.append(v)
        return out

    def set_voice(self, v):
        v = str(v).strip()
        if v: self.cur_voice = self.wanted_voice = v
        self.update_voice_ui()

    def update_voice_ui(self):
        v, mid = self.voice(), self.model(); m = voice_meta(v, mid); ico, _, gname = GENDERS.get(m["gender"], GENDERS["unknown"])
        sub = f"{gname} · {m['age']} · {m['accent']}" if m["gender"] != "unknown" else "Другие / API"
        ch = self.get_character(self.cur_character)
        if self.cur_character and (not ch or ch["voice"] != v): self.cur_character = ""; ch = None
        head = f"🎭 {self.cur_character}   ·   " if ch else ""
        self.btn_voice.setText(f"{head}{ico}   {v or '—'}    ·    {sub}      ▾ выбрать\n{m['desc']}")
        url = self.en_url(v); self.btn_en.setEnabled(bool(url))
        self.btn_en.setToolTip("Бесплатный англ. сэмпл голоса (Google Cloud, без VPN)" if url else "Для этого голоса нет бесплатного сэмпла — используйте ▶ RU (Кэш)")
        self.update_ru_dot(); self.refresh_profile_ui()

    def open_voice_picker(self):
        voices = self.voice_list + [c for c in self.custom_voices if c not in self.voice_list]
        dlg = VoicePickerDialog(self, voices, self.voice(), self.model())
        if dlg.exec() and dlg.selected:
            if dlg.selected_char: self.apply_character(dlg.selected_char)
            else:
                v = dlg.selected
                if v not in self.voice_list and v not in self.custom_voices: self.custom_voices.append(v)
                self.cur_character = ""; self.set_voice(v); self.save_cfg(); self.status(f"Голос: {v}")
        dlg.deleteLater()

    # ---------- профили и персонажи
    def get_character(self, name):
        return next((c for c in self.profiles.get(self.active_profile, []) if c["name"] == name), None) if name else None

    def character_settings(self):
        p = self.current_params(); return {k: p[k] for k in ("stability", "similarity", "style", "speed", "language")}

    def apply_character(self, ch):
        v = ch["voice"]
        if v not in self.voice_list and v not in self.custom_voices: self.custom_voices.append(v)
        s = ch.get("settings") or {}
        for sl, k in ((self.sl_stab, "stability"), (self.sl_sim, "similarity"), (self.sl_style, "style"), (self.sl_speed, "speed")):
            if isinstance(s.get(k), (int, float)): sl.setValue(round(s[k] * 100))
        if s.get("language"): self.cb_lang.setCurrentIndex(max(0, self.cb_lang.findText(s["language"])))
        self.cur_character = ch["name"]; self.set_voice(v); self.save_cfg()
        self.status(f"Персонаж «{ch['name']}» → голос {v}" + (" + сохранённые настройки" if s else ""))

    def refresh_profile_ui(self):
        if not hasattr(self, "cb_char"): return
        for cb in (self.cb_profile, self.cb_char): cb.blockSignals(True)
        self.cb_profile.clear()
        if self.profiles: self.cb_profile.addItems(list(self.profiles)); self.cb_profile.setCurrentText(self.active_profile)
        else: self.cb_profile.addItem("— нет профилей —")
        self.cb_profile.setEnabled(bool(self.profiles)); chars = self.profiles.get(self.active_profile, [])
        self.cb_char.clear(); self.cb_char.addItem("— без персонажа —" if chars else "добавьте в окне «выбрать» → 🎭", "")
        for c in chars: self.cb_char.addItem(f"🎭 {c['name']}  ·  {c['voice']}", c["name"])
        self.cb_char.setCurrentIndex(max(0, self.cb_char.findData(self.cur_character)) if self.cur_character else 0)
        self.cb_char.setEnabled(bool(chars))
        for cb in (self.cb_profile, self.cb_char): cb.blockSignals(False)

    def _on_profile_main(self, name):
        if name in self.profiles and name != self.active_profile:
            self.active_profile, self.cur_character = name, ""; self.refresh_profile_ui(); self.update_voice_ui(); self.save_cfg()

    def _on_char_main(self, i):
        ch = self.get_character(self.cb_char.itemData(i))
        if ch: self.apply_character(ch)
        else: self.cur_character = ""; self.update_voice_ui()

    def update_ru_dot(self):
        ok = self.ru_path(self.model(), self.voice()).is_file()
        self.ru_dot.setStyleSheet(f"color: {th()['ok'] if ok else th()['faint']}; font-size: 16pt;")
        self.ru_dot.setToolTip("RU-превью уже в кэше — проигрывается бесплатно" if ok else "RU-превью ещё не создано (будет сгенерировано через API)")

    def update_cost(self):
        n, mid = len(self.txt.toPlainText()), self.model(); rate = 40 if "turbo" in mid else 80
        note = "" if mid.startswith("elevenlabs/") else ", оценка"
        self.lbl_cost.setText(f"Символов: <b>{n}</b> &nbsp;·&nbsp; Стоимость: <b style='color:{th()['accent']}'>~${n * rate / 1e6:.4f}</b> &nbsp;(${rate}/1M симв.{note})")

    # ---------- previews
    def fetch_en_previews(self):
        self.en_state = "loading"
        self._start(ElVoicesWorker(), self._on_el_voices, self._on_el_fail)
    def _on_el_voices(self, m): self.en_previews, self.en_state = m, "ok"
    def _on_el_fail(self, _msg): self.en_state = "failed"  # api.elevenlabs.io часто недоступен без VPN — хватает VOICE_DB

    def en_url(self, voice, model=None):
        if not (model or self.model()).startswith("elevenlabs/"): return ""
        v = str(voice).lower(); return VOICE_DB.get(v, {}).get("url") or self.en_previews.get(v, "")

    def preview_en(self, voice=None, btn=None):
        v = voice or self.voice(); btn = btn or self.btn_en; path = PREVIEW_DIR / f"en_{safe_id(v.lower())}.mp3"
        if path.is_file(): return self.player.play_file(path, f"EN-превью · {v}")
        url = self.en_url(v)
        if not url: return self.status(f"Для голоса «{v}» нет бесплатного EN-превью — используйте ▶ RU (Кэш)")
        set_busy(btn, True)
        def done(p): set_busy(btn, False); self.update_voice_ui(); self.player.play_file(p, f"EN-превью · {v}")
        def fail(m):
            set_busy(btn, False); self.update_voice_ui()
            QMessageBox.warning(QApplication.activeWindow() or self, "EN-превью", f"Не удалось скачать сэмпл:\n{m}")
        self._start(DownloadWorker(url, path), done, fail)

    def preview_ru(self, voice=None, btn=None, on_done=None):
        model, voice, btn = self.model(), voice or self.voice(), btn or self.btn_ru; path = self.ru_path(model, voice)
        if not voice: return
        if path.is_file(): self.status("RU-превью из кэша — бесплатно"); return self.player.play_file(path, f"RU-превью · {voice} · {model}")
        key = self.ed_key.text().strip()
        if not key: return QMessageBox.warning(QApplication.activeWindow() or self, "Нет API-ключа", "Введите API-ключ OpenRouter, чтобы сгенерировать RU-превью.")
        p = {**self.current_params(), "seed": "", "previous_text": "", "next_text": "", "language": "ru"}
        set_busy(btn, True); self.status(f"Генерация RU-превью голоса {voice}…")
        def done(pth, note):
            set_busy(btn, False); self.update_ru_dot(); self.status(note or "RU-превью сохранено в voice_previews/ навсегда")
            if on_done: on_done()
            self.player.play_file(pth, f"RU-превью · {voice} · {model}")
        def fail(m): set_busy(btn, False); QMessageBox.critical(QApplication.activeWindow() or self, "Ошибка RU-превью", m)
        self._start(TTSWorker(key, build_payload(model, RU_PREVIEW_TEXT, voice, p, p["extended"]), path), done, fail)

    # ---------- text tools
    def insert_tag(self, tag):
        c = self.txt.textCursor(); doc = self.txt.toPlainText(); pos = c.selectionStart()
        pre = " " if pos > 0 and doc[pos - 1] not in " \n\t" else ""
        c.insertText(f"{pre}{tag} "); self.txt.setTextCursor(c); self.txt.setFocus()

    def insert_accent(self):
        c = self.txt.textCursor(); doc = self.txt.toPlainText(); pos = c.position()
        if pos == 0 or doc[pos - 1] not in VOWELS: self.status("Подсказка: ставьте курсор сразу ПОСЛЕ ударной гласной", 5000)
        c.insertText("\u0301"); self.txt.setTextCursor(c); self.txt.setFocus()

    def add_custom_tag(self):
        t = self.ed_custom.text().strip().strip("[]").strip()
        if not t: return
        tag = f"[{t}]"
        if tag not in self.custom_tags and tag not in QUICK_TAGS: self.custom_tags.append(tag); self._relayout_tags(); self.save_cfg()
        self.ed_custom.clear()

    def remove_custom_tag(self, tag):
        if tag in self.custom_tags: self.custom_tags.remove(tag); QTimer.singleShot(0, self._relayout_tags); self.save_cfg()

    def seed_from_last(self):
        for t in sorted(self.takes, key=lambda t: t.get("created", 0), reverse=True):
            s = str(t.get("params", {}).get("seed", "")).strip()
            if s: self.ed_seed.setText(s); return self.status(f"Seed {s} взят из дубля от {time.strftime('%d.%m %H:%M:%S', time.localtime(t['created']))}")
        QMessageBox.information(self, "Seed", "Ни у одного дубля в кэше seed не задавался.\nElevenLabs не возвращает случайный seed — "
                                "нажмите 🎲 перед генерацией, чтобы зафиксировать его и потом повторить удачный дубль.")

    # ---------- generation
    def generate(self):
        if self.gen_timer.isActive(): return
        key, model, voice, text = self.ed_key.text().strip(), self.model(), self.voice(), self.txt.toPlainText().strip()
        if not key: self.ed_key.setFocus(); return QMessageBox.warning(self, "Нет API-ключа", "Введите API-ключ OpenRouter (sk-or-…).")
        if not text: self.txt.setFocus(); return QMessageBox.warning(self, "Нет текста", "Введите текст для озвучки.")
        if not model or not voice: return QMessageBox.warning(self, "Модель / голос", "Выберите модель и голос.")
        p = self.current_params(); out = CACHE_DIR / f"take_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.mp3"
        meta = {"id": uuid.uuid4().hex, "created": time.time(), "file": out.name, "text": text, "model": model, "voice": voice,
                "params": p, "saved": False, "exported_name": "", "exported_path": "",
                "character": self.cur_character if self.get_character(self.cur_character) else ""}
        self.gen_started = time.time(); self.gen_timer.start(); self._tick(); self.btn_gen.setEnabled(False)
        self.status(f"Генерация: {model} · {voice} · {len(text)} симв.", 0); self.save_cfg()
        self._start(TTSWorker(key, build_payload(model, text, voice, p, p["extended"]), out),
                    lambda _p, note: self._on_take_ready(meta, note), self._on_gen_fail)

    def _tick(self): self.btn_gen.setText(f"⏳  ГЕНЕРАЦИЯ…  {int(time.time() - self.gen_started)} с")
    def _gen_reset(self): self.gen_timer.stop(); self.btn_gen.setEnabled(True); self.btn_gen.setText("🎙  СГЕНЕРИРОВАТЬ ОЗВУЧКУ  (Ctrl + Enter)")
    def _on_gen_fail(self, msg): self._gen_reset(); self.status("Ошибка генерации"); QMessageBox.critical(self, "Ошибка генерации", msg)

    def _on_take_ready(self, meta, note):
        self._gen_reset()
        if note: meta["params"]["fallback"] = True
        self.takes.append(meta); self.save_index(); card = self.add_card(meta); self.update_cache_status()
        self.status(note or f"Готово за {time.time() - self.gen_started:.1f} с → {meta['file']}", 15000)
        self.list_scroll.verticalScrollBar().setValue(0); card.ed_name.setFocus(); card.ed_name.selectAll()
        if self.player.autoplay.isChecked(): self.play_take(meta)

    # ---------- takes
    def add_card(self, take):
        c = TakeCard(take); c.play.connect(self.play_take); c.load.connect(self.load_take); c.save.connect(self.save_take)
        c.delete.connect(self.delete_take); self.list_l.insertWidget(0, c); self.cards[take["id"]] = c; return c

    def play_take(self, t): self.player.play_file(CACHE_DIR / t["file"], f"{t['voice']} · {t['text'][:70]}")

    def load_take(self, t):
        p = t.get("params", {}); self.txt.setPlainText(t.get("text", "")); self.wanted_voice = t.get("voice", "")
        if self.cb_model.findData(t["model"]) < 0: self.cb_model.addItem(t["model"], t["model"])
        self.cb_model.setCurrentIndex(self.cb_model.findData(t["model"]))
        if t["voice"] not in self.voice_list and t["voice"] not in self.custom_voices: self.custom_voices.append(t["voice"])
        ch = self.get_character(t.get("character"))
        self.cur_character = ch["name"] if ch and ch["voice"] == t["voice"] else ""; self.set_voice(t["voice"])
        for s, k, d in ((self.sl_stab, "stability", .95), (self.sl_sim, "similarity", .75), (self.sl_style, "style", 0), (self.sl_speed, "speed", 1)):
            s.setValue(round(float(p.get(k, d)) * 100))
        self.cb_lang.setCurrentIndex(max(0, self.cb_lang.findText(p.get("language", "ru")))); self.ed_seed.setText(str(p.get("seed", "")))
        self.ed_prev.setPlainText(p.get("previous_text", "")); self.ed_next.setPlainText(p.get("next_text", ""))
        self.chk_ext.setChecked(p.get("extended", True))
        if p.get("previous_text") or p.get("next_text"): self.btn_ctx.setChecked(True)
        self.txt.setFocus(); self.status("Текст и настройки дубля загружены в редактор")

    def choose_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Папка сохранения для монтажа", self.ed_folder.text() or str(Path.home()))
        if d: self.ed_folder.setText(str(Path(d))); self.save_cfg(); self.status(f"Папка сохранения: {d}")
        return bool(d)

    def open_folder(self):
        d = self.ed_folder.text().strip()
        if not d or not Path(d).is_dir(): return QMessageBox.information(self, "Папка", "Папка сохранения не выбрана или не существует.")
        if sys.platform == "win32": os.startfile(d)
        else: QDesktopServices.openUrl(QUrl.fromLocalFile(d))

    def save_take(self, card):
        folder = self.ed_folder.text().strip()
        if not folder or not Path(folder).is_dir():
            if not self.choose_folder(): return
            folder = self.ed_folder.text().strip()
        src = CACHE_DIR / card.take["file"]
        if not src.is_file(): return QMessageBox.critical(self, "Ошибка", "Файл дубля пропал из кэша.")
        name = sanitize_filename(card.ed_name.text()) or auto_name(card.take.get("text", "")); card.ed_name.setText(name)
        dst = unique_path(Path(folder), name); norm, note = None, ""
        if self.chk_norm.isChecked() and AUDIO_OK:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try: norm = normalize_mp3(src, dst, self.cb_norm.currentData())
            except Exception as e: note = f"   ⚠ нормализация не удалась ({type(e).__name__}: {e}) — сохранён оригинал"
            finally: QApplication.restoreOverrideCursor()
        if norm is None:
            try: shutil.copy2(src, dst)
            except OSError as e: return QMessageBox.critical(self, "Ошибка сохранения", f"Не удалось скопировать файл:\n{e}")
        card.take.update(saved=True, exported_name=dst.name, exported_path=str(dst),
                         export_lufs=round(norm["after"], 1) if norm else None)
        self.save_index(); card.mark_saved()
        if norm: note = f"   ·   громкость {norm['before']:.1f} → {norm['after']:.1f} LUFS" + ("  (лимитер пиков)" if norm["limited"] else "")
        self.status(f"✓ Сохранено: {dst}" + ("   (имя занято — добавлен суффикс версии)" if dst.stem != name else "") + note, 15000)

    def delete_take(self, card):
        t = card.take; extra = "\n\nКопия в папке проекта НЕ удаляется." if t.get("saved") else ""
        if QMessageBox.question(self, "Удалить дубль", f"Удалить дубль из кэша?{extra}") != QMessageBox.StandardButton.Yes: return
        try: (CACHE_DIR / t["file"]).unlink(missing_ok=True)
        except OSError as e: return QMessageBox.critical(self, "Ошибка", f"Не удалось удалить файл:\n{e}")
        if t in self.takes: self.takes.remove(t)
        self.cards.pop(t["id"], None); card.deleteLater(); self.save_index(); self.update_cache_status(); self.status("Дубль удалён из кэша")

    # ---------- cache
    def cleanup_cache(self):
        now, removed, keep = time.time(), 0, []
        for t in self.takes:
            f = CACHE_DIR / t["file"]
            if not f.is_file(): continue
            if now - float(t.get("created", 0)) > MAX_AGE:
                try: f.unlink(); removed += 1; continue
                except OSError: pass
            keep.append(t)
        known = {t["file"] for t in keep}
        for f in CACHE_DIR.glob("take_*.mp3*"):
            try:
                if f.name not in known and now - f.stat().st_mtime > MAX_AGE: f.unlink(); removed += 1
            except OSError: pass
        self.takes = keep; self.save_index(); return removed

    def manual_cleanup(self):
        removed = self.cleanup_cache(); ids = {t["id"] for t in self.takes}
        for tid in [k for k in self.cards if k not in ids]: self.cards.pop(tid).deleteLater()
        self.update_cache_status(); QMessageBox.information(self, "Очистка кэша", f"Удалено дублей старше 7 дней: {removed}")

    def update_cache_status(self):
        files = list(CACHE_DIR.glob("take_*.mp3")); size = sum(f.stat().st_size for f in files if f.is_file())
        self.cache_lbl.setText(f"🗄 Кэш дублей: {len(files)} файлов · {human_size(size)}  ·  автоочистка > 7 дней ")

    def closeEvent(self, e):
        self.save_cfg(); self.player.release()
        for w in list(self.workers):
            if not w.wait(1500): w.terminate(); w.wait(500)
        e.accept()
        if self.restart_exe:  # RESET_ENVIRONMENT: новая версия распаковывается в свою папку, а не наследует папку старой
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            subprocess.Popen([str(self.restart_exe)], cwd=str(self.restart_exe.parent), creationflags=flags,
                             env={**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"})

# ---------------------------------------------------------------- theme / entry
QSS = Template("""
* { font-family: 'Segoe UI Variable Text', 'Segoe UI', 'Inter', sans-serif; font-size: 10pt; color: $text; }
QMainWindow, QDialog { background: $bg; }
QLabel, QCheckBox { background: transparent; }
QFrame#topbar { background: $panel; border: none; border-bottom: 1px solid $border; }
QLabel#logo { font-size: 14pt; font-weight: 700; } QLabel#logosub { color: $dim; font-size: 9pt; }
QLabel#logoicon { font-size: 18pt; background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 $accent2, stop:1 $accent);
    border-radius: ${r2}px; min-width: 40px; max-width: 40px; min-height: 40px; max-height: 40px; qproperty-alignment: AlignCenter; }
QGroupBox { background: $panel; border: 1px solid $border; border-radius: ${r2}px; margin-top: 18px; padding: 14px 10px 10px 10px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: $accent; font-size: 10.5pt; }
QLineEdit, QPlainTextEdit, QComboBox { background: $input; border: 1px solid $border; border-radius: ${r}px; padding: 6px 8px;
    selection-background-color: $accent; selection-color: $on_accent; }
QLineEdit:hover, QPlainTextEdit:hover, QComboBox:hover { border-color: $border_hi; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: $accent; }
QLineEdit:disabled, QComboBox:disabled, QPlainTextEdit:disabled { color: $faint; background: $panel; }
QPlainTextEdit { font-size: 11pt; }
QComboBox QAbstractItemView { background: $card; border: 1px solid $border; padding: 4px; outline: none;
    selection-background-color: $accent; selection-color: $on_accent; }
QPushButton, QToolButton { background: $raised; border: 1px solid $border; border-radius: ${r}px; padding: 6px 12px; }
QPushButton:hover, QToolButton:hover { background: $hover; border-color: $accent; }
QPushButton:pressed, QToolButton:checked { background: $soft; color: $soft_text; }
QPushButton:disabled { color: $faint; background: $panel; border-color: $border; }
QPushButton#gen { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 $accent2, stop:1 $accent); color: $on_accent;
    font-size: 13pt; font-weight: 700; padding: 15px; border: none; border-radius: ${r2}px; }
QPushButton#gen:hover { border: 2px solid $text; padding: 13px; }
QPushButton#gen:disabled { background: $soft; color: $soft_text; }
QPushButton#accentbtn, QPushButton#pickbtn { background: $soft; border: 1px solid $accent; color: $soft_text; font-weight: 700; }
QPushButton#accentbtn:hover, QPushButton#pickbtn:hover { background: $accent; color: $on_accent; }
QPushButton#tag { padding: 4px 8px; font-size: 9pt; background: $card; border-radius: ${rp}px; font-family: 'Cascadia Mono', Consolas, monospace; }
QPushButton#tag:hover { background: $soft; color: $soft_text; }
QPushButton#playbtn { background: $accent; color: $on_accent; border: none; border-radius: 22px; font-size: 13pt; padding: 0; }
QPushButton#playbtn:hover { background: $accent2; }
QPushButton#roundbtn { border-radius: 17px; padding: 0; }
QToolButton#ctxbtn { border: none; background: transparent; color: $dim; padding: 4px 0; }
QPushButton#voicebtn { text-align: left; padding: 9px 14px; background: $input; font-size: 10.5pt; border-radius: ${r2}px; }
QPushButton#voicebtn:hover { background: $hover; }
QFrame#vcard, QFrame#card { background: $card; border: 1px solid $border; border-radius: ${r2}px; }
QFrame#vcard:hover, QFrame#card:hover { border-color: $border_hi; }
QFrame#vcard[current="true"] { border: 2px solid $accent; }
QFrame#player { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 $panel, stop:1 $card); border: 1px solid $border; border-radius: ${r2}px; }
QFrame#sidebar { background: $panel; border: 1px solid $border; border-radius: ${r2}px; }
QLabel#sidehead { color: $dim; font-size: 8.5pt; font-weight: 700; }
QListWidget { background: $input; border: 1px solid $border; border-radius: ${r}px; padding: 4px; outline: none; }
QListWidget::item { padding: 7px 6px; border-radius: ${r}px; margin: 1px 0; }
QListWidget::item:hover { background: $hover; } QListWidget::item:selected { background: $soft; color: $soft_text; }
QPushButton#filt { padding: 5px 14px; border-radius: ${rp}px; }
QPushButton#filt:checked { background: $accent; color: $on_accent; border-color: $accent; font-weight: 600; }
QLabel#chip { background: $raised; color: $dim; border-radius: ${rp}px; padding: 2px 9px; font-size: 9pt; }
QLabel#chipacc { background: $soft; color: $soft_text; border-radius: ${rp}px; padding: 2px 9px; font-size: 9pt; font-weight: 600; }
QLabel#vdesc { color: $dim; }
QLabel#ptitle { font-weight: 600; font-size: 10.5pt; } QLabel#ptime { font-family: 'Cascadia Mono', Consolas, monospace; color: $accent; }
QLabel#meta { color: $dim; font-size: 9pt; } QLabel#taketext { padding: 6px 8px; background: $input; border-radius: ${r}px; }
QLabel#saved { color: $ok; font-weight: 600; } QLabel#hint { color: $faint; font-size: 8.5pt; }
QLabel#section { color: $accent; font-weight: 600; font-size: 10.5pt; } QLabel#sval { font-family: 'Cascadia Mono', Consolas, monospace; color: $accent; }
QLabel#cost, QLabel#cachelbl { color: $dim; }
QSlider::groove:horizontal { height: 4px; background: $border; border-radius: 2px; }
QSlider::sub-page:horizontal { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 $accent2, stop:1 $accent); border-radius: 2px; }
QSlider::sub-page:horizontal:disabled { background: $faint; }
QSlider::handle:horizontal { background: $panel; border: 3px solid $accent; width: 10px; height: 10px; margin: -6px 0; border-radius: 8px; }
QSlider::handle:horizontal:hover { background: $accent; }
QSlider::handle:horizontal:disabled { border-color: $faint; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 2px; } QScrollBar::handle:vertical { background: $border_hi; border-radius: 4px; min-height: 30px; }
QScrollBar:horizontal { background: transparent; height: 9px; margin: 2px; } QScrollBar::handle:horizontal { background: $border_hi; border-radius: 4px; min-width: 30px; }
QScrollBar::handle:hover { background: $accent; }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page { background: none; height: 0; width: 0; }
QSplitter::handle { background: $bg; width: 6px; } QSplitter::handle:hover { background: $accent; }
QStatusBar { background: $panel; border-top: 1px solid $border; color: $dim; }
QToolTip { background: $card; color: $text; border: 1px solid $accent; padding: 5px; }
""")

def theme_icon(t):
    pm = QPixmap(18, 18); pm.fill(Qt.GlobalColor.transparent); p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor(t["border_hi"])); p.setBrush(QColor(t["bg"])); p.drawRoundedRect(0, 0, 17, 17, 4, 4)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(t["accent"])); p.drawEllipse(4, 4, 10, 10); p.end(); return QIcon(pm)

def apply_theme(app, name=None):
    global CURRENT_THEME
    if name in THEMES: CURRENT_THEME = name
    t = th(); app.setStyle("Fusion"); pal = QPalette()
    for role, key in ((QPalette.ColorRole.Window, "bg"), (QPalette.ColorRole.WindowText, "text"), (QPalette.ColorRole.Base, "input"),
                      (QPalette.ColorRole.AlternateBase, "card"), (QPalette.ColorRole.Text, "text"), (QPalette.ColorRole.Button, "raised"),
                      (QPalette.ColorRole.ButtonText, "text"), (QPalette.ColorRole.Highlight, "accent"), (QPalette.ColorRole.HighlightedText, "on_accent"),
                      (QPalette.ColorRole.ToolTipBase, "card"), (QPalette.ColorRole.ToolTipText, "text"), (QPalette.ColorRole.PlaceholderText, "faint")):
        pal.setColor(role, QColor(t[key]))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(t["faint"]))
    r = int(t["r"]); app.setPalette(pal)
    app.setStyleSheet(QSS.substitute({k: v for k, v in t.items() if k != "r"}, r=r, r2=r + 3, rp=max(r + 4, 12)))

def main():
    if sys.platform == "win32":  # своя иконка в панели задач, а не иконка Python
        try: import ctypes; ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TTSStudio.OpenRouter.App")
        except Exception: pass
    app = QApplication(sys.argv); app.setApplicationName("TTS Studio"); app.setWindowIcon(app_icon())
    apply_theme(app, load_json(CONFIG_PATH, {}).get("theme"))
    def hook(t, v, tb):
        if sys.stderr: traceback.print_exception(t, v, tb)
        QMessageBox.critical(None, "Непредвиденная ошибка", "".join(traceback.format_exception_only(t, v))[:2000])
    sys.excepthook = hook
    w = MainWindow(); w.show(); sys.exit(app.exec())

if __name__ == "__main__":
    main()
