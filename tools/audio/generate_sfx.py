"""Звуки игры из локальной Stable Audio 3 (сервер audio-studio-mcp автора) — сразу в карточки Студии.

    AS=/Users/cemeheeb/Projects/Miscelaceous/audio-studio-mcp
    $AS/.venv/bin/python tools/audio/generate_sfx.py                 # всё, чего ещё нет (S_<Имя>.wav в карточке)
    $AS/.venv/bin/python tools/audio/generate_sfx.py --only DoorOpen,Footstep --redo
    $AS/.venv/bin/python tools/audio/generate_sfx.py --list

Запускать питоном из окружения audio-studio-mcp: скрипт берёт его модель напрямую (без MCP), ничего никуда не
отправляет. Для каждого звука из таблицы SOUNDS:
  1. генерируются дубли (разные зёрна) по подсказке в формате Stable Audio 3: источник, действие, материал, место;
  2. каждый дубль доводится до игрового вида: одиночный звук — моно, тишина по краям обрезана, длина не больше
     keep, пик по level; петля — стерео, без вступления и хвоста, концы сведены внахлёст, громкость по RMS;
  3. дубли ложатся в takes/<карточка>-N.wav (48 кГц, 16 бит), описание — в takes/sa3.json;
  4. лучший по простым измерениям (см. score_*) копируется в S_<Имя>.wav и записывается в карточку как take.
Измерения не слышат: они отсекают пустые, оборванные и затянутые дубли, но не оценивают, похож ли звук.
Слушать и менять дубль — в Студии (кнопка «В игру» у дубля), потом tools/ue/import_audio.py.

Несколько звуков с точным рисунком (сердцебиение в петле, сигналы интерфейса, четыре писка сканера шлюза)
не генерируются, а считаются формулой (kind "synth"): модель не держит счёт и ритм, а здесь они важны.
"""
import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AUDIO = os.path.join(ROOT, "SourceArt", "audio")
SR_OUT = 48000
CLOSE = "close-up, dry, no reverb"

