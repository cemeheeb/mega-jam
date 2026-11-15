"""Голос героя для карточек SourceArt/audio/voice/vo-*: Chatterbox, образец Greenman (~/Projects/chatterbox/CLAUDE.md).

    CB=~/Projects/chatterbox
    $CB/.venv/bin/python tools/audio/generate_voice.py                       # всё, у чего ещё нет S_<Имя>.wav
    $CB/.venv/bin/python tools/audio/generate_voice.py --only vo-kill-rat,vo-suit-on --redo
    $CB/.venv/bin/python tools/audio/generate_voice.py --takes 3

Запускать питоном окружения Chatterbox: модель локальная, ничего никуда не отправляется. Карточки делает
tools/audio/voice_lines.py. Для каждой карточки:
  1. текст prompt из карточки читается голосом в нескольких дублях (зёрна 1..N). Подача — из таблицы
     voice_lines.py: обычная «cold_slow» автора (exaggeration 0,25, cfg 0,25) или hot для встречи с врагом
     (0,8 и 0,5, дублей не меньше трёх). Прежние дубли карточки удаляются;
  2. дубль доводится до игрового вида: тишина по краям обрезана (оставлено 60 мс в начале и 250 мс в конце),
     пик −3 дБ; ложится в takes/<карточка>-N.wav (моно, 16 бит), настройки — в takes/voice.json;
  3. лучший по измерениям копируется в S_<Имя>.wav (48 кГц, 16 бит, как кнопка «В игру» Студии) и пишется
     в карточку как take.
Измерения не слышат: они отсекают затянутые дубли (длина против ожидаемой по числу букв) и дубли с длинной
дырой посередине — так у Chatterbox выглядят заикания и «додуманные» хвосты. Слушать — в Студии.
Потом tools/ue/import_audio.py.
"""
import argparse
import glob
import json
import math
import os
import re
import subprocess
import time

import sys

import torch
import torchaudio as ta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from voice_lines import CALM, LINES  # noqa: E402  подача по реплике: обычная или hot (встреча с врагом)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VOICE_DIR = os.path.join(ROOT, "SourceArt", "audio", "voice")
CB = os.path.expanduser("~/Projects/chatterbox")
SAMPLE = os.path.join(CB, "voices", "librivox_greenman.mp3")
MOOD = {ln["slug"]: ln for ln in LINES}
PEAK = 10 ** (-3 / 20)


def pascal(slug):
    return "".join(p[:1].upper() + p[1:] for p in slug.split("-") if p)


def card_field(text, key):
    """Поле карточки: строка в кавычках (так пишет voice_lines.py) или без них (так может сохранить Студия)."""
    m = re.search(rf"^{key}:\s*(.+)$", text, re.M)
    if not m:
        return ""
    v = m.group(1).strip()
    if v.startswith('"'):
        try:
            return json.loads(v)
        except ValueError:
            return v.strip('"')
    if v.startswith("'"):
        return v.strip("'").replace("''", "'")
    return v


def set_take(path, name):
    text = open(path, encoding="utf-8").read()
    if re.search(r"^take:.*$", text, re.M):
        text = re.sub(r"^take:.*$", f"take: {name}", text, flags=re.M)
    else:
        text = text.rstrip("\n") + f"\ntake: {name}\n"
    open(path, "w", encoding="utf-8").write(text)


def frames_db(w, sr, hop=0.01):
    n = int(sr * hop)
    k = w.shape[-1] // n
    rms = w[..., : k * n].reshape(k, n).pow(2).mean(dim=1).sqrt()
    return 20 * torch.log10(rms + 1e-9), n


