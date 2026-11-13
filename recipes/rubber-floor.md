# Резиновый пол — `rubber-floor`

Студия: `assets/environment/common/rubber-floor/asset.yaml` · kind: texture · стадия сейчас: image · в игре: нет

Рифлёный графитовый пол жилых и рабочих палуб. Где: все палубы, кроме решёток технических. Материал по словарю: резина, Metallic 0, Roughness 0,85.

## Результат

В игре пока ничего нет. Утверждена одна генерация — `approved/rubber-floor-1.png`. Обработки не было.

Что должно получиться по гайду (TEXTURE):
- `environment/common/rubber-floor/rubber-floor_base.png` — бесшовный цвет, 1024 × 1024. Гайд даёт для текстуры поверхности 2 × 2 м на 1024 (512 пикселей на метр). Но при шаге рёбер около 1 см ребро заняло бы 5 пикселей. Поэтому масштаб плитки задаётся по картинке: сколько рёбер в кадре, столько сантиметров в плитке.
- карта высоты и нормаль `rubber-floor_nor.png`.

Имена — предложение.

Поле `game` манифеста:
- `directory: environment/common/rubber-floor`
- `textures` — эти файлы.

## Картинка

Шаблон `texture`, своих исключений нет. Снимок `approved/rubber-floor-1.txt`, собранный промт совпадает:

```text
PBR albedo texture for a first-person sci-fi video game set aboard a bright NASA-punk spaceship: a square swatch of the surface seen straight from above, filling the whole frame edge to edge. One continuous image, not a grid of repeated copies.

Floor covering of ribbed graphite matte rubber #2E3236: narrow, low, rounded parallel ribs about one centimetre apart running in one direction, tops slightly worn smoother, a faint matte grain in the rubber between them, with fine scuffs and a little dust in the grooves.

Style: semi-realistic material at real-world scale; subtle surface variation, light wear and a little dust in the crevices; flat even diffuse lighting with no shadows, highlights or reflections; low contrast so it reads as one calm surface from a distance.

Avoid: large distinct elements, high contrast, a grid of repeated copies, side view, perspective, horizon, objects, text, logos, directional shadows, specular highlights, vignette, borders, heavy rust, heavy grime.
```

**Внимание: утверждённая картинка не совпадает с промтом.** `rubber-floor-1.png` (PNG 1024) — это не рифлёная резина. На ней квадратная графитовая плита с рамкой по краю, винтами в углах и круглым люком с ручкой в середине. Рёбер нет. Как бесшовная текстура пола она не годится: рамка и центральная деталь при повторе выстроятся сеткой.

Нужна новая генерация по тому же промту. Ждём узкие низкие скруглённые рёбра с шагом около 1 см в одну сторону, без рамки и деталей.

Если Nano Banana снова рисует плиту, усилить исключения: «a single panel, a frame or border around the image, screws, a hatch or handle in the middle».

## Бесшовность

Метод — `pipeline/seamless-texture.md`, режим поверхности. Рёбра — регулярный узор:
1. Окно должно вмещать целое число рёбер поперёк их хода.
2. Вдоль хода окно произвольное, но с отступом 3–4 пикселя от краёв.
3. Рёбра должны идти строго по оси картинки. Если они наклонены, сначала повернуть.

Размер результата — 1024.

## Карта высоты и нормаль

По гайду (`assets/environment/style.md`, «Карта высоты»):
1. Nano Banana рисует карту высоты по готовой бесшовной картинке (image-to-image, промт в гайде).
2. Проверить совпадение с цветом.
3. Нормаль — Bump и запекание Normal в Blender.

Roughness 0,85 и Metallic 0 — значениями материала.

## Проверка

- Плитка 3 × 3: рёбра непрерывны, шаг одинаковый через стык.
- Цвет — графит `#2E3236`, низкий контраст.
- Крупных деталей нет.

## Подводные камни

- Утверждена картинка, которая не отвечает промту. Перед обработкой смотреть на картинку, а не только на статус.