# kind: shot — одиночный звук, loop — петля, music — короткая музыкальная фраза, synth — формула.
# gen — сколько секунд просить у модели, keep — сколько оставить (у петли — длина петли), level — пик дБ
# (у петли — RMS дБ), single — оставить одно событие (шаг, щелчок), даже если модель сыграла несколько.
SOUNDS = [
    # --- фон корабля ---
    dict(name="ShipHum", card="ambience/ship-hum", kind="loop", gen=24, keep=20, level=-27,
         src="spaceship engine room tone and air ventilation",
         act="continuous steady drone at a constant level, no events, no fade in, no fade out",
         mat="deep low engine hum, soft air hiss, faint electrical buzz, no melody, no beeps",
         space="inside a quiet metal ship corridor, enclosed, close"),
    dict(name="EmergencyHum", card="ambience/emergency-hum", kind="loop", gen=28, keep=24, level=-26,
         src="spaceship running on emergency power, failing reactor",
         act="continuous low unstable drone with a slow throbbing pulse, constant level, no fade in, no fade out",
         mat="dark sub-bass rumble, a muffled alarm tone far behind thick walls, an occasional faint metal creak, no melody",
         space="inside a sealed metal hull, enclosed, distant"),
    # --- аномалии ---
    dict(name="BlackHoleDrone", card="anomalies/black-hole-drone", kind="loop", gen=19, keep=15, level=-24,
         src="gravitational anomaly bending space",
         act="continuous ominous steady drone, constant level, no pulses, no swells, no rhythm, no fade in, no fade out",
         mat="deep sub-bass with a low warbling whistle above it, unsettling, no melody",
         space="small metal room, close, enveloping"),
    dict(name="BlackHoleSwallow", card="anomalies/black-hole-swallow", kind="shot", gen=3, keep=2.0, level=-2,
         src="everything sucked into a singularity",
         act="one stretching whoosh that drops steeply in pitch and ends in a sudden cut to silence",
         mat="vacuum suction, descending tone, low rumble underneath", space=CLOSE),
    dict(name="Decompression", card="anomalies/decompression", kind="shot", gen=4, keep=3.2, level=-1.5,
         src="air escaping from an airlock into vacuum",
         act="a violent sudden rush that howls for a moment and fades fast into muffled dead silence",
         mat="pressurised air blast, roaring wind", space="inside a metal chamber, close"),
    dict(name="FungusRoom", card="anomalies/fungus-room", kind="loop", gen=19, keep=15, level=-25,
         src="damp fungus overgrowth, something organic slowly growing",
         act="continuous slow irregular dripping and soft wet squelching, constant level, no fade in, no fade out",
         mat="wet and slimy, a faint airy hiss of spores, no animals", space="enclosed damp room, close"),
    dict(name="SlowTime", card="anomalies/slow-time", kind="loop", gen=19, keep=15, level=-24,
         src="deep slowed-down underwater hum, as if all sound is stretched",
         act="continuous steady low drone at a constant level, no swells, no events, no rhythm, no fade in, no fade out",
         mat="deep, muffled, heavy, with soft shimmering overtones, no melody", space="enveloping, wide"),
    dict(name="SmokeRoom", card="anomalies/smoke-room", kind="loop", gen=16, keep=12, level=-25,
         src="electrical fire smouldering behind wall panels",
         act="continuous soft crackling with an occasional small pop, constant level, no fade in, no fade out",
         mat="low hiss of thick smoke, embers, no roaring flames", space="small metal room, close, dry"),
    dict(name="VacuumRoom", card="anomalies/vacuum-room", kind="loop", gen=19, keep=15, level=-27,
         src="airless room heard from inside a space helmet",
         act="continuous near silence with a very low rumble felt through the floor and rare dull distant thuds, no fade in, no fade out",
         mat="muffled, low-passed, a faint high ringing, empty and cold", space="inside a helmet, very close, dead"),
    # --- шлюзы и двери ---
    dict(name="AirlockRefused", card="doors/airlock-refused", kind="shot", gen=2.5, keep=1.4, level=-3,
         src="industrial airlock control panel",
         act="a harsh low double warning buzz followed by one heavy mechanical lock clunk",
         mat="electric buzzer, thick steel latch", space=CLOSE),
    dict(name="AirlockScan", card="doors/airlock-scan", kind="synth", level=-9),
    dict(name="AirlockShift", card="doors/airlock-shift", kind="shot", gen=3, keep=2.2, level=-1.5,
         src="small steel room displaced through folded space",
         act="a short reversed swell into a deep sub-bass whoomp that ends abruptly, then a faint settling rattle",
         mat="warped metallic groan, heavy low impact", space="inside a small steel chamber, close, dry"),
    dict(name="DoorOpen", card="doors/door-open", kind="shot", gen=3, keep=1.7, level=-3,
         src="heavy sci-fi airlock sliding door opening",
         act="a short pneumatic hiss, a smooth electric motor whir and a solid metal clunk as it stops",
         mat="thick steel leaf, pneumatic seals, electric motor", space=CLOSE),
    dict(name="DoorClose", card="doors/door-close", kind="shot", gen=3, keep=1.7, level=-3,
         src="heavy sci-fi airlock sliding door shutting",
         act="an electric motor whir, a deep sealing thud and a short hiss of pressure at the end",
         mat="thick steel leaf, pneumatic seals, electric motor", space=CLOSE),
    # --- противники ---
    dict(name="RatAttack", card="enemies/rat-attack", kind="shot", gen=2, keep=1.1, level=-3,
         src="large mutant rat creature attacking",
         act="one vicious screeching squeal with a snapping bite", mat="harsh raspy animal shriek, teeth snap", space=CLOSE),
    dict(name="RatDeath", card="enemies/rat-death", kind="shot", gen=2.5, keep=1.4, level=-3,
         src="large mutant rat creature dying",
         act="one pained high squeal that cuts off, followed by a soft body thump", mat="raspy animal shriek, soft flesh thud", space=CLOSE),
    dict(name="RatIdle", card="enemies/rat-idle", kind="shot", gen=3, keep=2.2, level=-6,
         src="large rat-like creature lurking close by",
         act="low guttural chittering, wet sniffing and a quiet hiss", mat="throaty, wet, menacing animal", space=CLOSE),
    dict(name="RobotAttack", card="enemies/robot-attack", kind="shot", gen=2, keep=1.1, level=-3,
         src="maintenance robot firing a welding torch",
         act="one short burst: a sharp electric crackle and a hissing zap with a quick servo swing",
         mat="arc welder sparks, electric discharge, small servo motor", space=CLOSE),
    dict(name="RobotDeath", card="enemies/robot-death", kind="shot", gen=3, keep=2.2, level=-3,
         src="maintenance robot shutting down",
         act="a descending motor whine, a few crackling sparks and a final heavy clunk",
         mat="electric motor, shorting wires, metal casing", space=CLOSE),
    # сам удар по металлу — WrenchHitMetal; здесь только ответ робота, без лязга
    dict(name="RobotHit", card="enemies/robot-hit", kind="shot", gen=2, keep=0.8, level=-6,
         src="maintenance robot jolted by a blow",
         act="a short stuttering electrical glitch with a servo twitch and a few sparks",
         mat="buzzing electronics, small servo motor, no impact, no clang", space=CLOSE),
    # у каждого противника своя смерть (автор, 15.11): крыса — RatDeath, робот — RobotDeath, человек — HumanDeath;
    # Death остаётся за героем
    dict(name="HumanDeath", card="enemies/human-death", kind="shot", gen=3, keep=2.4, level=-3,
         idea="The human enemy, the hero's twisted double, is killed.",
         src="heavy brutish man dying",
         act="a low guttural choking groan that gurgles out, then a heavy body slumps onto a metal floor",
         mat="deep hoarse throat, wet gurgle, dull body thud on a steel plate, no words", space=CLOSE),
    dict(name="RobotMove", card="enemies/robot-move", kind="loop", gen=8, keep=4, level=-24,
         src="small tracked maintenance robot driving over a metal floor",
         act="continuous steady electric motor whine with rubber tracks rattling, constant speed, no fade in, no fade out",
         mat="servo motor, rubber treads, metal plates", space="close, dry"),
    # --- события ---
    dict(name="EnginesOnline", card="events/engines-online", kind="shot", gen=6, keep=5.6, level=-1.5,
         src="massive spaceship engines powering up",
         act="a deep rumble rising and building to a powerful roar, a bright electric surge at the peak, settling into a strong steady hum",
         mat="huge turbines, reactor, sub-bass", space="inside the ship hull, wide"),
    # --- вещи ---
    dict(name="FlashlightClick", card="items/flashlight-click", kind="shot", gen=2, keep=0.35, level=-9, single=True,
         src="rubber push button of a flashlight",
         act="one firm mechanical click", mat="plastic and rubber switch", space=CLOSE),
    dict(name="ItemDrop", card="items/item-drop", kind="shot", gen=2, keep=0.9, level=-6,
         src="small metal object dropped onto a metal floor",
         act="one short clatter that settles at once", mat="small steel part, steel floor plate", space=CLOSE),
    dict(name="ItemPickup", card="items/item-pickup", kind="shot", gen=2, keep=0.7, level=-9,
         src="hand grabbing a small object and slipping it into a fabric pocket",
         act="one quick soft grab and a short cloth rustle", mat="canvas fabric, soft handling noise", space=CLOSE),
    dict(name="MedkitUse", card="items/medkit-use", kind="shot", gen=3, keep=2.2, level=-5,
         src="first aid kit used in a hurry",
         act="a plastic case latch pops open, a quick spray hiss, a bandage wrapped and torn off",
         mat="plastic case, aerosol spray, gauze", space=CLOSE),
    dict(name="NotePaper", card="items/note-paper", kind="shot", gen=2, keep=1.1, level=-9,
         src="sheet of paper picked up and unfolded",
         act="one crisp short rustle", mat="dry thin paper", space=CLOSE),
    dict(name="NotebookOpen", card="items/notebook-open", kind="shot", gen=2, keep=0.9, level=-9,
         src="small paper notebook flipped open",
         act="a few pages riffling briefly", mat="paper pages, cardboard cover", space=CLOSE),
    dict(name="PageTurn", card="items/page-turn", kind="shot", gen=2, keep=0.6, level=-10, single=True,
         src="page of a small notebook", act="a single page turned", mat="thin paper", space=CLOSE),
    dict(name="SuitOn", card="items/suit-on", kind="shot", gen=4, keep=3.2, level=-4,
         src="putting on a spacesuit",
         act="heavy fabric rustling, metal latches snapping shut one after another, a helmet locking with a twist and a short pressurising hiss",
         mat="thick suit fabric, metal latches, air valve", space=CLOSE),
    dict(name="SuitOff", card="items/suit-off", kind="shot", gen=3.5, keep=2.7, level=-4,
         src="taking off a spacesuit",
         act="a helmet unlocking with a hiss of released air, latches opening, heavy fabric dropped onto the floor",
         mat="thick suit fabric, metal latches, air valve", space=CLOSE),
    # --- музыкальные фразы ---
    dict(name="DeathSting", card="music/death-sting", kind="music", gen=6, keep=5.5, level=-3,
         prompt="Dark cinematic horror sting: a low synth and string cluster struck once that sinks in pitch and decays "
                "into silence, with a sub-bass impact, ominous and final"),
    dict(name="Win", card="music/win", kind="music", gen=30, keep=30, level=-3,
         prompt="Warm relieved cinematic resolution after a long tension: swelling synth strings and a simple felt piano "
                "melody that opens up, hopeful and tired, gentle slow ending, no drums"),
    # --- герой ---
    dict(name="Cough", card="player/cough", kind="shot", gen=2.5, keep=1.6, level=-4,
         src="adult man coughing", act="two hard coughs, choking on thick smoke", mat="dry rasping throat, no words", space=CLOSE),
    dict(name="Death", card="player/death", kind="shot", gen=3, keep=2.2, level=-3,
         src="adult man collapsing",
         act="a last strained exhale, then a heavy body falls onto a metal floor", mat="breath, body thud on a steel plate, no words", space=CLOSE),
    dict(name="Footstep", card="player/footstep", kind="shot", gen=2, keep=0.45, level=-6, single=True,
         src="heavy work boot on a metal floor panel",
         act="a single footstep", mat="short dull thud with a slight metallic resonance, thin rubber coating", space=CLOSE),
    dict(name="Gasp", card="player/gasp", kind="shot", gen=2.5, keep=1.6, level=-4,
         src="adult man gasping desperately for air",
         act="one strained wheezing inhale that finds nothing, tight and panicked", mat="breathy, hoarse, no words", space="close, muffled"),
    dict(name="Heartbeat", card="player/heartbeat", kind="synth", level=-8),
    dict(name="Hurt", card="player/hurt", kind="shot", gen=2, keep=0.9, level=-3, single=True,
         src="adult man taking a sudden blow",
         act="one short pained grunt, the breath knocked out of him", mat="low male voice, no words", space=CLOSE),
    # удар ключом звучит по-разному (автор, 15.11): по предмету обстановки, по живому (человек, крыса), по металлу робота
    dict(name="WrenchHit", card="player/wrench-hit", kind="shot", gen=2, keep=0.8, level=-3, single=True,
         src="heavy steel wrench hitting something solid",
         act="one dull crunching thud with a short metallic ring", mat="solid steel tool, dense impact", space=CLOSE),
    dict(name="WrenchHitFlesh", card="player/wrench-hit-flesh", kind="shot", gen=2, keep=0.6, level=-3, single=True,
         idea="The pipe wrench lands on a living body: the human enemy or a rat.",
         src="heavy steel wrench hitting a living body",
         act="one dull meaty thud with a wet crunch", mat="flesh and bone impact, soft and heavy, no metallic ring", space=CLOSE),
    dict(name="WrenchHitMetal", card="player/wrench-hit-metal", kind="shot", gen=2, keep=0.8, level=-3, single=True,
         idea="The pipe wrench lands on the metal body of the maintenance robot.",
         src="heavy steel wrench striking a hollow metal machine casing",
         act="one loud bright clang that rings briefly", mat="steel on a thin steel shell, resonant metal", space=CLOSE),
    dict(name="WrenchSwing", card="player/wrench-swing", kind="shot", gen=2, keep=0.5, level=-8, single=True,
         src="heavy metal tool swung fast through the air",
         act="one short low whoosh", mat="air swish", space=CLOSE),
    dict(name="Dodge", card="player/dodge", kind="shot", gen=2, keep=0.6, level=-8, single=True,
         idea="The hero dashes aside to avoid a hit (Space or Left Alt).",
         src="person in a heavy work suit lunging sideways",
         act="one quick fabric rustle with a boot scuff on a metal floor", mat="thick canvas clothing, rubber sole", space=CLOSE),
    # --- интерфейс ---
    dict(name="UiClick", card="ui/ui-click", kind="synth", level=-14),
    dict(name="UiConfirm", card="ui/ui-confirm", kind="synth", level=-12),
    dict(name="UiDeny", card="ui/ui-deny", kind="synth", level=-16),
]


