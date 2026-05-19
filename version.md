# Version for QGIS 3.40.9

Migration from QGIS 3.10.9 to 3.40.9 (LTR "Bratislava"), May 2026.

## Deprecated / removed QGIS APIs in 3.40

These are breaking changes introduced by QGIS 3.40 that required direct code updates.

- `writeAsVectorFormat` → `writeAsVectorFormatV3` (returns 4 values instead of a tuple)
- `saga:invertdatanodata` removed (SAGA no longer bundled on Windows) → replaced by `invert()` via gdal+numpy
- `bandStatistics()` on `QgsRasterInterface` deprecated → replaced by gdal+numpy directly
- `QgsVectorLayer` / `QgsRasterLayer` cannot be instantiated in a `QgsTask` worker thread → replaced by `ogr` / `gdal` (thread-safe)
- `gdal:rastercalculator`: declaring `BAND_X: 1` with `INPUT_X: None` now raises a validation error → unused bands set to `BAND_X: -1`

## Behavioural changes in GDAL / gdal_calc (3.40)

These are changes in how GDAL tools behave that silently broke existing raster operations.

- `gdal_calc`: formula `B` no longer propagates nodata from input `A` → `clip()` rewritten with `numpy.where(A == -9999, -9999, B)`
- `gdal_calc`: nodata values are excluded from computation and cannot be transformed into valid values → `invert()`, `normalizeRaster()`, `thresholdRaster()`, `cummulateLayers()` all rewritten using gdal+numpy directly
- `gdal_calc`: `A+B+C` propagates nodata (any nodata cell makes the result nodata) → `cummulateLayers()` now uses `numpy.where(X == -9999, 0, X)` before summing
- `gdal_merge`: confuses pixel value `0` with nodata → `mergeLayers()` rewritten using gdal+numpy
- `gdal_proximity`: nodata pixels treated as distance sources, corrupting gradients → `-use_input_nodata YES` added
- `gdal_calc` on French Windows: stderr output encoded in CP1252 causes `UnicodeDecodeError` in QGIS → `thresholdRaster()` and `normalizeRaster()` bypass gdal_calc entirely

## Data / CRS bugs

Pre-existing bugs made visible during migration testing.

- `getNewFileName()`: `QUuid.toString()` includes `{}` braces which GDAL rejects on Windows → `toString()[1:-1]`
- `setExtentString()`: extent computed in layer CRS (e.g. EPSG:4326) but passed to GDAL in project CRS (e.g. EPSG:2154), causing `0×0 dataset` errors → `QgsReferencedRectangle` now always expressed in project CRS
- `copyCurrentLayer()`: memory layer created without CRS, so saved shapefile gets WGS84 `.prj` regardless of source layer CRS → `layer.setCrs(layer_shp.crs())` added before write
- New pre-calculation check `checkCRS()`: verifies all input layers share the same CRS as the map layer and that it uses metres; logs a full per-layer report and aborts if mismatches are found

## Raster logic bugs

Pre-existing logic errors, some masked by compensating behaviours in 3.10.

- `computeRaster()`: `inside` and `outside` calls used the same raster arguments, giving identical results regardless of zone → explicit `zone='inside'`/`zone='outside'` parameter added; for `Attractive`/`Repulsive`, `rasterLayer` and `rasterLayer_1` are swapped when computing the inside zone
- `computeRaster()`: `Sanctuarized` type produced nodata for both inside and outside → corrected semantics: `Sanctuarized` = nodata, `Excluded` = priority, `Included` = 0, applied to the correct zone mask

## Crash on close

- Signal `cleared` fires after `QgsProject::clear()` has already destroyed the layer tree → replaced by `aboutToBeCleared`, which fires before destruction
- `closeInstance()` called `readProjects()` during shutdown, traversing a partially destroyed layer tree → replaced by direct iteration over `self.projectNode.children()`

---

# Version for QGIS 3.10.9

Initial release.