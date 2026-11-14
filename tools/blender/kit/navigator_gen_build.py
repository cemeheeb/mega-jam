"""Navigator console, step 8 (pipeline/kit.md): write the ArmorPaint build script <source>/navigator-console.build.c.
Layers: Base, Relief, Scuffs, Scratches, Chips, Edge wear, Grime. Scuffs (rubbed streaks), Scratches and Chips take
their pattern from the wear textures of Singula through navigator-console_scuffs.png (navigator_scuffs.py): R where the
console is touched (only the zones the author marked), G fine scratches, B weathering (streaks dim, chips bright).
No procedural noise anywhere (the author's call): flat colours, an even band of edge wear, grime only in the cavities.
Materials of this console:
paint 100 (warm off-white), keys 010 (grey plastic keys and rocker caps), plastic 001 (black plates, screen recess),
screen 011, mat 110 (graphite rubber desk mat), orange 101 (stripe), satin 111 (steel switch bezels), lamp 000 (glass).
Screens and lamps get their pictures and light in navigator_post.py.
"""
import json

SRC = '/Users/cemeheeb/Projects/ludum-dare/SourceArt/environment/bridge/navigator-console/source'
NAME = 'navigator-console'
HEAD = """float r = step(0.5, id.x);
float g = step(0.5, id.y);
float b = step(0.5, id.z);
float paint = r * (1.0 - g) * (1.0 - b);
float keys = g * (1.0 - r) * (1.0 - b);
float plastic = b * (1.0 - r) * (1.0 - g);
float screen = g * b * (1.0 - r);
float mat = r * g * (1.0 - b);
float orange = r * b * (1.0 - g);
float satin = r * g * b;
float lamp = (1.0 - r) * (1.0 - g) * (1.0 - b);
float clear = screen + lamp;
float edge = clamp(1.055 * pow(max(masks.x, 0.0001), 0.41667) - 0.055, 0.0, 1.0);
float cav = clamp(1.055 * pow(max(masks.y, 0.0001), 0.41667) - 0.055, 0.0, 1.0);
float hgt = clamp(1.055 * pow(max(masks.z, 0.0001), 0.41667) - 0.055, 0.0, 1.0);
float rel = (hgt - 0.5) * 2.0;
float touch = clamp(1.055 * pow(max(scuffs.x, 0.0001), 0.41667) - 0.055, 0.0, 1.0);
float scr = clamp(1.055 * pow(max(scuffs.y, 0.0001), 0.41667) - 0.055, 0.0, 1.0);
float wth = clamp(1.055 * pow(max(scuffs.z, 0.0001), 0.41667) - 0.055, 0.0, 1.0);
"""
LAYERS = [
('Base', """float groove = clamp(-rel * 1.8, 0.0, 1.0) * (1.0 - mat) * (1.0 - clear);
float3 c = float3(0.880, 0.872, 0.845) * paint;
c = c + float3(0.205, 0.210, 0.218) * keys;
c = c + float3(0.095, 0.098, 0.104) * plastic;
c = c + float3(0.440, 0.800, 0.730) * screen;
c = c + lerp(float3(0.215, 0.220, 0.228), float3(0.165, 0.173, 0.190), touch) * mat;
c = c + float3(0.820, 0.350, 0.130) * orange * clamp(0.97 + 1.2 * rel, 0.75, 1.1);
c = c + float3(0.700, 0.700, 0.695) * satin;
c = c + float3(0.300, 0.300, 0.300) * lamp;
c = c * (1.0 - 0.6 * groove);
output.color = c;
output.opacity = 1.0;
output.occlusion = 1.0 - 0.45 * cav - 0.3 * groove;
float polish = touch * (1.0 - edge);
output.roughness = paint * 0.49 + keys * (0.38 - 0.14 * polish) + plastic * (0.44 - 0.08 * polish) + screen * 0.12 + mat * (0.81 - 0.5 * touch) + orange * 0.41 + satin * 0.35 + lamp * 0.10;
output.metallic = satin;
"""),
('Scuffs', """float rub = smoothstep(0.05, 0.20, wth);
float3 c = float3(0.800, 0.795, 0.775) * paint;
c = c + float3(0.300, 0.305, 0.315) * keys;
c = c + float3(0.175, 0.178, 0.186) * plastic;
c = c + float3(0.215, 0.220, 0.228) * mat;
c = c + float3(0.800, 0.400, 0.200) * orange;
c = c + float3(0.640, 0.640, 0.640) * satin;
c = c + float3(0.440, 0.800, 0.730) * screen + float3(0.300, 0.300, 0.300) * lamp;
output.color = c;
output.opacity = rub * touch * (0.3 * paint + 0.35 * keys + 0.65 * plastic + 0.25 * orange + 0.35 * satin);
output.occlusion = 1.0;
output.roughness = paint * 0.36 + keys * 0.50 + plastic * 0.52 + mat * 0.81 + orange * 0.32 + satin * 0.28 + clear * 0.2;
output.metallic = satin;
"""),
('Scratches', """float w = smoothstep(0.02, 0.3, scr);
float k = clamp(w * touch, 0.0, 1.0);
float3 c = float3(0.800, 0.795, 0.785) * paint + float3(0.740, 0.320, 0.120) * orange;
c = c + float3(0.360, 0.365, 0.375) * keys + float3(0.270, 0.275, 0.285) * plastic + float3(0.860, 0.860, 0.860) * satin;
output.color = c;
output.opacity = k * (0.4 * (paint + orange) + 0.9 * plastic + 0.85 * keys + 0.8 * satin);
output.occlusion = 1.0;
output.roughness = (paint + orange) * 0.29 + (keys + plastic) * 0.62 + satin * 0.18 + mat * 0.8 + clear * 0.2;
output.metallic = satin;
"""),
('Chips', """float chip = smoothstep(0.55, 0.85, wth);
output.color = (paint + orange) * float3(0.740, 0.750, 0.760) + (keys + plastic) * float3(0.300, 0.305, 0.315);
output.opacity = chip * touch * 0.5 * ((paint + orange) * 0.9 + (keys + plastic) * 0.8);
output.occlusion = 1.0;
output.roughness = 0.38;
output.metallic = (paint + orange) * 0.8;
"""),
('Edge wear', """float wear = smoothstep(0.8, 1.05, edge);
float3 c = float3(0.68, 0.685, 0.69) * paint;
c = c + float3(0.300, 0.305, 0.312) * keys * (1.0 + 0.4 * touch);
c = c + float3(0.240, 0.244, 0.250) * plastic * (1.0 + 0.35 * touch);
c = c + float3(0.330, 0.335, 0.340) * mat;
c = c + float3(0.930, 0.620, 0.450) * orange;
c = c + float3(0.800, 0.800, 0.795) * satin;
c = c + float3(0.440, 0.800, 0.730) * screen + float3(0.300, 0.300, 0.300) * lamp;
output.color = c;
output.opacity = wear * (paint * 0.5 + keys * (0.5 + 0.4 * touch) + plastic * (0.5 + 0.35 * touch) + mat * 0.45 + orange * 0.55 + satin * 0.5);
output.occlusion = 1.0;
output.roughness = paint * 0.40 + keys * 0.30 + plastic * 0.45 + mat * 0.65 + orange * 0.45 + satin * 0.22 + clear * 0.2;
output.metallic = 0.5 * paint + satin;
"""),
('Grime', """float dirt = clamp(cav * (0.8 + 0.5 * touch * (keys + plastic + satin)), 0.0, 1.0);
float darkp = mat + plastic + keys;
output.color = float3(0.17, 0.155, 0.135) * (1.0 - darkp) + float3(0.42, 0.40, 0.37) * darkp;
output.opacity = dirt * (0.6 - 0.35 * clear - 0.15 * paint);
output.occlusion = 1.0;
output.roughness = 0.75;
output.metallic = 0.0;
"""),
]
q = lambda s: json.dumps(s)
out = ['void main() {']
for n in ('id', 'masks', 'noise', 'relief', 'scuffs'):
    out.append('\tscript_import_asset(%s, 0);' % q('%s/%s_%s.png' % (SRC, NAME, n)))
