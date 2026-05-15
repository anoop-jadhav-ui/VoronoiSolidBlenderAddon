import sys
import bpy

PROJECT_DIR = "/Users/anoopjadhav/Documents/vibeCodedProjects/VoronoiSolidBlenderAddon"
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import voronoi_solid_addon

# Change these values before running if needed.
CELL_COUNT = 24
RANDOM_SEED = 7
GAP = 0.08
ATTEMPT_MULTIPLIER = 100
KEEP_ORIGINAL = True
COLLECTION_NAME = "VoronoiCells_Run"
JOIN_CELLS = True

if not hasattr(bpy.types.Scene, "voronoi_solid_settings"):
    voronoi_solid_addon.register()

obj = bpy.context.active_object
if obj is None or obj.type != 'MESH':
    raise RuntimeError("Select a mesh object in Object Mode before running this script")

if obj.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

settings = bpy.context.scene.voronoi_solid_settings
settings.seed_count = CELL_COUNT
settings.random_seed = RANDOM_SEED
settings.gap = GAP
settings.sample_attempt_multiplier = ATTEMPT_MULTIPLIER
settings.keep_original = KEEP_ORIGINAL
settings.collection_name = COLLECTION_NAME
settings.join_cells = JOIN_CELLS

bpy.context.view_layer.objects.active = obj
obj.select_set(True)
result = bpy.ops.object.generate_voronoi_solid_cells()
print("Voronoi generation result:", result)
