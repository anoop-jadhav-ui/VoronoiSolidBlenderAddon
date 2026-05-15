import sys
import bpy

PROJECT_DIR = "/Users/anoopjadhav/Documents/vibeCodedProjects/VoronoiSolidBlenderAddon"
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import voronoi_solid_addon

# Change these values before running if needed.
GENERATION_MODE = 'SOLID'  # 'SOLID' or 'LATTICE'
LATTICE_OUTPUT_MODE = 'CELLS'  # 'CELLS', 'RAW_EDGES', or 'FINAL_NETWORK'
CELL_COUNT = 24
SURFACE_SEED_COUNT = 24
INTERIOR_SEED_COUNT = 6
SURFACE_SHELL_DEPTH = 0.12
SURFACE_SHELL_BIAS = 1.0
WELD_TOLERANCE = 0.02
MINIMUM_EDGE_LENGTH = 0.01
DUPLICATE_EDGE_TOLERANCE = 0.0005
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
settings.generation_mode = GENERATION_MODE
settings.lattice_output_mode = LATTICE_OUTPUT_MODE
settings.seed_count = CELL_COUNT
settings.surface_seed_count = SURFACE_SEED_COUNT
settings.interior_seed_count = INTERIOR_SEED_COUNT
settings.surface_shell_depth = SURFACE_SHELL_DEPTH
settings.surface_shell_bias = SURFACE_SHELL_BIAS
settings.weld_tolerance = WELD_TOLERANCE
settings.minimum_edge_length = MINIMUM_EDGE_LENGTH
settings.duplicate_edge_tolerance = DUPLICATE_EDGE_TOLERANCE
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