out.append('\tslot_material_t *m;\n\tui_node_t *out;\n\tui_node_t *sh;\n\tui_node_t *t0;\n\tui_node_t *t1;\n\tui_node_t *t2;\n\tslot_layer_t *l;')


def fill(name, text):
    out.append('\tm = script_material_create(%s);' % q(name))
    out.append('\tscript_material_set(m);')
    out.append('\tm->paint_nor = false;\n\tm->paint_height = false;\n\tm->paint_emis = false;\n\tm->paint_subs = false;')
    out.append('\tout = script_material_get_node("OUTPUT_MATERIAL_PBR");')
    out.append('\tsh = script_material_create_node_at("SHADER_GPU", -400.0, 0.0);')
    for i, (s, asset) in enumerate((('Id', 0), ('Masks', 1), ('Scuffs', 4))):     # no noise: the author wants none
        out.append('\tscript_material_add_input(sh, "RGBA", %s);' % q(s))
        out.append('\tt0 = script_material_create_node_at("TEX_IMAGE", -800.0, %d.0);' % (i * 300))
        out.append('\tscript_material_set_button(t0, 0, %d.0);\n\tscript_material_set_button(t0, 1, 1.0);' % asset)
        out.append('\tscript_material_connect(t0, 0, sh, %d);' % i)
    for s in ('Opacity', 'Occlusion', 'Roughness', 'Metallic'):
        out.append('\tscript_material_add_output(sh, "VALUE", %s);' % q(s))
    out.append('\tscript_material_set_text(sh, 0, %s);' % q(HEAD + text))
    for a, b in ((0, 0), (1, 1), (2, 2), (3, 3), (4, 4)):
        out.append('\tscript_material_connect(sh, %d, out, %d);' % (a, b))
    out.append('\tscript_material_update();')
    out.append('\tl = script_layer_new_fill();')
    out.append('\tscript_layer_set_name(l, %s);' % q(name))
    out.append('\tl->paint_nor = false;\n\tl->paint_nor_blend = false;\n\tl->paint_height = false;\n\tl->paint_height_blend = false;\n\tl->paint_emis = false;\n\tl->paint_subs = false;')
    out.append('\tscript_layer_update(l);')


