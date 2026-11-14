"""Вид аномалий (DESIGN.md 5.9, решение автора 15.11): материалы в /Game/FX/Anomalies.

    python3 tools/ue/import_anomalies.py          # создать то, чего нет; код шейдеров и параметры экземпляров — всегда

- M_AnomalyLens — шар, который гнёт свет: прозрачный, преломление «2D offset» (сдвиг картинки за ним), сильнее всего
  на полпути от середины к краю и ноль на самом краю — края плавные, ободка нет; сдвиг закручен и дрожит во времени.
  Core и Darken могут затемнить середину, но MI_BlackHole без чёрного — только преломление, как у аномалий STALKER
  (решение автора 15.11). MI_TimeBubble — пузырь замедления (слабый сдвиг, голубой).
- M_SmokeVolume — дым объёмом, как у дымовой гранаты CS2 (просьба автора 15.11): коробка, сквозь которую пиксель
  идёт лучом по объёмному шуму T_SmokeVolume (атлас срезов 64^3, SourceArt/fx/anomalies/source/make_smoke_volume.py).
  Плотное облако с клубами по нижней границе, тени в складках, мягко обтекает мебель и героя (луч обрывается на
  глубине сцены), изнутри ничего не видно. Рисуются только задние грани коробки и без проверки глубины: камера
  может быть внутри. MI_SmokeVolume — дым комнаты (ARunThreat::SetupSmoke; границы коробки задаёт код).
- M_Smoke — прежний дым слоями-плоскостями, запасной: если M_SmokeVolume нет, комната берёт его (MI_Smoke).
- MI_MushroomCap, MI_MushroomStem — заглушки грибов из базовых фигур (ARunRoom::ApplyFungus), экземпляры M_KitSolid.
Граф каждого материала строится один раз; потом меняется только код узлов Custom (удалять узлы у загруженного
материала опасно). Нужен открытый редактор с проектом MegaJam, не в Play.
"""

import json
import os
import sys

from import_wall_columns import call, exists, instance, ref, set_params
from kit_materials import AS, MT, OB, TX, add, link, out, set_props

MI = "editor_toolset.toolsets.material_instance.MaterialInstanceTools"
PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(PROJECT, "SourceArt", "fx", "anomalies")
FOLDER = "/Game/FX/Anomalies"

LENS_CODE = """
// N, V — нормаль и направление на камеру в мире; NV — нормаль в осях вида (xy — на экране)
float ndv = saturate(dot(normalize(N), normalize(V)));
float s = sqrt(saturate(1.0 - ndv * ndv));             // радиус на экране: 0 в середине шара, 1 на краю
float e = 1.0 - s * s;
float bend = 3.5 * s * e * e;                          // плавно к нулю и в середине, и к краю (вместе с наклоном):
                                                       // контура шара не видно (замечание автора 15.11)
float2 dir = NV.xy / max(length(NV.xy), 1e-4);
// воздух дрожит, как над аномалиями в STALKER: направление сдвига закручено к краю и покачивается, сила дышит
float a = 1.3 * s + 0.35 * sin(Time * 1.7 + s * 9.0);
float2 r = float2(dir.x * cos(a) - dir.y * sin(a), dir.x * sin(a) + dir.y * cos(a));
float2 off = r * bend * Strength * (1.0 + 0.2 * sin(Time * 2.3));
float core = saturate((ndv - Core) / 0.05);            // тёмная середина, если Core < 1 (у дыры её нет)
float op = saturate(core + Darken * ndv * ndv * ndv);
return float3(off, op);
"""

# Дым объёмом: Density — поглощение на сантиметр (0,02 — через полтора метра уже стена), Billow — высота зоны клубов
# над нижней границей, Scale — период шума в сантиметрах, цвета — освещённая сторона клуба и его глубина.
# Дым чёрный (замечание автора 15.11: «дым белый, а должен быть чёрный»)
SMOKE_VOLUME = {"Density": 0.035, "Bottom": 110.0, "Billow": 60.0, "Scale": 300.0,
                "ColorLit": (0.03, 0.028, 0.026), "ColorDark": (0.002, 0.002, 0.002)}   # чёрный, как от пожара (автор 15.11)