# ---------- измерения и доводка ----------

def db(x):
    return 20.0 * np.log10(np.maximum(x, 1e-9))


def envelope(mono, sr, win_s):
    win = max(1, int(sr * win_s))
    n = len(mono) // win
    if n == 0:
        return np.zeros(1), win
    return np.sqrt((mono[: n * win].reshape(n, win) ** 2).mean(axis=1)), win


def events(mono, sr, floor_db=-38.0, gap_s=0.06):
    """Куски звука громче порога (от пика огибающей), между которыми тишина не короче gap_s: (начало, конец) в отсчётах."""
    env, win = envelope(mono, sr, 0.005)
    rel = db(env) - db(env.max())
    loud = np.nonzero(rel > floor_db)[0]
    if loud.size == 0:
        return []
    out, start, prev = [], loud[0], loud[0]
    for i in loud[1:]:
        if (i - prev) * win / sr > gap_s:
            out.append((start * win, (prev + 1) * win))
            start = i
        prev = i
    out.append((start * win, (prev + 1) * win))
    return out


def fade(a, sr, in_s, out_s):
    a = a.copy()
    n = min(a.shape[-1], int(sr * in_s))
    if n > 0:
        a[..., :n] *= np.sin(np.linspace(0, np.pi / 2, n)) ** 2
    n = min(a.shape[-1], int(sr * out_s))
    if n > 0:
        a[..., -n:] *= np.cos(np.linspace(0, np.pi / 2, n)) ** 2
    return a


