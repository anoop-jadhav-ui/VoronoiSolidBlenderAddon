# Voronoi Solid Blender Addon

Project path:
`/Users/anoopjadhav/Documents/vibeCodedProjects/VoronoiSolidBlenderAddon`

This project contains a Blender addon that generates Voronoi-style volumetric cells from any selected closed mesh object.

Files:
- `voronoi_solid_addon/__init__.py` — installable addon
- `run_selected_object.py` — quick runner script for the currently selected object
- `test_voronoi_addon.py` — headless validation script

What it does:
- samples random points inside the selected solid
- now includes a `Lattice Seeds` mode that biases seeds to a shallow shell near the mesh surface
- computes a Voronoi-like clipped cell for each point
- by default joins generated cells into one mesh object so modifiers affect the whole result
- can optionally keep cells as separate mesh objects in a new collection
- optionally shrinks each cell to create visible gaps

Current limitations:
- works best on clean, closed, manifold meshes
- this is a geometry prototype, not a polished production addon yet
- performance drops as cell count rises because each cell is clipped against every other point
- for very thin/complex shapes, increase `sample_attempt_multiplier`
- `Lattice Seeds` is Iteration 1 only: it improves shell-oriented seeding but still outputs clipped Voronoi cells rather than a cleaned strut network

Tested:
- Blender 4.3.0
- cube: 8 cells generated successfully
- UV sphere: 10 cells generated successfully

Headless test command:
```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup --python /Users/anoopjadhav/Documents/vibeCodedProjects/VoronoiSolidBlenderAddon/test_voronoi_addon.py
```

Expected result:
- Blender prints that it generated the cube and sphere cell collections
- exits with code 0

Option 1: Run as an installable addon in Blender
1. Open Blender.
2. Go to Edit > Preferences > Add-ons.
3. Click the dropdown in the top-right and choose Install from Disk if you zip the `voronoi_solid_addon` folder, or copy the folder into your Blender addons directory.
4. Enable `Voronoi Solid Pattern`.
5. Select a closed mesh object in Object Mode.
6. Open the 3D View sidebar with `N`.
7. Open the `Voronoi` tab.
8. Set:
   - `Mode`
   - `Cells`
   - `Random Seed`
   - `Gap`
   - `Sample Attempts x`
   - `Collection`
   - `Join Cells` (enabled by default so one modifier affects the whole result)
9. Click `Generate Voronoi Cells`.

Lattice mode controls:
- `Surface Seeds` — number of shell-oriented seeds near the source surface
- `Interior Seeds` — optional extra seeds inside the volume
- `Shell Depth` — max inward offset from the surface for shell seeds
- `Shell Bias` — higher values keep seeds closer to the outer skin

Option 2: Run the included script directly in Blender
1. Open Blender.
2. Open or create a mesh object.
3. Select the target mesh in Object Mode.
4. Open the Scripting workspace.
5. Open this file:
   `/Users/anoopjadhav/Documents/vibeCodedProjects/VoronoiSolidBlenderAddon/run_selected_object.py`
6. Adjust the values at the top if needed:
   - `GENERATION_MODE`
   - `CELL_COUNT`
   - `SURFACE_SEED_COUNT`
   - `INTERIOR_SEED_COUNT`
   - `SURFACE_SHELL_DEPTH`
   - `SURFACE_SHELL_BIAS`
   - `RANDOM_SEED`
   - `GAP`
   - `ATTEMPT_MULTIPLIER`
   - `KEEP_ORIGINAL`
   - `COLLECTION_NAME`
   - `JOIN_CELLS`
7. Click `Run Script`.
8. Generated cells will appear in a new collection.

Recommended starting values:
- simple object: `CELL_COUNT = 12`
- more detailed breakup: `CELL_COUNT = 20 to 40`
- visible gaps: `GAP = 0.05 to 0.12`
- complex meshes: `ATTEMPT_MULTIPLIER = 80 to 150`

If generation fails:
- make sure the object is a closed mesh
- apply transforms if the mesh has unusual scale
- recalculate normals in Edit Mode
- try reducing `CELL_COUNT`
- increase `ATTEMPT_MULTIPLIER`

Next good improvements:
- blue-noise / Poisson sampling instead of pure random sampling
- boolean pattern carving mode instead of only generating separate cells
- Geometry Nodes-assisted preview workflow
- export helpers for 3D-printable shells or perforated surfaces