SMOKE_CODE = """
// WP — точка плоскости, AP — центр пола комнаты (актёр угрозы), Depth — расстояние от камеры
float z = WP.z - AP.z;
float2 uv1 = WP.xy / Scale + float2(0.010, 0.004) * Time + z * 0.0071;
float2 uv2 = WP.xy / (Scale * 0.45) + float2(-0.006, 0.009) * Time - z * 0.0113;
float n1 = Texture2DSample(Tex, TexSampler, uv1).r;
float n2 = Texture2DSample(Tex, TexSampler, uv2).r;
float n = saturate(n1 * (0.55 + n2) - 0.1);
float h = saturate((z - Bottom) / max(Top - Bottom, 1.0));
float cam = saturate((Depth - 25.0) / 120.0);
return n * Density * lerp(0.45, 1.0, h) * cam;
"""

VOLUME_CODE = """
// Дым лучом сквозь объём. Cam, End — камера и точка задней грани коробки относительно актёра угрозы (центр пола
// комнаты); BoxMin, BoxMax — коробка в тех же осях; Face — знак грани (рисуются только задние: камера бывает внутри).
if (Face > 0.0) return float4(0.0, 0.0, 0.0, 0.0);
struct FSmokeVol
{
    // том 64^3 в атласе 8 x 8: плитка 66 px, из них 1 px каймы с каждой стороны (make_smoke_volume.py)
    float2 Vol(Texture2D T, SamplerState S, float3 uvw)
    {
        uvw = frac(uvw);
        float z = uvw.z * 64.0 - 0.5;
        float z0 = floor(z);
        float f = z - z0;
        float i0 = z0 < 0.0 ? 63.0 : z0;
        float i1 = z0 >= 63.0 ? 0.0 : z0 + 1.0;
        float2 uv = (1.0 + uvw.xy * 64.0) / 528.0;
        float2 a = Texture2DSampleLevel(T, S, uv + float2(fmod(i0, 8.0), floor(i0 / 8.0)) * 0.125, 0).rg;
        float2 b = Texture2DSampleLevel(T, S, uv + float2(fmod(i1, 8.0), floor(i1 / 8.0)) * 0.125, 0).rg;
        return lerp(a, b, f);
    }
    // плотность 0..1: ниже bottom пусто, на высоте billow над ним — сплошь; между ними клубы свисают по шуму
    float Dens(Texture2D T, SamplerState S, float3 p, float tm, float bottom, float billow, float scale, float detail)
    {
        float h = p.z - bottom;
        if (h <= 0.0) return 0.0;
        float3 q = p / scale;
        float n = Vol(T, S, q + float3(0.011, 0.006, -0.005) * tm).r;
        float d = saturate(h / billow) * 1.7 + n - 1.0;
        if (detail > 0.5 && d > -0.25 && d < 0.5)
        {
            // мелкий шум выедает края клубов; в глубине дыма его не видно, там он не считается
            float g = Vol(T, S, q * 2.9 + float3(-0.021, 0.013, 0.017) * tm).g;
            d -= (1.0 - g) * 0.25;
        }
        return saturate(d * 5.0);
    }
};
float3 ro = Cam;
float3 rd = End - Cam;
float len = max(length(rd), 1.0);
rd /= len;
float3 sd = float3(abs(rd.x) < 1e-4 ? 1e-4 : rd.x, abs(rd.y) < 1e-4 ? 1e-4 : rd.y, abs(rd.z) < 1e-4 ? 1e-4 : rd.z);
float3 ta = (BoxMin - ro) / sd;
float3 tb = (BoxMax - ro) / sd;
float3 tn = min(ta, tb);
float3 tf = max(ta, tb);
float t0 = max(max(tn.x, tn.y), max(tn.z, 0.0));
float t1 = min(min(tf.x, tf.y), tf.z);
t1 = min(t1, SceneDepth * len / max(PixelDepth, 1.0));   // луч обрывается на том, что стоит в дыму
float span = t1 - t0;
if (span <= 0.5) return float4(0.0, 0.0, 0.0, 0.0);
float dt = max(span / 40.0, 9.0);
// начало луча сдвинуто по-своему в каждом пикселе и кадре: вместо полос шага — зерно, его сглаживает TSR
float jit = frac(52.9829189 * frac(dot(Parameters.SvPosition.xy, float2(0.06711056, 0.00583715))) + frac(Time * 7.31));
float t = t0 + dt * jit;
float tr = 1.0;
float3 col = float3(0.0, 0.0, 0.0);
float3 L = float3(0.53, 0.32, -0.78);                     // свет снизу и сбоку: низ клубов светлый, складки тёмные
FSmokeVol sm;
for (int i = 0; i < 40; i++)
{
    if (t >= t1 || tr < 0.02) break;
    float3 p = ro + rd * t;
    float d = sm.Dens(Tex, TexSampler, p, Time, Bottom, Billow, Scale, 1.0);
    if (d > 0.002)
    {
        // две пробы к свету: ближняя рисует мелкие складки, дальняя — тень между большими клубами
        float dl = sm.Dens(Tex, TexSampler, p + L * 22.0, Time, Bottom, Billow, Scale, 0.0)
                 + sm.Dens(Tex, TexSampler, p + L * 60.0, Time, Bottom, Billow, Scale, 0.0);
        float a = 1.0 - exp(-d * Density * dt);
        col += tr * a * lerp(ColorDark, ColorLit, exp(-1.6 * dl));
        tr *= 1.0 - a;
    }
    t += dt;
}
float alpha = tr < 0.02 ? 1.0 : 1.0 - tr;
return float4(col / max(1.0 - tr, 1e-3), alpha);
"""