def shape_shot(audio, sr, s):
    """Одиночный звук: моно, без тишины по краям, не длиннее keep, пик level. Возвращает (звук, оценка, заметка)."""
    mono = audio.mean(axis=0)
    raw_peak = float(np.abs(mono).max())
    if raw_peak < 1e-4:
        return None, -99.0, "тишина"
    ev = events(mono, sr)
    if not ev:
        return None, -99.0, "тишина"
    total = len(mono)
    if s.get("single"):
        # самое громкое событие; из равных по силе (в пределах 6 дБ) — первое
        peaks = [float(np.abs(mono[a:b]).max()) for a, b in ev]
        best = max(peaks)
        a, b = next(e for e, p in zip(ev, peaks) if p >= best * 0.5)
    else:
        a, b = ev[0][0], ev[-1][1]
    onset, active = a / sr, (b - a) / sr
    cut = b >= total - int(0.05 * sr)                      # звук упёрся в конец записи: оборван
    a = max(0, a - int(0.003 * sr))
    b = min(total, b + int(0.03 * sr))
    clip = mono[a:b]
    keep = int(s["keep"] * sr)
    long_fade = False
    if len(clip) > keep:
        clip, long_fade = clip[:keep], True
    clip = fade(clip, sr, 0.002, max(0.025, 0.3 * s["keep"]) if (long_fade or cut) else 0.025)
    clip = clip * (10 ** (s["level"] / 20) / max(float(np.abs(clip).max()), 1e-6))
    target = 0.8 * s["keep"]
    score = (-2.0 * max(0.0, onset - 0.5)                     # поздно началось
             - 1.5 * abs(np.log(max(active, 0.02) / target))  # длина далека от нужной
             - (1.0 if cut else 0.0)
             - (0.25 * (len(ev) - 1) if s.get("single") else 0.0)
             + 0.03 * db(raw_peak))                           # тихий исходник — обычно неудача
    note = "начало %.2f с, звучит %.2f с%s%s" % (onset, active, ", оборван в конце" if cut else "",
                                                 ", событий %d" % len(ev) if s.get("single") else "")
    return clip[None, :], float(score), note


