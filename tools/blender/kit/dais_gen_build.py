"""Bridge dais, step 8 (pipeline/kit.md): write the ArmorPaint build script <source>/bridge-dais.build.c.
Copied from navigator_gen_build.py. Layers: Base, Relief, Scuffs, Scratches, Chips, Edge wear, Grime. Scuffs, Scratches
and Chips take their pattern from the Singula wear textures through bridge-dais_scuffs.png (dais_scuffs.py): R where
the dais is trodden (only the author's zone), G fine scratches, B weathering. No procedural noise (the author's call).
Materials: paint 100 (warm off-white plates), metal 010 (light aluminium side, trim, pockets: matte, metallic 0.3, so that it reads light grey as in the picture
whatever it reflects; bare aluminium only where edges and scratches wear through), dark 001 (graphite
plinth, slot walls, niche backs), lens 011 (teal light strip: its light goes in in dais_post.py), rubber 110 (graphite
anti-slip tiles, pebble tops lighter by the height), orange 101 (edge stripe), satin 111 (steel frames, bars),
brushed 000 (mounting plate with concentric brushing by the height, light steel screws and bolts). Rubber is soft: no scratches and no chips on it.
"""
import json

SRC = '/Users/cemeheeb/Projects/ludum-dare/SourceArt/environment/bridge/bridge-dais/source'
NAME = 'bridge-dais'
HEAD = """float r = step(0.5, id.x);
float g = step(0.5, id.y);
float b = step(0.5, id.z);
float paint = r * (1.0 - g) * (1.0 - b);
float metal = g * (1.0 - r) * (1.0 - b);
float dark = b * (1.0 - r) * (1.0 - g);
float lens = g * b * (1.0 - r);
float rubber = r * g * (1.0 - b);
float orange = r * b * (1.0 - g);
float satin = r * g * b;
float brushed = (1.0 - r) * (1.0 - g) * (1.0 - b);
float edge = clamp(1.055 * pow(max(masks.x, 0.0001), 0.41667) - 0.055, 0.0, 1.0);
float cav = clamp(1.055 * pow(max(masks.y, 0.0001), 0.41667) - 0.055, 0.0, 1.0);
float hgt = clamp(1.055 * pow(max(masks.z, 0.0001), 0.41667) - 0.055, 0.0, 1.0);
float rel = (hgt - 0.5) * 2.0;
float touch = clamp(1.055 * pow(max(scuffs.x, 0.0001), 0.41667) - 0.055, 0.0, 1.0);
float scr = clamp(1.055 * pow(max(scuffs.y, 0.0001), 0.41667) - 0.055, 0.0, 1.0);
float wth = clamp(1.055 * pow(max(scuffs.z, 0.0001), 0.41667) - 0.055, 0.0, 1.0);
float pebble = smoothstep(0.08, 0.28, rel);
"""
LAYERS = [
('Base', """float groove = clamp(-rel * 1.8, 0.0, 1.0) * (1.0 - rubber) * (1.0 - brushed) * (1.0 - lens);
float3 c = float3(0.880, 0.872, 0.845) * paint;
c = c + float3(0.680, 0.688, 0.698) * metal;
c = c + float3(0.095, 0.098, 0.104) * dark;
c = c + float3(0.300, 0.640, 0.650) * lens;
c = c + float3(0.150, 0.155, 0.162) * rubber * clamp(0.78 + 0.75 * rel, 0.7, 1.05);
c = c + float3(0.820, 0.350, 0.130) * orange;
c = c + float3(0.430, 0.437, 0.447) * satin;
c = c + float3(0.780, 0.785, 0.790) * brushed * clamp(1.0 + 0.8 * rel, 0.9, 1.1);
c = c * (1.0 - 0.6 * groove);
output.color = c;
output.opacity = 1.0;
output.occlusion = 1.0 - 0.45 * cav - 0.3 * groove;
output.roughness = paint * 0.48 + metal * 0.48 + dark * 0.5 + lens * 0.15 + rubber * (0.86 - 0.22 * touch * pebble) + orange * 0.41 + satin * 0.34 + brushed * clamp(0.26 + 2.0 * rel, 0.18, 0.34);
output.metallic = 0.3 * metal + satin + brushed;
"""),
('Scuffs', """float rub = smoothstep(0.05, 0.20, wth);
float3 c = float3(0.760, 0.755, 0.740) * paint;
c = c + float3(0.620, 0.628, 0.638) * metal;
c = c + float3(0.170, 0.174, 0.180) * dark;
c = c + float3(0.215, 0.220, 0.228) * rubber;
c = c + float3(0.720, 0.370, 0.190) * orange;
c = c + float3(0.540, 0.548, 0.558) * satin;
c = c + float3(0.300, 0.640, 0.650) * lens + float3(0.780, 0.785, 0.790) * brushed;
output.color = c;
output.opacity = rub * touch * (0.35 * paint + 0.3 * metal + 0.4 * dark + 0.5 * rubber + 0.35 * orange + 0.3 * satin);
output.occlusion = 1.0;
output.roughness = paint * 0.42 + metal * 0.38 + dark * 0.52 + rubber * 0.66 + orange * 0.36 + satin * 0.3 + (lens + brushed) * 0.2;
output.metallic = 0.3 * metal + satin + brushed;
"""),
('Scratches', """float w = smoothstep(0.02, 0.3, scr);
float k = clamp(w * touch, 0.0, 1.0);
float3 c = float3(0.800, 0.795, 0.785) * paint + float3(0.740, 0.320, 0.120) * orange;
c = c + float3(0.820, 0.826, 0.834) * metal + float3(0.270, 0.275, 0.285) * dark + float3(0.700, 0.705, 0.712) * satin;
output.color = c;
output.opacity = k * (0.4 * (paint + orange) + 0.6 * metal + 0.8 * dark + 0.7 * satin);
output.occlusion = 1.0;
output.roughness = (paint + orange) * 0.29 + metal * 0.3 + dark * 0.62 + satin * 0.2 + (rubber + lens + brushed) * 0.3;
output.metallic = metal + satin;
"""),
('Chips', """float chip = smoothstep(0.55, 0.85, wth);
output.color = (paint + orange) * float3(0.740, 0.750, 0.760) + dark * float3(0.300, 0.305, 0.315) + metal * float3(0.600, 0.606, 0.614);
output.opacity = chip * touch * 0.5 * ((paint + orange) * 0.9 + dark * 0.8 + metal * 0.6);
output.occlusion = 1.0;
output.roughness = 0.38;
output.metallic = (paint + orange) * 0.8 + metal;
"""),
('Edge wear', """float wear = smoothstep(0.8, 1.05, edge);
float3 c = float3(0.68, 0.685, 0.69) * paint;
c = c + float3(0.860, 0.870, 0.880) * metal;
c = c + float3(0.240, 0.244, 0.250) * dark;
c = c + float3(0.250, 0.255, 0.262) * rubber;
c = c + float3(0.930, 0.620, 0.450) * orange;
c = c + float3(0.750, 0.758, 0.768) * satin;
c = c + float3(0.880, 0.882, 0.890) * brushed + float3(0.300, 0.640, 0.650) * lens;
output.color = c;
output.opacity = wear * (1.0 + 0.4 * touch) * (paint * 0.5 + metal * 0.5 + dark * 0.45 + rubber * 0.35 + orange * 0.55 + satin * 0.5 + brushed * 0.4);
output.occlusion = 1.0;
output.roughness = paint * 0.40 + metal * 0.25 + dark * 0.45 + rubber * 0.7 + orange * 0.45 + satin * 0.22 + brushed * 0.2 + lens * 0.15;
output.metallic = 0.5 * (paint + orange) + metal + satin + brushed;
"""),
('Grime', """float dirt = clamp(cav * (0.8 + 0.4 * touch), 0.0, 1.0);
float darkp = dark + rubber;
output.color = float3(0.17, 0.155, 0.135) * (1.0 - darkp) + float3(0.090, 0.088, 0.085) * darkp;
output.opacity = 0.6 * dirt * (1.0 - lens);
output.occlusion = 1.0;
output.roughness = 0.8;
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
