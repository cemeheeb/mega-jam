# Связь капитана — `communication-parts`

Студия: `assets/environment/bridge/communication-parts/asset.yaml` · kind: kit · стадия сейчас: prompt · в игре: нет

Микрофон, гарнитура, динамик, панель каналов и кнопка связи для пульта капитана. Без проводов снаружи. Где: рубка — пульты капитанской и зеркальной.

Картинки ещё нет. Есть только промт.

## Результат

По образцу наборов деталей (`control-console-parts`, `door-hatch-controls`):
- FBX на объект: `SM_<Объект>.fbx` (`pipeline/unreal.md`);
- общие текстуры набора рядом с FBX, в FBX не вшиты: `T_CommunicationParts_BaseColor.png`, `T_CommunicationParts_ORM.png`, `T_CommunicationParts_Normal.png` и `T_CommunicationParts_Emissive.png` для экрана панели каналов.

Имена — предложение.

Поле `game`:
- `directory: environment/bridge/communication-parts`
- `model` — меш Tripo;
- `blend`;
- `glb` — пути к `SM_*.fbx`, по объекту (поле Студии так называется);
- `textures` — общие текстуры `T_CommunicationParts_*`.

## Картинка

Шаблон `kit`, свои исключения: coiled cord, telephone handset. Снимков нет — собранный промт:

```text
3D render of a set of game-ready props with semi-realistic PBR materials for a first-person sci-fi game set aboard a bright NASA-punk spaceship. Separate objects in a loose row on a plain seamless light-grey studio background, with clear empty space between them so that no two objects touch; each has only a soft shadow under it.

Five objects: a desk microphone with a small graphite matte plastic head on a flexible brushed aluminium gooseneck rising from a round base; a wireless headset with one padded ear cup and a short boom microphone, hanging on a small aluminium charging hook; a square speaker box of satin painted metal with a perforated aluminium grille; a channel selector panel with six square matte plastic buttons and a small muted teal screen; a large round push-to-talk button under an international orange flip cover.

Colors: off-white paint #ECEAE4, warm light-grey aluminium #B9BCC0, graphite rubber and plastic #2E3236, international orange accents and stripes #F26A21, muted teal screens and indicators #5FC6C9. No other colors.

View: three-quarter view from slightly above, all objects at the same scale and fully visible.

Style: realistic proportions and materials: satin painted metal with light wear on the edges, brushed aluminium, matte rubber and plastic; subtle surface variation and a little dust in the crevices; soft physically based studio lighting.

Avoid: heavy rust, heavy grime, text, logos, table or visible floor, scenery, objects touching or overlapping, stacked objects, a shared base or plinth, cropped parts, glow, transparency, loose cables or cords, coiled cord, telephone handset.
```

## Замысел

Пять объектов:
- **Настольный микрофон.** Небольшая головка из графитового матового пластика на гибкой шее из алюминия, круглое основание.
- **Беспроводная гарнитура.** Одна мягкая чашка и короткий микрофон на штанге. Висит на маленьком алюминиевом крючке-зарядке.
- **Динамик.** Квадратный корпус из крашеного металла, перфорированная алюминиевая решётка.
- **Панель каналов.** Шесть квадратных кнопок из матового пластика и маленький бирюзовый экран. На неё табличка с ключом `SIGN_COMMUNICATION` (Связь / Comms) — малая табличка листа `bridge-decals`.
- **Кнопка «нажми и говори».** Большая круглая, под оранжевой откидной крышкой.

Правило гайда (`assets/environment/style.md`, «Материалы»): у приборов проводов снаружи нет. Ни шнура у микрофона, ни провода у гарнитуры: провод уходит в корпус или в панель. Поэтому в исключениях — витой шнур и телефонная трубка.

## Дальше

Путь набора (`assets/environment/style.md`, KIT):
1. Nano Banana → картинка.
2. Tripo → один меш на картинку.
3. Blender: Separate by Loose Parts, точку привязки каждой детали — на сторону, которой она крепится к пульту.
4. Модели пересобрать по обмеру меша Tripo, развёртка, маски, ArmorPaint, FBX на объект (`pipeline/kit.md`, шаги 11–12) — тем же стеком, что у наборов `door-hatch-controls` и `rack-equipment`.
5. Подвижное — дочерний объект с началом координат на оси: крышка кнопки на петле, шея микрофона, если гнётся. В Unreal — свой `SM_<Деталь>.fbx` и сборка `BP_<Объект>` (`pipeline/unreal.md`, «Подвижные детали»).

Размеры — реальные, по руке (ручки, кнопки — под палец и ладонь).