def shape_loop(audio, sr, s):
    """Петля: стерео, без вступления и хвоста, концы сведены внахлёст, RMS level."""
    if audio.shape[0] == 1:
        audio = np.repeat(audio, 2, axis=0)
    xfade = min(1.5, 0.2 * s["keep"])
    a = audio[:, int(1.0 * sr): audio.shape[-1] - int(0.5 * sr)]
    need = int((s["keep"] + xfade) * sr)
    if a.shape[-1] < need:
        return None, -99.0, "коротко: %.1f с" % (a.shape[-1] / sr)
    off = (a.shape[-1] - need) // 2
    a = a[:, off: off + need]
    env, _ = envelope(a.mean(axis=0), sr, 0.2)
    if env.max() < 1e-4:
        return None, -99.0, "тишина"
    rel = db(env) - db(np.median(env))
    spread = float(np.std(rel))
    holes = float((rel < -18.0).mean())
    n = int(xfade * sr)
    t = np.linspace(0, np.pi / 2, n, dtype=np.float32)
    loop = np.concatenate([a[:, :n] * np.sin(t) + a[:, -n:] * np.cos(t), a[:, n:-n]], axis=1)
    rms = float(np.sqrt((loop ** 2).mean()))
    loop = loop * (10 ** (s["level"] / 20) / max(rms, 1e-6))
    peak = float(np.abs(loop).max())
    if peak > 10 ** (-2 / 20):
        loop = loop * (10 ** (-2 / 20) / peak)
    return loop, -spread - 6.0 * holes, "разброс громкости %.1f дБ, провалов %.0f%%" % (spread, holes * 100)


