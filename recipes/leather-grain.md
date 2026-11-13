# Кожа — `leather-grain`

Студия: `assets/environment/common/leather-grain/asset.yaml` · kind: texture (шаблон grayscale-map) · стадия сейчас: image · в игре: нет

Карта высоты зерна кожи — мелкий рельеф кожаных деталей. Где: кресла, подголовники, ремни.

## Результат

В игре пока ничего нет. Утверждена одна генерация — `approved/leather-grain-1.png`. Дальше ничего не делалось.

Что должно получиться по замыслу:
- `environment/common/leather-grain/leather-grain_height.png` — бесшовная серая карта высоты, 1024 × 1024;
- `environment/common/leather-grain/T_LeatherGrain_Normal.png` — нормаль из неё, 1024 × 1024, зелёный инвертирован (DirectX).

Имена файлов — предложение. Нормаль идёт в Unreal, поэтому названа по `unreal.md`. Карта высоты — вход Blender, имя прежнее.

Поле `game` манифеста:
- `directory: environment/common/leather-grain`
- `textures` — оба файла.

## Картинка

Шаблон `grayscale-map`, своих исключений нет. Снимок `approved/leather-grain-1.txt`, собранный промт совпадает:

```text
Grayscale texture map for a semi-realistic PBR video game: a square swatch of a material seen straight from above, filling the whole frame edge to edge, in shades of grey only. One continuous image, not a grid of repeated copies.

Height map of natural leather grain, a swatch about ten centimetres across: white is the raised pebbled grain, black the deepest creases, mid-grey the average surface. Small irregular rounded pebbles about two millimetres across, separated by a network of thin shallow creases, with a few longer soft wrinkles; even density over the whole frame.

Style: a clean scanned material map at real-world scale: pure grey values with no color, no lighting, no shadows, no highlights or reflections; the same density and brightness over the whole frame with no vignette, so that it tiles calmly.

Avoid: color, a grid of repeated copies, perspective, side view, objects, text, logos, directional shadows, specular highlights, vignette, a frame around the image, a gradient across the image, one large feature in the middle.
```

Что дала генерация. 1024 × 1024, WebP с расширением `.png`. Мелкая галька зерна по всему кадру, между ней сеть тонких складок. Длинные мягкие морщины идут наискосок, сверху слева вниз вправо. Яркость ровная, около средне-серого.

## Бесшовность

Метод — `pipeline/seamless-texture.md`, режим поверхности:
- без окна — зерно нерегулярное;
- если крайние 3–4 пикселя темнее, взять окно с отступом 4 пикселя;
- размер 1024.

## Нормаль (не сделано)

Как у `fabric-weave`, по гайду `assets/environment/style.md` («Карта высоты»):
1. Плоскость в Blender, карта высоты (`Non-Color`) → Bump → Normal.
2. Запекание Normal 1024.

В игре — детальная нормаль с мелким тайлом поверх основной. Цвет кожи даёт материал.

В Unreal — как у `fabric-weave`: зелёный инвертировать, записать `T_LeatherGrain_Normal.png`, импорт с Normalmap и выключенным Flip Green Channel. Входа детальной нормали у `M_Kit` нет: как её накладывать, решить с автором.

## Проверка

- Плитка 3 × 3 без шва.
- Наискосок идущие морщины на плитке не должны выстраиваться в заметные параллельные полосы. Если выстраиваются — перегенерировать с меньшим числом длинных морщин.
- В Unreal зерно выпуклое, а не вдавленное: зелёный инвертирован ровно один раз.

## Подводные камни

- Утверждённая картинка — WebP с расширением `.png`.
