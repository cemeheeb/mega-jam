# Ткань — `fabric-weave`

Студия: `assets/environment/common/fabric-weave/asset.yaml` · kind: texture (шаблон grayscale-map) · стадия сейчас: image · в игре: нет

Карта высоты переплетения ткани — мелкий рельеф тканевых деталей. Где: форма экипажа, чехлы, ремни, обшивка.

## Результат

В игре пока ничего нет. Утверждены две генерации, обложка Студии — `approved/fabric-weave-2.png`. Дальше ничего не делалось.

Что должно получиться по замыслу:
- `environment/common/fabric-weave/fabric-weave_height.png` — бесшовная серая карта высоты, 1024 × 1024;
- `environment/common/fabric-weave/T_FabricWeave_Normal.png` — карта нормалей из неё, 1024 × 1024, зелёный инвертирован (DirectX).

Имена файлов — предложение: в старом проекте их нет. Нормаль идёт в Unreal, поэтому названа по `unreal.md`. Карта высоты — вход Blender, имя прежнее.

Поле `game` манифеста:
- `directory: environment/common/fabric-weave`
- `textures` — оба файла.

## Картинка

Шаблон `grayscale-map`, своих исключений нет. Снимки `approved/fabric-weave-1.txt` и `approved/fabric-weave-2.txt` одинаковые, собранный промт совпадает:

```text
Grayscale texture map for a semi-realistic PBR video game: a square swatch of a material seen straight from above, filling the whole frame edge to edge, in shades of grey only. One continuous image, not a grid of repeated copies.

Height map of tightly woven cotton and nylon fabric, a swatch about five centimetres across: white is the raised crossings of the threads, black the gaps between them, mid-grey the average surface. A plain over-under weave with threads running straight horizontally and vertically, slightly irregular in thickness, with tiny loose fibres; even density over the whole frame.

Style: a clean scanned material map at real-world scale: pure grey values with no color, no lighting, no shadows, no highlights or reflections; the same density and brightness over the whole frame with no vignette, so that it tiles calmly.

Avoid: color, a grid of repeated copies, perspective, side view, objects, text, logos, directional shadows, specular highlights, vignette, a frame around the image, a gradient across the image, one large feature in the middle.
```

Что дали генерации. Обе — 1024 × 1024, WebP с расширением `.png`. Полотняное переплетение, нити прямые, по горизонтали и вертикали.
- `fabric-weave-2` (обложка): повтор узора около 31 пикселя по x и 33 по y, около 32 повторов на кадр. Пиксель ≈ 0,05 мм при образце 5 см.
- `fabric-weave-1`: повтор около 21 пикселя по обеим осям.

Период мерить по пику спектра: БПФ строк или столбцов серой картинки, самая сильная ненулевая частота k, период = 1024 / k.

## Бесшовность

Метод — `pipeline/seamless-texture.md`, режим поверхности. Узор регулярный, поэтому нужно окно: целое число нитей по каждой оси. Например, для `fabric-weave-2` — 32 периода по x (≈ 992 пикселя) и 30 по y (≈ 990 пикселей). Края — не ближе 3–4 пикселей к краю картинки. Размер результата — 1024.

Если период плывёт по кадру, окно подобрать по совпадению краёв: левый столбец окна должен походить на столбец сразу за правым краем. Так же сверху и снизу.

## Нормаль (не сделано)

По гайду `assets/environment/style.md` («Карта высоты», GRAYSCALE-MAP):
1. В Blender плоскость с развёрткой на весь квадрат.
2. Материал: карта высоты (`Non-Color`) → узел Bump → Normal шейдера.
3. Запекание Normal в картинку 1024 той же развёртки.

Сила Bump в старом проекте не задана. Подобрать так, чтобы рельеф нитей читался мягко, без резких граней.

В игре это детальная нормаль с мелким тайлом поверх основной. Цвет ткани даёт материал, а не эта карта.

В Unreal — по `unreal.md`: запечённую нормаль распаковать, инвертировать зелёный (G → 1 − G), записать как данные в `T_FabricWeave_Normal.png`. Импорт — Compression Settings: Normalmap, Flip Green Channel выключен. Входа детальной нормали у `M_Kit` нет: как её накладывать, решить с автором.

## Проверка

- Плитка 3 × 3: нити непрерывны через стык, сдвига фазы нет.
- Нормаль: нет шва на краях, рельеф совпадает с картой высоты.
- В Unreal нити выпуклые, а не вдавленные: зелёный инвертирован ровно один раз.

## Подводные камни

- Без окна в целое число нитей стык виден: разложение убирает скачок яркости, но не сдвиг узора.
- Генерации — WebP с расширением `.png`.