def finish(w, sr):
    """Обрезать тишину по краям, пик −3 дБ. Возвращает волну и измерения."""
    w = w.reshape(-1)
    db, n = frames_db(w, sr)
    loud = (db > db.max() - 40).nonzero().reshape(-1)
    a, b = int(loud[0]) * n, (int(loud[-1]) + 1) * n
    a, b = max(0, a - int(0.06 * sr)), min(w.shape[0], b + int(0.25 * sr))
    w = w[a:b]
    w = w / (w.abs().max() + 1e-9) * PEAK
    # самая длинная дыра внутри речи
    db, n = frames_db(w, sr)
    quiet = (db < db.max() - 40).tolist()
    gap = run = 0
    for qf in quiet:
        run = run + 1 if qf else 0
        gap = max(gap, run)
    return w.reshape(1, -1), dict(seconds=round(w.shape[0] / sr, 2), gap=round(gap * n / sr, 2))


def score(m, text, hot=False):
    # по пробам: 74 буквы — 5,9 с, 13 букв — 1,7 с; живая подача быстрее
    expected = 0.4 + len(text) / 15 if hot else 0.6 + len(text) / 12.5
    s = abs(math.log(m["seconds"] / expected))
    if m["gap"] > 1.0:
        s += m["gap"]                        # дыра посередине — заикание или хвост
    return round(s, 3), round(expected, 2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--only", default="")
    p.add_argument("--redo", action="store_true")
    p.add_argument("--takes", type=int, default=2)
    a = p.parse_args()
    only = {s.strip() for s in a.only.split(",") if s.strip()}
    cards = sorted(glob.glob(os.path.join(VOICE_DIR, "vo-*", "asset.yml")))
    todo = []
    for c in cards:
        slug = os.path.basename(os.path.dirname(c))
        wav = os.path.join(os.path.dirname(c), f"S_{pascal(slug)}.wav")
        if only and slug not in only:
            continue
        if os.path.exists(wav) and not a.redo:
            continue
        todo.append((slug, c, wav))
    print(f"voice: {len(todo)} of {len(cards)} cards to do", flush=True)
    if not todo:
        return
    from chatterbox.tts import ChatterboxTTS
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    model = ChatterboxTTS.from_pretrained(device=dev)
    t0 = time.time()
    for i, (slug, card, wav) in enumerate(todo, 1):
        text = card_field(open(card, encoding="utf-8").read(), "prompt")
        d = os.path.dirname(card)
        takes = os.path.join(d, "takes")
        os.makedirs(takes, exist_ok=True)
        log_path = os.path.join(takes, "voice.json")
        log = json.load(open(log_path)) if os.path.exists(log_path) else {}
        best = None
        mood = MOOD.get(slug, dict(CALM, hot=False))
        ex, cfg, hot = mood["exaggeration"], mood["cfg"], mood["hot"]
        for name in [n for n in os.listdir(takes) if n.startswith(slug + "-") and n.endswith(".wav")]:
            os.remove(os.path.join(takes, name))          # старые дубли (прежний текст или подача)
            log.pop(name, None)
        for seed in range(1, max(a.takes, 3 if hot else 0) + 1):
            torch.manual_seed(seed)
            raw = model.generate(text, audio_prompt_path=SAMPLE, exaggeration=ex, cfg_weight=cfg)
            w, m = finish(raw.cpu(), model.sr)
            s, expected = score(m, text, hot)
            name = f"{slug}-{seed}.wav"
            ta.save(os.path.join(takes, name), w, model.sr, encoding="PCM_S", bits_per_sample=16)
            log[name] = dict(text=text, seed=seed, exaggeration=ex, cfg=cfg, sample=os.path.basename(SAMPLE),
                             expected=expected, score=s, **m)
            if best is None or s < best[0]:
                best = (s, name)
        json.dump(log, open(log_path, "w"), indent=1, ensure_ascii=False)
        subprocess.run(["/usr/bin/afconvert", "-f", "WAVE", "-d", "LEI16@48000", os.path.join(takes, best[1]), wav], check=True)
        set_take(card, best[1])
        info = log[best[1]]
        print(f"[{i}/{len(todo)}] {slug}: {best[1]} {info['seconds']} s (expected {info['expected']}, gap {info['gap']}) "
              f"- {time.time() - t0:.0f} s", flush=True)
    print("voice: done", flush=True)


if __name__ == "__main__":
    main()
