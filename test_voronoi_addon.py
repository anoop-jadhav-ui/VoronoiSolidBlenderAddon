import json
import math
import os
import sys

import bpy
import bmesh

PROJECT_DIR = "/Users/anoopjadhav/Documents/vibeCodedProjects/VoronoiSolidBlenderAddon"
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import voronoi_solid_addon

if getattr(voronoi_solid_addon, "__file__", "").startswith(PROJECT_DIR) is False:
    raise RuntimeError(f"Loaded wrong addon module: {getattr(voronoi_solid_addon, '__file__', None)}")


results = []


def reset_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    for collection in list(bpy.data.collections):
        if collection.users == 0:
            bpy.data.collections.remove(collection)


def object_volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    volume = abs(bm.calc_volume()) if len(bm.faces) >= 4 else 0.0
    bm.free()
    return volume


def run_case(kind, seed_count, gap, join_cells=None, apply_wireframe=False):
    reset_scene()

    if kind.startswith("cube"):
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
        src = bpy.context.active_object
    elif kind.startswith("sphere"):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.25, segments=32, ring_count=16, location=(0, 0, 0))
        src = bpy.context.active_object
    else:
        raise ValueError(kind)

    settings = bpy.context.scene.voronoi_solid_settings
    settings.seed_count = seed_count
    settings.random_seed = 7
    settings.gap = gap
    settings.sample_attempt_multiplier = 100
    settings.keep_original = True
    settings.collection_name = f"{kind}_cells"
    if join_cells is not None:
        settings.join_cells = join_cells

    bpy.context.view_layer.objects.active = src
    src.select_set(True)

    result = bpy.ops.object.generate_voronoi_solid_cells()
    if 'FINISHED' not in result:
        raise RuntimeError(f"Operator failed for {kind}: {result}")

    generated = [c for c in bpy.data.collections if c.name.startswith(settings.collection_name)]
    if not generated:
        raise RuntimeError(f"No collection created for {kind}")

    collection = max(generated, key=lambda c: len(c.objects))
    mesh_objects = [obj for obj in collection.objects if obj.type == 'MESH']
    volumes = [object_volume(obj) for obj in mesh_objects]

    join_expected = settings.join_cells if join_cells is None else join_cells
    expected_objects = 1 if join_expected else seed_count
    if len(mesh_objects) != expected_objects:
        raise RuntimeError(f"Expected {expected_objects} mesh objects for {kind}, got {len(mesh_objects)}")
    if any(v <= 0.0 for v in volumes):
        raise RuntimeError(f"Non-positive cell volume found for {kind}: {volumes}")

    if apply_wireframe:
        target = mesh_objects[0]
        mod = target.modifiers.new(name="WireframeTest", type='WIREFRAME')
        mod.thickness = 0.03
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated = target.evaluated_get(depsgraph)
        temp_mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=depsgraph)
        try:
            if len(temp_mesh.vertices) == 0:
                raise RuntimeError(f"Wireframe modifier evaluation produced empty mesh for {kind}")
        finally:
            bpy.data.meshes.remove(temp_mesh)

    results.append(
        {
            "case": kind,
            "cells": len(mesh_objects),
            "join_cells": join_expected,
            "wireframe_tested": apply_wireframe,
            "min_volume": round(min(volumes), 6),
            "max_volume": round(max(volumes), 6),
            "total_volume": round(sum(volumes), 6),
        }
    )


voronoi_solid_addon.register()
run_case("cube_default_joined", seed_count=8, gap=0.05)
run_case("sphere", seed_count=10, gap=0.08)
run_case("cube_joined", seed_count=8, gap=0.05, join_cells=True, apply_wireframe=True)
run_case("cube_separate", seed_count=6, gap=0.05, join_cells=False)
print(json.dumps(results, indent=2))
voronoi_solid_addon.unregister()