def shape_music(audio, sr, s):
    """Музыкальная фраза: стерео, тишина в хвосте обрезана, длина не больше keep, плавный уход, пик level."""
    if audio.shape[0] == 1:
        audio = np.repeat(audio, 2, axis=0)
    ev = events(audio.mean(axis=0), sr, floor_db=-50.0, gap_s=0.5)
    if not ev:
        return None, -99.0, "тишина"
    a = audio[:, ev[0][0]: min(audio.shape[-1], ev[-1][1] + int(0.1 * sr))]
    a = a[:, : int(s["keep"] * sr)]
    a = fade(a, sr, 0.005, min(3.0, 0.25 * a.shape[-1] / sr))
    a = a * (10 ** (s["level"] / 20) / max(float(np.abs(a).max()), 1e-6))
    return a, a.shape[-1] / sr, "длина %.1f с" % (a.shape[-1] / sr)


# ---------- звуки формулой ----------

def tone(freq, dur, sr=SR_OUT, decay=18.0, harm=0.0):
    t = np.arange(int(dur * sr)) / sr
    w = np.sin(2 * np.pi * freq * t) + harm * np.sin(2 * np.pi * 2 * freq * t)
    return (w * np.exp(-decay * t)).astype(np.float32)


def place(parts, total, sr=SR_OUT):
    out = np.zeros(int(total * sr), dtype=np.float32)
    for at, w in parts:
        i = int(at * sr)
        out[i: i + len(w)] += w[: len(out) - i]
    return out


def synth(name):
    """Возвращает (звук [каналы, отсчёты], описание). Частота дискретизации SR_OUT."""
    rng = np.random.default_rng(2026)
    if name == "UiClick":
        n = int(0.004 * SR_OUT)
        tick = rng.standard_normal(n).astype(np.float32) * np.linspace(1, 0, n) ** 2 * 0.5
        w = place([(0.0, tick), (0.0, tone(1900, 0.05, decay=90))], 0.07)
        return fade(w, SR_OUT, 0.0005, 0.01)[None, :], "короткий тик: щелчок шума 4 мс и тон 1,9 кГц"
    if name == "UiConfirm":
        w = place([(0.0, tone(659.3, 0.16, decay=20, harm=0.25)), (0.09, tone(987.8, 0.24, decay=14, harm=0.25))], 0.36)
        return fade(w, SR_OUT, 0.002, 0.03)[None, :], "две ноты вверх: ми и си второй октавы"
    if name == "UiDeny":
        beep = np.tanh(3.0 * tone(196.0, 0.085, decay=6, harm=0.5)) * 0.8
        w = place([(0.0, fade(beep, SR_OUT, 0.003, 0.02)), (0.13, fade(beep, SR_OUT, 0.003, 0.02))], 0.25)
        return w[None, :], "два низких глухих гудка 196 Гц"
    if name == "AirlockScan":
        parts = [(0.22 * i, fade(tone(f, 0.07, decay=22, harm=0.2), SR_OUT, 0.002, 0.01))
                 for i, f in enumerate((660.0, 740.0, 830.6, 987.8))]
        parts.append((0.96, fade(tone(1318.5, 0.3, decay=9, harm=0.2), SR_OUT, 0.003, 0.05)))
        return place(parts, 1.3)[None, :], "четыре писка по восходящей через 0,22 с и подтверждающий тон"
    if name == "Heartbeat":
        # 60 ударов в минуту, 4 удара в петле 4 с: «тук» и через 0,3 с «тук» потише и повыше; по краям тишина
        def thump(freq, dur, gain):
            t = np.arange(int(dur * SR_OUT)) / SR_OUT
            w = np.sin(2 * np.pi * (freq * t + 0.6 * freq * 0.03 * (1 - np.exp(-t / 0.03))))   # лёгкий спад тона
            return (gain * w * np.exp(-t / (dur * 0.28)) * np.minimum(1.0, t / 0.006)).astype(np.float32)
        parts = []
        for beat in range(4):
            parts.append((0.05 + beat, thump(52.0, 0.26, 1.0)))
            parts.append((0.35 + beat, thump(68.0, 0.2, 0.62)))
        w = place(parts, 4.0)
        return np.stack([w, w]), "60 ударов в минуту, 4 удара, петля ровно 4 с"
    raise KeyError(name)


