# Стёганая обшивка — `quilted-padding`

Студия: `assets/environment/common/quilted-padding/asset.yaml` · kind: texture · стадия сейчас: image · в игре: `environment/common/quilted-padding`

Мягкая обшивка стен там, где сидят и спят: рубка, каюты, кают-компания. Материал по словарю (`assets/environment/style.md`, «Материалы»): стёганая обшивка, Metallic 0, Roughness 0,9.

## Результат

В игре:
- `environment/common/quilted-padding/quilted-padding_base.png` — бесшовный цвет. 1024 × 1024, PNG RGB 8 бит. Плитка — 2 × 2 ячейки стёжки. При ячейке 10 см это 20 × 20 см.
- `environment/common/quilted-padding/source/quilted-padding-1.webp` — исходная генерация. Хранится для истории.

Та же бесшовная картинка утверждена в Студии как `approved/quilted-padding-2.png`. Это байт в байт тот же файл, что `quilted-padding_base.png`.

Поле `game` манифеста:
- `directory: environment/common/quilted-padding`
- `textures: [environment/common/quilted-padding/quilted-padding_base.png]`

Карты высоты и нормали пока нет. Это следующий шаг, ниже.

## Картинка

Шаблон `texture`. Снимок `approved/quilted-padding-2.txt`, собранный промт совпадает:

```text
PBR albedo texture for a first-person sci-fi video game set aboard a bright NASA-punk spaceship: a square swatch of the surface seen straight from above, filling the whole frame edge to edge. One continuous image, not a grid of repeated copies.

Wall padding of quilted off-white fabric #ECEAE4: soft rectangular quilted cells about ten centimetres across, gently puffed between thin stitched seams running in straight horizontal and vertical lines; matte cloth with a fine weave visible up close, a few faint creases and slightly worn fabric along some seams.

Style: semi-realistic material at real-world scale; subtle surface variation, light wear and a little dust in the crevices; flat even diffuse lighting with no shadows, highlights or reflections; low contrast so it reads as one calm surface from a distance.

Avoid: large distinct elements, high contrast, a grid of repeated copies, side view, perspective, horizon, objects, text, logos, directional shadows, specular highlights, vignette, borders, heavy rust, heavy grime.
```

Что получилось у генерации. Nano Banana дала 1024 × 1024, файл WebP с расширением `.png`. На картинке почти квадратные ячейки, период сетки — 384 пикселя по обеим осям. В кадре около 2,7 ячейки, то есть около 27 см. Швы прямые, тонкие, светло-бежевые. Ткань тёплая off-white, низкий контраст.

Попытки: сырая генерация `quilted-padding-1.png` отклонена с причиной «швы» — она не бесшовная. Утверждена её обработанная копия `quilted-padding-2.png`. Промт у обеих один.

## Бесшовность

Метод — `pipeline/seamless-texture.md`, режим поверхности.

Параметры:
- **Исходник** — сырая генерация, 1024 × 1024.
- **Окно:** x 253–1021, y 252–1021 (конец не входит), то есть 768 × 769 пикселей. По каждой оси ровно два периода сетки: 2 × 384.
- **Почему такое окно.** Края окна лежат в ткани, на трети ячейки от швов, а не на шве. Правый и нижний края отступают на 3 пикселя от края картинки: крайняя строка исходника темнее.
- **Скачок на краях** снят разложением на периодическую и гладкую части.
- **Размер:** 1024 × 1024, интерполяцией Фурье. Это увеличение примерно в 1,33 раза: ячейка становится 512 пикселей, плитка — ровно 2 × 2 ячейки.

Как подобрать окно на новой генерации:
1. Найти швы по x и по y и измерить период в пикселях.
2. Взять окно в два периода по каждой оси.
3. Сдвинуть его так, чтобы края легли примерно на треть ячейки от шва и не ближе 3 пикселей к краю картинки.
4. Если период не 384, окно будет другим. Размер результата всё равно 1024. Тогда на плитке 2 × 2 ячейки, и при 512 пикселях на ячейку 1024 = 20 см при ячейке 10 см.

Сдвиг на половину с закраской креста здесь не годится. 1024 не делится на ячейку, и на стыке вышла бы узкая ячейка.

## Карта высоты и нормаль (не сделано)

План по гайду (`assets/environment/style.md`, «Карта высоты»):
1. Nano Banana рисует серую карту высоты по готовой бесшовной картинке. Это image-to-image, картинка — единственный референс, промт — в гайде.
2. Карту наложить на цвет и проверить, что рельеф совпадает. Не совпал — перегенерировать.
3. Нормаль — в Blender: плоскость с материалом через Bump, запекание Normal.
4. Roughness 0,9 и Metallic 0 — значениями материала.

Карта высоты рисуется по уже бесшовной картинке. Поэтому она тоже должна выйти бесшовной. Проверить плиткой; при скачке на краях — тот же метод без окна и без смены размера.

## Проверка

- Числа после бесшовности: скачок по x и y не больше обычного шага между соседями.
- Плитка 3 × 3 в предпросмотре: швы стёжки идут непрерывно, ячейки одинаковой ширины, тёмной полосы на стыке нет.
- В Blender плоскость 2 × 2 плитки: ячейка ≈ 10 см при плитке 20 см.
- Цвет ткани близок к `#ECEAE4`, низкий контраст.

## Подводные камни

- Сырые картинки Nano Banana — WebP с расширением `.png`.
- Крайняя строка и столбец генерации темнее. Окно отступает от края на 3 пикселя.
- Окно чуть не квадратное: 768 по x, 769 по y. Так было в исходной обработке.
- Ячейка стёжки около 10 см только в замысле промта. Масштаб в игре задаёт развёртка: 1024 пикселя = 20 см.