def custom_node(m):
    for e in call(MT, "get_expressions", {"material_or_function": m}) or []:
        if "MaterialExpressionCustom" in e["refPath"]:
            return e
    return None


def add_custom(m, code, output_type, names, x=0, y=0):
    node = add(m, "Custom", x, y, Code=code, OutputType=output_type, Description="Anomaly")
    # массив входов растёт по одному элементу, прежние передаются в точности как их отдаёт редактор (build_menu.py)
    for k, name in enumerate(names):
        cur = json.loads(call(OB, "get_properties", {"instance": node, "properties": ["Inputs"]}))["Inputs"]
        if k < len(cur):
            cur[k]["inputName"] = name
        else:
            cur.append({**cur[0], "inputName": name})
        set_props(node, {"Inputs": cur})
    return node


def scalar(m, name, value, x, y):
    return add(m, "ScalarParameter", x, y, ParameterName=name, DefaultValue=value)


def build_lens():
    path = f"{FOLDER}/M_AnomalyLens"
    if exists(path):
        m = ref(path)
        node = custom_node(m)
        set_props(node, {"Code": LENS_CODE})
        # вход Time добавлен 15.11 (дрожание): у собранного раньше материала его дописать, узлы не удалять
        if "Time" not in call(MT, "get_expression_input_names", {"expression": node}):
            cur = json.loads(call(OB, "get_properties", {"instance": node, "properties": ["Inputs"]}))["Inputs"]
            set_props(node, {"Inputs": cur + [{**cur[0], "inputName": "Time"}]})
            link(add(m, "Time", -700, 520), "", node, "Time")
        return path
    m = call(MT, "create_material", {"folder_path": FOLDER, "asset_name": "M_AnomalyLens"})
    node = add_custom(m, LENS_CODE, "CMOT_Float3", ["N", "V", "NV", "Strength", "Core", "Darken", "Time"])
    link(add(m, "Time", -700, 520), "", node, "Time")
    n = add(m, "VertexNormalWS", -700, -200)
    link(n, "", node, "N")
    link(add(m, "CameraVectorWS", -700, -100), "", node, "V")
    nv = add(m, "Transform", -450, 0, TransformSourceType="TRANSFORMSOURCE_World", TransformType="TRANSFORM_View")
    link(n, "", nv, "")
    link(nv, "", node, "NV")
    for i, (name, v) in enumerate((("Strength", 0.05), ("Core", 0.86), ("Darken", 0.35))):
        link(scalar(m, name, v, -700, 150 + i * 120), "", node, name)
    rg = add(m, "ComponentMask", 300, -100, R=True, G=True, B=False, A=False)
    b = add(m, "ComponentMask", 300, 100, R=False, G=False, B=True, A=False)
    link(node, "", rg, "")
    link(node, "", b, "")
    out(rg, "", "MP_Refraction")
    out(b, "", "MP_Opacity")
    tint = add(m, "VectorParameter", 0, 300, ParameterName="Tint", DefaultValue={"R": 0, "G": 0, "B": 0, "A": 1})
    out(tint, "RGB", "MP_EmissiveColor")
    set_props(m, {"BlendMode": "BLEND_Translucent", "ShadingModel": "MSM_Unlit", "RefractionMethod": "RM_2DOffset",
                  "bHasPixelAnimation": True})
    return path