# ---------- файлы и карточки ----------

def to_game_rate(audio, sr):
    """Пересчёт частоты модели (44,1 кГц) в частоту игры до любой доводки: иначе края петли, сведённые внахлёст,
    пересчитывались бы у границы файла и стык мог щёлкнуть. Заодно убирается постоянное смещение."""
    audio = audio - audio.mean(axis=-1, keepdims=True)
    if sr == SR_OUT:
        return audio
    with tempfile.TemporaryDirectory() as tmp:
        a, b = os.path.join(tmp, "a.wav"), os.path.join(tmp, "b.wav")
        sf.write(a, np.clip(audio, -1.0, 1.0).T, sr, format="WAV", subtype="FLOAT")
        subprocess.run(["/usr/bin/afconvert", "-f", "WAVE", "-d", "LEF32@%d" % SR_OUT, a, b], check=True)
        data, _ = sf.read(b, dtype="float32", always_2d=True)
    return np.ascontiguousarray(data.T)


def write_wav(path, audio, sr):
    """WAV 48 кГц 16 бит (как делает Студия кнопкой «В игру»). Звук уже на частоте игры."""
    assert sr == SR_OUT
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, np.clip(audio, -1.0, 1.0).T, sr, format="WAV", subtype="PCM_16")


def next_take(card_dir, count):
    takes = os.path.join(card_dir, "takes")
    os.makedirs(takes, exist_ok=True)
    base = os.path.basename(card_dir)
    used = [int(m.group(1)) for f in os.listdir(takes) for m in [re.fullmatch(re.escape(base) + r"-(\d+)\.\w+", f)] if m]
    first = max([0] + used) + 1
    return [os.path.join(takes, "%s-%d.wav" % (base, first + i)) for i in range(count)]


def update_card(card_dir, s, take, note):
    """take: <дубль> и строка в конце блока notes. Карточки нет (Dodge) — создаётся."""
    path = os.path.join(card_dir, "asset.yml")
    if not os.path.exists(path):
        title = re.sub(r"(?<!^)(?=[A-Z])", " ", s["name"])
        lines = ["title: %s" % title, "kind: sound", "priority: 2", 'idea: "%s"' % s.get("idea", ""),
                 'prompt: "%s"' % prompt_text(s), "seconds: %g" % s.get("keep", 1), "notes: |", "  Приоритет 2."]
    else:
        with open(path, encoding="utf-8") as f:
            lines = f.read().rstrip("\n").split("\n")
    # прежний выбор и прежняя строка этого скрипта заменяются, а не копятся
    lines = [l for l in lines if not l.startswith("take:") and "(tools/audio/generate_sfx.py)" not in l]
    try:
        i = next(k for k, l in enumerate(lines) if l.startswith("notes:"))
    except StopIteration:
        lines.append("notes: |")
        i = len(lines) - 1
    j = i + 1
    while j < len(lines) and (lines[j].startswith(" ") or lines[j] == ""):
        j += 1
    while j > i + 1 and lines[j - 1] == "":
        j -= 1
    lines.insert(j, "  " + note)
    lines.append("take: " + take)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def prompt_text(s):
    parts = [s.get("prompt", ""), s.get("src", ""), s.get("act", ""), s.get("mat", ""), s.get("space", "")]
    return ", ".join(p.strip().rstrip(" .,") for p in parts if p.strip()) + "."


