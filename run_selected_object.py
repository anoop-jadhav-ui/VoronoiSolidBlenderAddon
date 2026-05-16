import sys
import bpy

PROJECT_DIR = "/Users/anoopjadhav/Documents/vibeCodedProjects/VoronoiSolidBlenderAddon"
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import voronoi_solid_addon

# Change these values before running if needed.
GENERATION_MODE = 'SOLID'  # 'SOLID' or 'LATTICE'
SOLID_OUTPUT_MODE = 'CELLS'  # 'CELLS' or 'CARVED'
LATTICE_OUTPUT_MODE = 'CELLS'  # 'CELLS', 'RAW_EDGES', 'FINAL_NETWORK', 'GN_PREVIEW', or 'STRUTS'
SAMPLING_MODE = 'BLUE_NOISE'  # 'BLUE_NOISE' or 'RANDOM'
CELL_COUNT = 24
SURFACE_SEED_COUNT = 24
INTERIOR_SEED_COUNT = 6
SURFACE_SHELL_DEPTH = 0.12
SURFACE_SHELL_BIAS = 1.0
WELD_TOLERANCE = 0.02
MINIMUM_EDGE_LENGTH = 0.01
DUPLICATE_EDGE_TOLERANCE = 0.0005
LATTICE_RELAX_ITERATIONS = 4
LATTICE_RELAX_STRENGTH = 0.35
STRUT_RADIUS = 0.03
NODE_RADIUS_MULTIPLIER = 1.25
STRUT_SIDES = 8
NODE_SUBDIVISIONS = 1
BOUNDARY_CLEANUP_ITERATIONS = 4
BOUNDARY_COMPONENT_MAX_EDGES = 2
STRUT_REMESH_VOXEL_SIZE = 0.0  # 0.0 = auto
STRUT_SMOOTH_ITERATIONS = 4
STRUT_SMOOTH_FACTOR = 0.35
EXPORT_AFTER_GENERATION = False
EXPORT_MODE = 'EVALUATED'  # 'EVALUATED' or 'SOLIDIFY_SHELL'
EXPORT_SHELL_THICKNESS = 0.2
EXPORT_FILEPATH = ""  # blank = current blend directory or Blender temp folder
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
settings.solid_output_mode = SOLID_OUTPUT_MODE
settings.lattice_output_mode = LATTICE_OUTPUT_MODE
settings.sampling_mode = SAMPLING_MODE
settings.seed_count = CELL_COUNT
settings.surface_seed_count = SURFACE_SEED_COUNT
settings.interior_seed_count = INTERIOR_SEED_COUNT
settings.surface_shell_depth = SURFACE_SHELL_DEPTH
settings.surface_shell_bias = SURFACE_SHELL_BIAS
settings.weld_tolerance = WELD_TOLERANCE
settings.minimum_edge_length = MINIMUM_EDGE_LENGTH
settings.duplicate_edge_tolerance = DUPLICATE_EDGE_TOLERANCE
settings.lattice_relax_iterations = LATTICE_RELAX_ITERATIONS
settings.lattice_relax_strength = LATTICE_RELAX_STRENGTH
settings.strut_radius = STRUT_RADIUS
settings.node_radius_multiplier = NODE_RADIUS_MULTIPLIER
settings.strut_sides = STRUT_SIDES
settings.node_subdivisions = NODE_SUBDIVISIONS
settings.boundary_cleanup_iterations = BOUNDARY_CLEANUP_ITERATIONS
settings.boundary_component_max_edges = BOUNDARY_COMPONENT_MAX_EDGES
settings.strut_remesh_voxel_size = STRUT_REMESH_VOXEL_SIZE
settings.strut_smooth_iterations = STRUT_SMOOTH_ITERATIONS
settings.strut_smooth_factor = STRUT_SMOOTH_FACTOR
settings.export_mode = EXPORT_MODE
settings.export_shell_thickness = EXPORT_SHELL_THICKNESS
settings.export_filepath = EXPORT_FILEPATH
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

if result != {'FINISHED'}:
    raise RuntimeError(f"Voronoi generation did not finish successfully: {result}")

if EXPORT_AFTER_GENERATION:
    active_after_generation = bpy.context.view_layer.objects.active
    if active_after_generation is None or active_after_generation.type != 'MESH':
        raise RuntimeError("Export requested, but there is no active mesh object after generation")
    export_result = bpy.ops.object.export_voronoi_active_stl()
    print("Voronoi export result:", export_result)
    if export_result != {'FINISHED'}:
        raise RuntimeError(f"Voronoi export did not finish successfully: {export_result}")
    print("Exported STL:", bpy.context.scene.voronoi_solid_settings.export_filepath)