def build_smoke(noise):
    path = f"{FOLDER}/M_Smoke"
    if exists(path):
        set_props(custom_node(ref(path)), {"Code": SMOKE_CODE})
        return path
    m = call(MT, "create_material", {"folder_path": FOLDER, "asset_name": "M_Smoke"})
    node = add_custom(m, SMOKE_CODE, "CMOT_Float1", ["WP", "AP", "Time", "Depth", "Tex", "Density", "Bottom", "Top", "Scale"])
    link(add(m, "WorldPosition", -700, -300), "", node, "WP")
    link(add(m, "ActorPositionWS", -700, -200), "", node, "AP")
    link(add(m, "Time", -700, -100), "", node, "Time")
    link(add(m, "PixelDepth", -700, 0), "", node, "Depth")
    link(add(m, "TextureObjectParameter", -700, 100, ParameterName="Noise", Texture=noise), "", node, "Tex")
    for i, (name, v) in enumerate((("Density", 0.35), ("Bottom", 140.0), ("Top", 290.0), ("Scale", 350.0))):
        link(scalar(m, name, v, -700, 250 + i * 120), "", node, name)
    fade = add(m, "DepthFade", 300, 0, FadeDistanceDefault=60.0)
    link(node, "", fade, "Opacity")
    out(fade, "", "MP_Opacity")
    color = add(m, "VectorParameter", 300, -200, ParameterName="Color", DefaultValue={"R": 0.16, "G": 0.15, "B": 0.14, "A": 1})
    out(color, "RGB", "MP_BaseColor")
    set_props(m, {"BlendMode": "BLEND_Translucent", "TwoSided": True,
                  "TranslucencyLightingMode": "TLM_VolumetricNonDirectional", "bHasPixelAnimation": True})
    return path


def build_smoke_volume(tex):
    path = f"{FOLDER}/M_SmokeVolume"
    if exists(path):
        set_props(custom_node(ref(path)), {"Code": VOLUME_CODE})
        return path
    m = call(MT, "create_material", {"folder_path": FOLDER, "asset_name": "M_SmokeVolume"})
    node = add_custom(m, VOLUME_CODE, "CMOT_Float4", ["Cam", "End", "SceneDepth", "PixelDepth", "Time", "Tex", "BoxMin", "BoxMax",
                                                      "Density", "Bottom", "Billow", "Scale", "ColorLit", "ColorDark", "Face"])
    ap = add(m, "ActorPositionWS", -1100, -300)
    for name, cls, y in (("Cam", "CameraPositionWS", -400), ("End", "WorldPosition", -200)):
        sub = add(m, "Subtract", -800, y)
        link(add(m, cls, -1100, y), "", sub, "A")
        link(ap, "", sub, "B")
        link(sub, "", node, name)
    link(add(m, "SceneDepth", -800, -50), "", node, "SceneDepth")
    link(add(m, "PixelDepth", -800, 50), "", node, "PixelDepth")
    link(add(m, "Time", -800, 150), "", node, "Time")
    link(add(m, "TextureObjectParameter", -800, 250, ParameterName="Volume", Texture=tex), "", node, "Tex")
    for i, (name, v) in enumerate((("BoxMin", -100000.0), ("BoxMax", 100000.0))):
        link(add(m, "VectorParameter", -800, 450 + i * 200, ParameterName=name, DefaultValue={"R": v, "G": v, "B": v, "A": 0}),
             "RGB", node, name)
    for i, (name, v) in enumerate((("Density", 0.02), ("Bottom", 140.0), ("Billow", 70.0), ("Scale", 380.0))):
        link(scalar(m, name, v, -500, 450 + i * 120), "", node, name)
    for i, (name, v) in enumerate((("ColorLit", 0.75), ("ColorDark", 0.34))):
        link(add(m, "VectorParameter", -800, 900 + i * 200, ParameterName=name, DefaultValue={"R": v, "G": v, "B": v, "A": 1}),
             "RGB", node, name)
    link(add(m, "TwoSidedSign", -500, 1000), "", node, "Face")
    rgb = add(m, "ComponentMask", 300, -100, R=True, G=True, B=True, A=False)
    a = add(m, "ComponentMask", 300, 100, R=False, G=False, B=False, A=True)
    link(node, "", rgb, "")
    link(node, "", a, "")
    out(rgb, "", "MP_EmissiveColor")
    out(a, "", "MP_Opacity")
    set_props(m, {"BlendMode": "BLEND_Translucent", "ShadingModel": "MSM_Unlit", "TwoSided": True,
                  "bDisableDepthTest": True, "bHasPixelAnimation": True})
    return path