fill(*LAYERS[0])
out.append('\tm = script_material_create("Relief");\n\tscript_material_set(m);')
out.append('\tm->paint_base = false;\n\tm->paint_opac = true;\n\tm->paint_occ = false;\n\tm->paint_rough = false;\n\tm->paint_met = false;\n\tm->paint_height = false;\n\tm->paint_emis = false;\n\tm->paint_subs = false;')
out.append('\tout = script_material_get_node("OUTPUT_MATERIAL_PBR");')
out.append('\tt0 = script_material_create_node_at("TEX_IMAGE", -400.0, 0.0);\n\tscript_material_set_button(t0, 0, 3.0);\n\tscript_material_set_button(t0, 1, 1.0);')
out.append('\tscript_material_connect(t0, 0, out, 5);\n\tscript_material_update();')
out.append('\tl = script_layer_new_fill();\n\tscript_layer_set_name(l, "Relief");')
out.append('\tl->paint_base = false;\n\tl->paint_opac = true;\n\tl->paint_occ = false;\n\tl->paint_rough = false;\n\tl->paint_met = false;\n\tl->paint_height = false;\n\tl->paint_height_blend = false;\n\tl->paint_emis = false;\n\tl->paint_subs = false;\n\tl->paint_nor = true;\n\tl->paint_nor_blend = false;')
out.append('\tscript_layer_update(l);')
for name, text in LAYERS[1:]:
    fill(name, text)
out.append('\tprintf("layers %d\\n", script_layer_count());')
out.append('\tproject_filepath_set(%s);' % q('%s/%s.arm' % (SRC, NAME)))
out.append('\tproject_save(0);')
out.append('}')
open('%s/%s.build.c' % (SRC, NAME), 'w').write('\n'.join(out) + '\n')
print('ok', sum(len(x) for x in out))
