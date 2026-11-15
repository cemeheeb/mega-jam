"""Мысли героя вслух: таблица реплик -> карточки Студии и таблица для игры.

    python3 tools/audio/voice_lines.py            # карточки SourceArt/audio/voice/vo-*/asset.yml и RunVoiceData.inl
    python3 tools/audio/voice_lines.py --list     # только показать реплики
    python3 tools/audio/voice_lines.py --only=vo-meet-rats,vo-meet-robot   # переписать эти карточки (take пропадёт)

Источник истины по репликам: эта таблица. game: строка ровно как в коде игры (Say() или строка шага GetStep());
по ней игра находит звук (RunVoiceData.inl -> ARunDirector::VoiceFor). Поменяли строку в коде — поменять и здесь,
иначе реплика просто останется без голоса. say: что произносит голос; без подсказок клавиш ([E], [Tab]) и без
надписей капсом. step: строка шага — звучит один раз за забег, когда шаг сменился и голос свободен.

Голос делает tools/audio/generate_voice.py (Chatterbox, ~/Projects/chatterbox). Существующую карточку скрипт не
переписывает (автор мог поправить текст в Студии), только дописывает новые; --force переписывает все.

Не озвучены нарочно:
- строки с переменной частью (код корабля, записки, «Still the same bridge. %s»);
- урон и смерть: они от второго лица, это не мысли героя;
- строки шага, которые повторяют реплику того же момента (неправильная комната, противник, тайник, кресло).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VOICE = os.path.join(ROOT, "SourceArt", "audio", "voice")
INL = os.path.join(ROOT, "Source", "MegaJam", "Run", "RunVoiceData.inl")


# Подача Chatterbox: обычная — «cold_slow» автора; hot — встреча с врагом (просьба автора 15.11, ночь: «речь сухая,
# добавь матов в критических ситуациях, и сделай реплики в таких ситуациях короче»): живее и быстрее.
CALM = dict(exaggeration=0.25, cfg=0.25)
HOT = dict(exaggeration=0.8, cfg=0.5)


def line(slug, title, game, where, say=None, step=False, hot=False):
    return dict(slug=f"vo-{slug}", title=f"Hero: {title}", game=game, say=say or game, where=where, step=step, hot=hot,
                **(HOT if hot else CALM))


LINES = [
    # --- начало: каюта, рубка, петля ---
    line("cabin-wake", "Cabin Wake", "My cabin? I don't remember falling asleep. And the door is locked with a code.",
         "просыпается в каюте"),
    line("step-cabin-locked", "Cabin Locked", "Locked. There is a keypad left of the door [E].\nNo code? Leave it empty and press [Enter]: a new ship.",
         "шаг в каюте, дверь заперта", say="Locked. There is a keypad left of the door.", step=True),
    line("step-cabin-open", "Cabin Open", "The door is open. Time to find out where I am.", "шаг в каюте, дверь открыта", step=True),
    line("corpse-self", "Corpse Is Me", "Someone is lying by the bridge door. Same suit, same face... That is me.",
         "первый взгляд на рубку и свой труп"),
    line("step-leave-bridge", "Leave Bridge", "I need to get off the bridge. Any door will do.", "шаг на рубке до первой петли", step=True),
    line("bridge-loop", "Bridge Loop", "The bridge again? The same body by the door... I walked in a circle.",
         "вернулся на рубку в первый раз"),
    line("step-loop", "Walking In A Loop",
         "Every door brings me back to this bridge. I am walking in a loop.\nSomething here must be keeping me in. I should search the bridge.",
         "шаг на рубке после первой петли",
         say="Every door brings me back to this bridge. I am walking in a loop. Something here must be keeping me in. I should search the bridge.",
         step=True),
    line("hint-corner", "Hint Corner", "I never looked behind the ring of consoles. A far corner, maybe?", "подсказка тайника, дальний угол"),
    line("hint-chair", "Hint Chair", "I never looked inside the ring of consoles. At the foot of the captain's chair?", "подсказка тайника, у кресла"),
    line("guide-item", "Guide Item", "This does not belong on the bridge. What happens if I take it through a door?",
         "взял вещь из тайника рубки"),
    line("first-room", "First Room", "A different room, finally! It was the thing in my pocket. The doors... they read what I carry.",
         "первая новая комната после петли"),
    line("step-notebook-here", "Notebook Here", "My notebook is here. I should take it [E].", "шаг: блокнот в комнате",
         say="My notebook is here. I should take it.", step=True),
    line("step-read-notebook", "Read Notebook", "Let me read my notebook [Tab].", "шаг: блокнот взят, ещё не открыт",
         say="Let me read my notebook.", step=True),
    # --- мысли-открытия (EnterRoom, по разу) ---
    line("thought-back", "Thought Back Door", "Back where I was. The door I walked in through always leads back.",
         "вернулся через обратную дверь"),
    line("thought-same", "Thought Same Pocket", "The same room again? Of course: same pocket, same room.",
         "та же комната с тем же карманом"),
    line("thought-junk", "Thought Junk", "The same room, even though my pocket changed. So that thing does not count for the doors. Junk.",
         "та же комната, хотя карман сменился"),
    line("thought-new", "Thought New Room", "Somewhere new again. Something new in my pocket - a new room behind the door.",
         "новая комната после петли", say="Somewhere new again. Something new in my pocket... a new room behind the door."),
    # --- поиск по запискам ---
    line("step-notes-here", "Notes Here", "There are notes here [E]. Maybe they say what to carry next.", "шаг: в комнате непрочитанные записки",
         say="There are notes here. Maybe they say what to carry next.", step=True),
    line("step-carry", "Carry And Try", "Carry what the notes name, drop the junk [G], try a door. What I carry decides where it leads.",
         "шаг по умолчанию", say="Carry what the notes name, drop the junk, try a door. What I carry decides where it leads.", step=True),
    line("pocket-full", "Pocket Full", "My pocket is full.", "карман полон, вещь не взять"),
    line("hands-empty", "Hands Empty", "My hands are empty. Mouse wheel or [1]-[4] takes an item in hand.", "пустые руки: применить или ударить нечем",
         say="My hands are empty."),
    # --- опасные комнаты ---
    line("anomaly-black-hole", "Anomaly Black Hole", "A tiny black hole. This room is wrong. I can just walk back out the way I came.",
         "вошёл в комнату с чёрной дырой"),
    line("anomaly-smoke", "Anomaly Smoke", "Smoke. This room is wrong. I can just walk back out the way I came.", "вошёл в задымлённую комнату"),
    line("anomaly-slow-time", "Anomaly Slow Time", "Slow time. This room is wrong. I can just walk back out the way I came.",
         "вошёл в комнату с медленным временем"),
    line("anomaly-fungus", "Anomaly Fungus", "Fungal growth. This room is wrong. I can just walk back out the way I came.",
         "вошёл в заросшую комнату"),
    line("hull-breach", "Hull Breach", "Hull breach. No air in here, only the hiss of my suit.", "вошёл в пробоину в скафандре"),
    line("hull-locked", "Hull Locked", "The airlock reads my pocket and stays shut: HULL BREACH beyond. I need a suit.",
         "шлюз в пробоину не открылся без скафандра", say="The airlock reads my pocket and stays shut. Hull breach beyond. I need a suit."),
    line("suit-on", "Suit On", "I pull on the space suit. The helmet seals with a hiss.", "надел скафандр"),
    line("suit-off", "Suit Off", "I step out of the space suit and leave it standing.", "снял скафандр"),
    line("suit-no-air", "Suit No Air", "Not here. There is no air to breathe.", "попытка снять скафандр в пробоине"),
    # --- противники ---
    line("meet-twin", "Meet Twin", "Damn! That's me. Get a door between us!", "в комнате двойник", hot=True),
    line("meet-robot", "Meet Robot", "Oh hell, a robot! It stays here. I don't have to.", "в комнате робот", hot=True),
    line("meet-rats", "Meet Rats", "Rats! Huge damn rats. Keep moving!", "в комнате крысы", hot=True),
    line("twin-follows", "Twin Follows", "Damn it, it followed me!", "двойник успел за героем в дверь", hot=True),
    line("no-weapon", "No Weapon", "Hell, nothing to fight with!", "удар без оружия", hot=True),
    line("kill-twin", "Kill Twin", "The other me goes down and does not get up.", "двойник убит"),
    line("kill-robot", "Kill Robot", "The robot sparks and goes still.", "робот убит"),
    line("kill-rat", "Kill Rat", "One rat less.", "крыса убита"),
    line("medkit-keep", "Medkit Keep", "I am not hurt. Better keep the medkit.", "аптечка при полном здоровье"),
    line("medkit-use", "Medkit Use", "I patch myself up. Better.", "применил аптечку"),
    # --- карточка капитана и финал ---
    line("captain-found", "Captain Found", "The captain. By the warp core. His card is still on him.", "вошёл в машинное отделение"),
    line("step-take-card", "Take Card", "The captain's card. I need it [E].", "шаг в машинном отделении",
         say="The captain's card. I need it.", step=True),
    line("step-pocket-full-card", "Pocket Full For Card", "My pocket is full. Drop what I no longer need [G], then take the captain's card [E].",
         "шаг в машинном отделении с полным карманом",
         say="My pocket is full. Drop what I no longer need, then take the captain's card.", step=True),
    line("step-card-left", "Card Left Behind", "The card is still in the engine room. Same pocket as then - same room.",
         "шаг: двигатель запущен, карточка осталась", say="The card is still in the engine room. Same pocket as then... same room.", step=True),
    line("step-drop-extra", "Drop Extra", "Only the notebook and the card. Everything else goes: [1]-[4] takes an item in hand, [G] drops it.",
         "шаг с карточкой и лишними вещами", say="Only the notebook and the card. Everything else goes.", step=True),
    line("step-go-bridge", "Go To Bridge", "Nothing that matters in my pocket now. Any door should take me to the bridge.",
         "шаг с карточкой и пустым карманом", step=True),
    line("card-bridge", "Card On Bridge", "The bridge. Now the card goes into the captain's chair.", "вернулся на рубку с карточкой"),
    line("ship-saved", "Ship Saved", "The card clicks into the slot. The engines roar. THE SHIP IS SAVED.", "победа",
         say="The card clicks into the slot. The engines roar. The ship is saved."),
]


def pascal(slug):
    return "".join(p[:1].upper() + p[1:] for p in slug.split("-") if p)


def q(s):
    return json.dumps(s, ensure_ascii=False)     # строка JSON — это и строка YAML в двойных кавычках


def card_text(ln):
    kind = "строка шага: звучит один раз за забег, когда шаг сменился" if ln["step"] else "реплика: звучит вместе с субтитром"
    return (f"title: {q(ln['title'])}\n"
            "kind: sound\n"
            f"priority: {2 if ln['step'] else 1}\n"
            f"idea: {q(ln['game'])}\n"
            f"prompt: {q(ln['say'])}\n"
            "notes: |\n"
            f"  Мысль героя вслух ({kind}): {ln['where']}.\n"
            "  idea — строка ровно как в игре, по ней игра находит звук; prompt — что произносит голос (без клавиш).\n"
            f"  Голос: Chatterbox, образец Greenman (~/Projects/chatterbox/CLAUDE.md), exaggeration {ln['exaggeration']}, "
            f"cfg {ln['cfg']}{' (встреча с врагом: живее и быстрее)' if ln['hot'] else ''}.\n"
            "  Делает tools/audio/generate_voice.py: дубли в takes/, лучший по измерениям — S_<Имя>.wav; на слух\n"
            "  ассистент не проверял. Другой дубль — кнопка «В игру» в Студии, потом tools/ue/import_audio.py.\n")


def cpp(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def main():
    if "--list" in sys.argv:
        for ln in LINES:
            print(f"{'step' if ln['step'] else 'say '}  S_{pascal(ln['slug']):28s} {ln['say']}")
        print(len(LINES), "lines")
        return
    force = "--force" in sys.argv
    only = {a for arg in sys.argv[1:] if arg.startswith("--only=") for a in arg[7:].split(",")}
    slugs = [ln["slug"] for ln in LINES]
    games = [ln["game"] for ln in LINES]
    assert len(set(slugs)) == len(slugs) and len(set(games)) == len(games), "повторы в таблице"
    made = 0
    for ln in LINES:
        d = os.path.join(VOICE, ln["slug"])
        f = os.path.join(d, "asset.yml")
        if os.path.exists(f) and not force and ln["slug"] not in only:
            continue
        os.makedirs(d, exist_ok=True)
        with open(f, "w", encoding="utf-8") as out:
            out.write(card_text(ln))
        made += 1
    rows = [f'\t{{ TEXT("{cpp(ln["game"])}"), TEXT("{pascal(ln["slug"])}"), {"true" if ln["step"] else "false"} }},'
            for ln in LINES]
    with open(INL, "w", encoding="utf-8") as out:
        out.write("// Создаётся tools/audio/voice_lines.py — руками не править. Строка игры -> голос /Game/Audio/S_<Имя>,\n"
                  "// третье — строка шага (звучит один раз за забег). Подключается в RunDirector.cpp (VoiceFor).\n")
        out.write("\n".join(rows) + "\n")
    print(f"cards: {made} new of {len(LINES)}; table: {os.path.relpath(INL, ROOT)}")


if __name__ == "__main__":
    main()