def main():
    res = call("EditorToolset.EditorAppToolset", "IsPIERunning", {})
    if res is not False:
        sys.exit(f"Редактор в режиме Play (или не ответил: {res!r}). Остановите игру и запустите снова.")
    call(AS, "create_folder", {"path": FOLDER})
    saved = []
    noise_path = f"{FOLDER}/T_SmokeNoise"
    if not exists(noise_path):
        call(TX, "import_file", {"folder_path": FOLDER, "asset_name": "T_SmokeNoise", "source_file": os.path.join(SRC, "T_SmokeNoise.png")})
    set_props(ref(noise_path), {"SRGB": False, "CompressionSettings": "TC_Grayscale"})
    saved.append(noise_path)

    vol_path = f"{FOLDER}/T_SmokeVolume"
    if not exists(vol_path):
        call(TX, "import_file", {"folder_path": FOLDER, "asset_name": "T_SmokeVolume", "source_file": os.path.join(SRC, "T_SmokeVolume.png")})
    # атлас срезов: без сжатия и без мипов, иначе соседние срезы затекают друг в друга
    set_props(ref(vol_path), {"SRGB": False, "CompressionSettings": "TC_VectorDisplacementmap", "MipGenSettings": "TMGS_NoMipmaps",
                              "NeverStream": True})
    saved.append(vol_path)

    lens = build_lens()
    smoke = build_smoke(ref(noise_path))
    volume = build_smoke_volume(ref(vol_path))
    for m in (lens, smoke, volume):
        call(MT, "recompile", {"material_or_function": ref(m)})
        saved.append(m)
    for name, params in (("BlackHole", {"Strength": 0.2, "Core": 1.2, "Darken": 0.0, "Tint": (0.0, 0.0, 0.0)}),
                         ("TimeBubble", {"Strength": 0.015, "Core": 1.2, "Darken": 0.06, "Tint": (0.35, 0.55, 0.8)})):
        p = instance(FOLDER, name, lens)
        set_params(ref(p), params)
        saved.append(p)
    p = instance(FOLDER, "Smoke", smoke)
    set_params(ref(p), {"Density": 1.6, "Bottom": 140.0, "Top": 290.0, "Scale": 350.0, "Color": (0.16, 0.15, 0.14)})
    saved.append(p)
    p = instance(FOLDER, "SmokeVolume", volume)
    set_params(ref(p), SMOKE_VOLUME)
    saved.append(p)
    assert exists("/Game/Materials/M_KitSolid"), "нет /Game/Materials/M_KitSolid: сначала tools/ue/kit_materials.py"
    for name, params in (("MushroomCap", {"Color": (0.30, 0.19, 0.085), "Roughness": 0.55}),
                         ("MushroomStem", {"Color": (0.62, 0.58, 0.46), "Roughness": 0.7})):
        p = instance(FOLDER, name, "/Game/Materials/M_KitSolid")
        set_params(ref(p), params)
        saved.append(p)
    print("saved", call(AS, "save_assets", {"asset_paths": saved}))


if __name__ == "__main__":
    main()