def save(s, takes, chosen, extra):
    """takes: [(звук, sr, оценка, заметка, зерно)] — все в takes/, выбранный — в S_<Имя>.wav и в карточку."""
    card_dir = os.path.join(AUDIO, s["card"])
    paths = next_take(card_dir, len(takes))
    log_path = os.path.join(card_dir, "takes", "sa3.json")
    log = json.load(open(log_path, encoding="utf-8")) if os.path.exists(log_path) else []
    for k, ((audio, sr, score, note, seed), path) in enumerate(zip(takes, paths)):
        write_wav(path, audio, sr)
        log.append({"file": os.path.basename(path), "chosen": k == chosen, "seed": seed, "score": round(score, 2),
                    "measured": note, "seconds": round(audio.shape[-1] / sr, 2), **extra})
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    game = os.path.join(card_dir, "S_%s.wav" % s["name"])
    shutil.copyfile(paths[chosen], game)
    how = "посчитан формулой" if s["kind"] == "synth" else "сгенерирован локально Stable Audio 3"
    update_card(card_dir, s, os.path.basename(paths[chosen]),
                "15.11: звук %s (tools/audio/generate_sfx.py), дублей %d, выбран %s по измерениям — "
                "на слух ассистент не проверял. Другой дубль: кнопка «В игру» у него, потом tools/ue/import_audio.py."
                % (how, len(takes), os.path.basename(paths[chosen])))
    return game


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="имена через запятую: DoorOpen,Footstep")
    ap.add_argument("--redo", action="store_true", help="заново, даже если S_<Имя>.wav уже есть")
    ap.add_argument("--variations", type=int, default=0, help="дублей на звук (по умолчанию 4, у петель и музыки 2)")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    only = {n.strip() for n in args.only.split(",") if n.strip()}
    unknown = only - {s["name"] for s in SOUNDS}
    if unknown:
        sys.exit("нет таких звуков: " + ", ".join(sorted(unknown)))
    todo = []
    for s in SOUNDS:
        have = os.path.exists(os.path.join(AUDIO, s["card"], "S_%s.wav" % s["name"]))
        if args.list:
            print("%-17s %-28s %-5s %s" % (s["name"], s["card"], s["kind"], "есть" if have else "нет"))
            continue
        if (only and s["name"] not in only) or (have and not args.redo):
            continue
        todo.append(s)
    if args.list or not todo:
        if not args.list:
            print("нечего делать: все звуки на месте (заново — с --redo)")
        return

    backend = None
    t0 = time.time()
    for n, s in enumerate(todo):
        if s["kind"] == "synth":
            audio, about = synth(s["name"])
            peak = float(np.abs(audio).max())
            audio = audio * (10 ** (s["level"] / 20) / max(peak, 1e-6))
            game = save(s, [(audio, SR_OUT, 0.0, about, None)], 0, {"kind": "synth"})
            print("[%d/%d] %-17s формула: %s -> %s" % (n + 1, len(todo), s["name"], about, os.path.relpath(game, ROOT)), flush=True)
            continue
        if backend is None:
            from audio_studio_mcp.backends import GenerationRequest, create_backend
            from audio_studio_mcp.prompts import prepare_prompt
            backend = create_backend()
        count = args.variations or (2 if s["kind"] in ("loop", "music") else 4)
        kind = "music" if s["kind"] == "music" else "sfx"
        fields = (s.get("src", ""), s.get("act", ""), s.get("mat", ""), s.get("space", ""))
        text, _ = prepare_prompt(s.get("prompt", ""), kind, s["gen"], None, fields)
        seeds = [int(np.random.randint(0, 2 ** 31 - 10))]
        seeds = [seeds[0] + i for i in range(count)]
        res = await backend.generate(seeds, GenerationRequest(prompt=text, seconds=float(s["gen"]), steps=8, cfg=1.0))
        shape = {"shot": shape_shot, "loop": shape_loop, "music": shape_music}[s["kind"]]
        takes = []
        for seed, audio in zip(seeds, res.audios):
            out, score, note = shape(to_game_rate(np.asarray(audio, dtype=np.float32), backend.sample_rate), SR_OUT, s)
            if out is not None:
                takes.append((out, SR_OUT, score, note, seed))
        if not takes:
            print("[%d/%d] %-17s НЕ ВЫШЛО: все дубли пустые" % (n + 1, len(todo), s["name"]), flush=True)
            continue
        chosen = int(np.argmax([t[2] for t in takes]))
        game = save(s, takes, chosen, {"kind": s["kind"], "prompt_used": text, "model": backend.model_label})
        print("[%d/%d] %-17s %4.1f с модели, дублей %d, выбран %d: %s -> %s" % (
            n + 1, len(todo), s["name"], res.wall_seconds, len(takes), chosen + 1, takes[chosen][3],
            os.path.relpath(game, ROOT)), flush=True)
        for k, t in enumerate(takes):
            if k != chosen:
                print("        дубль %d (оценка %.2f против %.2f): %s" % (k + 1, t[2], takes[chosen][2], t[3]), flush=True)
    print("готово за %.0f с" % (time.time() - t0), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
