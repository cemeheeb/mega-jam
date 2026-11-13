"""Каталог предметов и шаблоны записок. Тексты в игре на английском.

Предметы: id = индекс в CATALOG. Роли (проводник, ключи, ложные, пустышки)
раздаёт генератор по зерну, поэтому у предмета нет постоянной роли.
Блокнот, оружие и скафандр сюда не входят: это отдельные виды предметов.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    name: str      # для интерфейса кармана
    noun: str      # для подстановки в записки, со строчной и артиклем
    category: str  # tool / part / personal
    brief: str     # бриф для референса и модели


CATALOG: tuple[Item, ...] = (
    # Инструменты
    Item("Flashlight", "the flashlight", "tool",
         "Chunky industrial flashlight, rubber grip, scuffed yellow body."),
    Item("Duct Tape", "the duct tape", "tool",
         "Half-used roll of silver duct tape with a torn end."),
    Item("Sealant Can", "the sealant can", "tool",
         "Dented aerosol can of hull-breach sealant with hazard stripes."),
    Item("Pressure Gauge", "the pressure gauge", "tool",
         "Round analog gauge with cracked glass on a short pipe stub."),
    # Детали корабля
    Item("Fuse", "the fuse", "part",
         "Large ceramic cartridge fuse with brass caps and a warning label."),
    Item("Power Cell", "the power cell", "part",
         "Cylindrical battery with a carry handle and a glowing charge strip."),
    Item("Circuit Board", "the circuit board", "part",
         "Green circuit board with chips and a burnt corner."),
    Item("Gyroscope", "the gyroscope", "part",
         "Nested metal gimbal rings around a heavy rotor."),
    Item("Coolant Valve", "the coolant valve", "part",
         "Red handwheel valve on a short frosted pipe section."),
    Item("Data Cartridge", "the data cartridge", "part",
         "Chunky plastic storage cartridge with a label and gold contacts."),
    # Личные вещи экипажа
    Item("Voice Recorder", "the voice recorder", "personal",
         "Pocket crew voice recorder with a small speaker grille and a record button."),
    Item("Rubber Duck", "the rubber duck", "personal",
         "Yellow rubber duck, slightly scorched."),
    Item("Family Photo", "the family photo", "personal",
         "Small framed photo behind cracked glass."),
    Item("Dog Tag", "the dog tag", "personal",
         "Crew member's stamped metal dog tag on a ball chain."),
    Item("Snow Globe", "the snow globe", "personal",
         "Glass snow globe with a tiny Earth city inside."),
    Item("Ration Tin", "the ration tin", "personal",
         "Dented food tin with a peeling label."),
)

NOTEBOOK_NAME = "Notebook"

# Виды записок (номера совпадают с N_* в generator.py)
N_NOTEBOOK_FIRST = 0  # первая запись блокнота: проводник
N_LOOP_EXIT = 1       # какой предмет выводит из текущей петли
N_NEXT_KEY = 2        # где появляется следующий ключ
N_USELESS = 3         # какой предмет бесполезен
N_DANGER = 4          # какое сочетание двух предметов привело в опасную комнату
N_ENGINE_SET = 5      # какой набор нужен для двигательного отсека
N_FINALE = 6          # записка в двигательном отсеке: «вспомни, как попал в рубку» (решение автора 13.11)

NOTE_KIND_NAMES = ("notebook_first", "loop_exit", "next_key", "useless",
                   "danger", "engine_set", "finale")

# Подстановки: {item}/{Item} — главный предмет (со строчной / с заглавной),
# {item2}, {item3} — второй и третий, {prereq} — «the X» или «the X and the Y»,
# {leader}/{Leader} — проводник. В Unreal это FText::FormatNamed с теми же именами.
TEMPLATES: dict[int, tuple[str, ...]] = {
    N_NOTEBOOK_FIRST: (
        "Everything you add, the singularity will erase. Only this remains.\n"
        "Carry {item}. It breaks the first loop.",
    ),
    N_LOOP_EXIT: (
        "Same rooms, over and over. {Item} is what breaks this loop.",
        "I walked these rooms for hours before I got it. Carry {item} and the doors let you go.",
        "This loop only lets go of those who carry {item}.",
    ),
    N_NEXT_KEY: (
        "{Item} only shows up for someone carrying {prereq}.",
        "You won't find {item} unless you carry {prereq}. Don't ask me how I know.",
        "Looked everywhere for {item}. It was never there until I picked up {prereq}.",
    ),
    N_USELESS: (
        "{Item} is junk. The doors don't care about it.",
        "Carried {item} through a dozen doors. Nothing changed. Drop it.",
        "Don't waste a slot on {item}.",
    ),
    N_DANGER: (
        "I carried {item} and {item2} through a door. The room behind it nearly killed me.",
        "{Item} with {item2}, and nothing else that matters. That door hurts.",
        "Tried {item} together with {item2}. Bad room. Don't.",
    ),
    N_ENGINE_SET: (
        "The engine room answers to three things: {item}, {item2} and {item3}. "
        "Keep the notebook. {Leader} has done its job. Let it go.",
        "Engines. {Item}, {item2}, {item3}. Nothing else but this notebook. "
        "Drop {leader} when the time comes.",
    ),
    N_FINALE: (
        "Remember how you got to the bridge.",
        "The engines are humming. Now remember how you got to the bridge.",
        "It's fixed. Remember how you got to the bridge, and do it once more.",
    ),
}


def cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def render(kind: int, tpl: int, items: tuple[int, ...]) -> str:
    """Текст записки. items — id предметов в порядке, описанном в generator.Note."""
    nouns = [CATALOG[i].noun for i in items]
    f: dict[str, str] = {}
    if nouns:
        f["item"], f["Item"] = nouns[0], cap(nouns[0])
    if kind == N_NEXT_KEY:
        f["prereq"] = " and ".join(nouns[1:])
    if kind == N_DANGER:
        f["item2"] = nouns[1]
    if kind == N_ENGINE_SET:
        f["item2"], f["item3"] = nouns[1], nouns[2]
        f["leader"], f["Leader"] = nouns[3], cap(nouns[3])
    return TEMPLATES[kind][tpl].format(**f)
