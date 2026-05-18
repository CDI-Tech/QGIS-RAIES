# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# @par CDI-Technologies, Vincent Majorczyk

from qgis.core import *
from qgis.gui import *
from qgis.PyQt.QtCore import *
import processing

from .debug import Debug
from .constraint_item import ConstraintType

## @brief task to create a raser from constraints
#
# # Content
# this class is composed of a list of methods which use basic qgis algorithms adapted to Suricates application
# and automatic traitments of a constraint list.
#
# list of basic algorithms:
# - bufferVector: create a vector layer (.shp) from another with a buffer
# - rasterize: create a raster layer (.tif) from a vector layer
# - proximity: create a raster layer (.tif) from distance of filled zones
# - clip: create a raster layer (.tif) with clipping of a raster layer by another
# - invert: create a raster layer (.sdat: saga library) with inversion of data and no-data cells
# - convertSagaOutput: convert .sdat raster layer to .tif raster layer
# - mergeLayers: merge two layers (.tif): complete no_data cells by content of the second layer
# - normalizeRaster: normalize a raster (.tif)
# - thresholdRaster: binarize raster with a threshold (.tif)
#
# list of advanced algorithms:
# - rasterizeWithBuffer: use methods bufferVector and rasterize (.tif)
# - calculateTheConstraintOfProximity: create a proximity raster with clipping and normalization (.tif)
# - calculateTheConstraintWithConstant: set a value to a raster
#
# # Using
# this class is initialized by four parameters:
# - *contraints* which is the list of contraints used to create raster;
# - *descrition* is the text used to define the task
# - *tmpPath* is the path for temporary files
# - *tmpBaseName* is a part of temporary files associated to this task
#
# ```py
# constraints = list()
# constraints.append(ConstraintItem('path/map.shp', 10000, 80, ConstraintType.Map))
# constraints.append(ConstraintItem('path/input1.shp', 2000, 50, ConstraintType.Repulsive, ConstraintType.Repulsive))
# constraints.append(ConstraintItem('path/input2.shp', 4000, 50, ConstraintType.Excluded, ConstraintType.Included))
# constraints.append(ConstraintItem('path/input3.shp', 8000, 50, ConstraintType.Sanctuarized, ConstraintType.Excluded))
#
# a = SuricatesAlgo(constraints,'test', tmp)
# QgsApplication.taskManager().addTask(a)
# ```
class SuricatesAlgo(QgsTask):
    ## @var constraints
    # list of constraints to compute

    ## @var createdFiles
    # list of created temporary files during the computation

    ## @var suricatesInstance
    # current SuricatesInstance

    ## @var projectName
    # name of the project

    ## @var counter
    # number of filename created (include in the temporary filenames)

    ## @var date
    # date of the creation of the classe (include in the temporary filenames)

    ## @var time
    # time of the creation of the classe (include in the temporary filenames)

    ## @var tmpPath
    # absolute path for temporary files

    ## @var extent
    # boundary box of the current working area

    ## @var maxprogress
    # number of temporary file which must be created during the computation

    ## @var outputs
    # list of important temporary files (rasters of each constrained layer, raster of cumulation of rasters, raster with threshold)

    ## @brief constructor of the task
    # @param constraints list of constraints (ConstraintItem)
    # @param suricatesInstance current SuricatesInstance
    # @param projectName name of the task
    def __init__(self, constraints, projectName, suricatesInstance):
        Debug.begin("SuricatesAlgo::__init__")
        super().__init__(projectName, QgsTask.CanCancel)
        self.constraints = constraints
        self.createdFiles = list()
        self.suricatesInstance = suricatesInstance
        self.projectName = projectName

        self.counter = 0
        self.date = QDate.currentDate().toString("yyMMdd")
        self.time = QTime.currentTime().toString("hhmmss")
        self.createTmpPath()
        self.deleteTmp = False
        Debug.end("SuricatesAlgo::__init__")
        return

    ## @brief create the path to temporary files
    #
    # a folder 'tmp' is created in the QGIS project folder
    def createTmpPath(self):
        Debug.begin("SuricatesAlgo::createTmpPath")
        projectPath = QDir(QgsProject.instance().absolutePath())
        if not projectPath.exists("tmp/"):
            projectPath.mkdir("tmp")
        projectPath.cd("tmp/")
        self.tmpPath = projectPath.absolutePath()
        Debug.end("SuricatesAlgo::createTmpPath")
        return

    ## @brief delete temporary files
    #
    # delete temporary files created during the task
    #
    # @note the *.shp* files are associated to others files which have the same base name but not the same extension: These file are also removed.
    def deleteTmpFile(self):
        Debug.begin("SuricatesAlgo::deleteTmpFile")
        for filename in self.createdFiles:
            info = QFileInfo(filename)
            base = info.baseName()
            dir = QDir(info.absolutePath())

            filter = list()
            filter.append(base + '.*')

            dir.setNameFilters(filter)
            dir.setFilter(QDir.Files | QDir.NoDotAndDotDot | QDir.NoSymLinks)

            fileList = dir.entryInfoList()
            for i in fileList:
                if i.exists():
                    Debug.print("delete " + i.absoluteFilePath())
                    QFile.remove(i.absoluteFilePath())

        self.createdFiles = list()
        Debug.begin("SuricatesAlgo::deleteTmpFile")
        return

    ## @brief delete temporary path
    def deleteAllTmpFile(self):
        Debug.begin("SuricatesAlgo::deleteAllTmpFile")
        QDir(self.tmpPath).removeRecursively()
        self.createTmpPath()
        Debug.begin("SuricatesAlgo::deleteAllTmpFile")
        return

    ## @brief get the main extent of a project as String.
    #
    # this generate a string registred in the attribute SuricatesAlgo.extent used by the method SuricatesAlgo.rasterize
    #
    # @param layerName name of the layer
    # @return the extent formated string: `xMin, xMax, yMin, yMax [CRS]`
    def setExtentString(self, layerName):
        # QgsVectorLayer/QgsRasterLayer cannot be instantiated in a QgsTask worker thread
        # (QGIS 3.40+). Use osgeo.ogr / osgeo.gdal directly — they are thread-safe.
        # WARNING: all layers must be in the same CRS as the project (no reprojection done here).
        from osgeo import ogr, gdal
        BUFFER = 100

        # Try as vector (OGR)
        ds = ogr.Open(layerName)
        if ds is not None:
            lyr = ds.GetLayer(0)
            xMin, xMax, yMin, yMax = lyr.GetExtent()  # (xMin, xMax, yMin, yMax)
            src_srs = lyr.GetSpatialRef()
            src_crs_id = src_srs.GetAuthorityName(None) + ':' + src_srs.GetAuthorityCode(None) if src_srs else '?'
            project_crs_id = QgsProject.instance().crs().authid()
            if src_crs_id != project_crs_id:
                Debug.error(
                    "setExtentString: CRS mismatch! Layer=" + src_crs_id + " Project=" + project_crs_id + " => " + layerName)
            ds = None
            project_crs = QgsProject.instance().crs()
            rect = QgsRectangle(xMin - BUFFER, yMin - BUFFER, xMax + BUFFER, yMax + BUFFER)
            self.extent = QgsReferencedRectangle(rect, project_crs)
            Debug.warning("setExtentString: extent=" + str(self.extent))
            return self.extent

        # Try as raster (GDAL)
        ds = gdal.Open(layerName)
        if ds is not None:
            gt = ds.GetGeoTransform()
            xMin = gt[0]
            yMax = gt[3]
            xMax = xMin + gt[1] * ds.RasterXSize
            yMin = yMax + gt[5] * ds.RasterYSize
            ds = None
            project_crs = QgsProject.instance().crs()
            rect = QgsRectangle(xMin - BUFFER, yMin - BUFFER, xMax + BUFFER, yMax + BUFFER)
            self.extent = QgsReferencedRectangle(rect, project_crs)
            Debug.warning("setExtentString: extent=" + str(self.extent))
            return self.extent

        Debug.error("setExtentString: impossible d'ouvrir le fichier: " + str(layerName))
        self.extent = None
        return self.extent

    ## @brief create a random name for temporary file
    # @param extension of the file (example: .sdat, .tif)
    # @return a filename
    #
    # this is also used to count and display progress of the task
    #
    def getNewFileName(self, extension):
        self.counter = self.counter + 1
        self.setProgress(100.0 * float(self.counter) / (self.maxprogress + 1))
        # QUuid.toString() produces {xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx} with curly braces.
        # GDAL on Windows does not support curly braces in file paths and silently fails
        # to create or open the file. Strip the braces with [1:-1].
        uuid = QUuid.createUuid().toString()[1:-1]
        filename = QDir(self.tmpPath).filePath(
            '{}-{}{:02d}-{}{}'.format(self.date, self.time, self.counter, uuid, extension))
        self.createdFiles.append(filename)
        return filename

    ## @brief create a new vector layer with buffer from a vector layer
    # @param vectorName name of the input vector file
    # @param outputName name of the output vector file
    # @param distance distance around the area delimited by the vector layer
    # @return the name of the output raster file
    # @note return value may be different from the property *outputName* if the value of *outputName* is None
    def bufferVector(self, vectorName, outputName, distance):
        Debug.begin("SuricatesAlgo:bufferVector")
        if (outputName == None): outputName = self.getNewFileName('.shp')
        result = processing.run("native:buffer", {'INPUT': vectorName,
                                                  'DISTANCE': distance,
                                                  'SEGMENTS': 5,
                                                  'DISSOLVE': False,
                                                  'END_CAP_STYLE': 0,
                                                  'JOIN_STYLE': 0,
                                                  'MITER_LIMIT': 2,
                                                  'OUTPUT': outputName})
        print('bufferVector ' + outputName)
        Debug.end("SuricatesAlgo:bufferVector")
        return outputName

    ## @brief rasterize vector layer
    # @param vectorName name of the input vector file
    # @param outputName name of the output raster file
    # @return the name of the output raster file
    # @note return value may be different from the property *outputName* if the value of *outputName* is `TEMPORARY_OUTPUT` or None
    def rasterize(self, vectorName, outputName):
        if (outputName == None): outputName = self.getNewFileName('.tif')
        Debug.warning("rasterize: self.extent type=" + str(type(self.extent)) + " value=" + str(self.extent))
        result = processing.run("gdal:rasterize", {'BURN': 0,
                                                   'DATA_TYPE': 5,
                                                   'EXTENT': self.extent,
                                                   'EXTRA': '',
                                                   'FIELD': None,
                                                   'HEIGHT': 100,
                                                   'INIT': None,
                                                   'INPUT': vectorName,
                                                   'INVERT': False,
                                                   'NODATA': -9999,
                                                   'OPTIONS': '',
                                                   'OUTPUT': outputName,
                                                   'UNITS': 1,
                                                   'WIDTH': 100})
        print('rasterize ' + result['OUTPUT'])
        return result['OUTPUT']

    ## @brief rasterize vector layer with buffer
    # @param vectorName name of the input vector file
    # @param outputName name of the output raster file
    # @param buffer size of the buffer
    # @param saveExtent save the current extent
    # @return the name of the output raster file
    # @note return value may be different from the property *outputName* if the value of *outputName* is `TEMPORARY_OUTPUT` or None
    def rasterizeWithBuffer(self, vectorName, outputName, buffer, saveExtent):
        Debug.begin("SuricatesAlgo:rasterizeWithBuffer")
        if (buffer > 0):
            tmp = self.bufferVector(vectorName, None, buffer)
            if (saveExtent): self.setExtentString(tmp)
            r = self.rasterize(tmp, outputName)
            Debug.end("SuricatesAlgo:rasterizeWithBuffer (1)")
            return r
        else:
            if (saveExtent): self.setExtentString(vectorName)
            r = self.rasterize(vectorName, outputName)
            Debug.end("SuricatesAlgo:rasterizeWithBuffer (2)")
            return r

    ## @brief proximity vector layer
    # @param rasterName name of the input raster file
    # @param outputName name of the output raster file
    # @return the name of the output raster file
    def proximity(self, rasterName, outputName):
        if (outputName == None): outputName = self.getNewFileName('.tif')
        # EXTRA '-srcnodata -9999' tells gdal_proximity to ignore input nodata pixels
        # so they don't act as distance sources and corrupt the gradient.
        # VALUES='0' : compute distance to pixels with value 0 (the burned constraint cells).
        result = processing.run("gdal:proximity", {'BAND': 1,
                                                   'DATA_TYPE': 5,
                                                   'EXTRA': '',
                                                   'INPUT': rasterName,
                                                   'MAX_DISTANCE': 0,
                                                   'NODATA': -9999,
                                                   'OPTIONS': '',
                                                   'OUTPUT': outputName,
                                                   'REPLACE': 0,
                                                   'UNITS': 1,
                                                   'VALUES': '0'})
        Debug.print('proximity: ' + result['OUTPUT'])
        return result['OUTPUT']

    ## @brief clip a raster layer
    # @param rasterName name of the input raster file
    # @param clipRasterName name of the input raster file used to clip
    # @param outputName name of the output raster file
    # @return the name of the output raster file
    def clip(self, rasterName, clipRasterName, outputName):
        if (outputName == None): outputName = self.getNewFileName('.tif')
        Debug.print("clip-start: raster=" + rasterName + " clip=" + clipRasterName)
        # In QGIS 3.40 gdal_calc, formula 'B' does not propagate nodata from A.
        # Use explicit numpy.where to mask B by A's nodata.
        result = processing.run("gdal:rastercalculator",
                                {'BAND_A': 1, 'BAND_B': 1, 'BAND_C': -1, 'BAND_D': -1, 'BAND_E': -1, 'BAND_F': -1,
                                 'EXTRA': '',
                                 'FORMULA': 'numpy.where(A == -9999, -9999, B)',
                                 'INPUT_A': clipRasterName,
                                 'INPUT_B': rasterName,
                                 'INPUT_C': None, 'INPUT_D': None, 'INPUT_E': None, 'INPUT_F': None,
                                 'NO_DATA': -9999,
                                 'OPTIONS': '',
                                 'OUTPUT': outputName,
                                 'RTYPE': 5})
        Debug.print('clip: ' + result['OUTPUT'])
        return result['OUTPUT']

    ## @brief invert data/nodata cells of a raster layer
    # @param rasterName name of the input raster file
    # @param outputName name of the output raster file
    # @return the name of the output raster file
    # @note saga:invertdatanodata removed in QGIS 3.40 - replaced by gdal:rastercalculator
    def invert(self, rasterName, outputName):
        # gdal_calc cannot transform nodata pixels into values (nodata always propagates).
        # Use gdal+numpy directly: pixels with data (==0) become nodata, nodata becomes 0.
        from osgeo import gdal
        import numpy as np

        if (outputName == None): outputName = self.getNewFileName('.tif')

        ds_in = gdal.Open(rasterName)
        if ds_in is None:
            Debug.error("invert: impossible d'ouvrir " + str(rasterName))
            return None

        band = ds_in.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        if nodata is None: nodata = -9999.0
        data = band.ReadAsArray().astype(np.float32)

        # Invert: where data has a value (!=nodata) → set to nodata
        #         where data is nodata              → set to 0
        result_data = np.where(data == nodata, np.float32(0.0), np.float32(nodata))

        driver = gdal.GetDriverByName('GTiff')
        ds_out = driver.Create(outputName, ds_in.RasterXSize, ds_in.RasterYSize, 1, gdal.GDT_Float32)
        ds_out.SetGeoTransform(ds_in.GetGeoTransform())
        ds_out.SetProjection(ds_in.GetProjection())
        band_out = ds_out.GetRasterBand(1)
        band_out.SetNoDataValue(nodata)
        band_out.WriteArray(result_data)
        band_out.FlushCache()
        ds_out = None
        ds_in = None

        Debug.print('invert: ' + outputName)
        return outputName

    ## @brief convert sdat raster layer to tif
    # @param rasterName name of the input raster file
    # @param outputName name of the output raster file
    # @return the name of the output raster file
    def convertSagaOutput(self, rasterName, outputName):
        if (outputName == None): outputName = self.getNewFileName('.tif')
        result = processing.run("gdal:translate", {'COPY_SUBDATASETS': False,
                                                   'DATA_TYPE': 6,
                                                   'EXTRA': '',
                                                   'INPUT': rasterName,
                                                   'NODATA': -9999,
                                                   'OPTIONS': '',
                                                   'OUTPUT': outputName,
                                                   'TARGET_CRS': None})
        print('convertSagaOutput' + result['OUTPUT'])
        return result['OUTPUT']

    ## @brief merge two raster layer (complete no-data celles by the values of the second raster)
    # @param rasterName1 name of the input raster file
    # @param rasterName2 name of the input raster file to merge
    # @param outputName name of the output raster file
    # @return the name of the output raster file
    def mergeLayers(self, rasterName1, rasterName2, outputName):
        # Use gdal+numpy to merge: rasterName1 takes priority where it has data,
        # rasterName2 fills in where rasterName1 is nodata.
        # gdal:merge can mishandle 0 values if nodata detection is inconsistent.
        from osgeo import gdal
        import numpy as np

        if (outputName == None): outputName = self.getNewFileName('.tif')

        ds1 = gdal.Open(rasterName1)
        ds2 = gdal.Open(rasterName2)
        if ds1 is None or ds2 is None:
            Debug.error("mergeLayers: impossible d'ouvrir un des rasters")
            return None

        band1 = ds1.GetRasterBand(1)
        band2 = ds2.GetRasterBand(1)
        nd1 = band1.GetNoDataValue() if band1.GetNoDataValue() is not None else -9999.0
        nd2 = band2.GetNoDataValue() if band2.GetNoDataValue() is not None else -9999.0
        nodata = -9999.0

        data1 = band1.ReadAsArray().astype(np.float32)
        data2 = band2.ReadAsArray().astype(np.float32)

        # Merge: raster1 wins where it has data; raster2 fills the rest
        merged = np.where(data1 != nd1, data1, np.where(data2 != nd2, data2, np.float32(nodata)))

        driver = gdal.GetDriverByName('GTiff')
        ds_out = driver.Create(outputName, ds1.RasterXSize, ds1.RasterYSize, 1, gdal.GDT_Float32)
        ds_out.SetGeoTransform(ds1.GetGeoTransform())
        ds_out.SetProjection(ds1.GetProjection())
        band_out = ds_out.GetRasterBand(1)
        band_out.SetNoDataValue(nodata)
        band_out.WriteArray(merged)
        band_out.FlushCache()
        ds_out = None
        ds1 = None
        ds2 = None

        Debug.print('mergeLayers: ' + outputName)
        return outputName

    ## @brief normalize raster between min and max
    # @param rasterName name of the input raster file
    # @param outputName name of the output raster file
    # @param invert invert min (0) and max (coef)
    # @param coef maximum value
    # @return the name of the output raster file
    def normalizeRaster(self, rasterName, outputName, invert, coef):
        if (outputName == None): outputName = self.getNewFileName('.tif')

        # QgsRasterLayer cannot be instantiated in a QgsTask worker thread (QGIS 3.40+).
        # Use gdal directly to compute band statistics — it is thread-safe.
        from osgeo import gdal
        import sys
        import numpy as np

        ds = gdal.Open(rasterName)
        if ds is None:
            Debug.error("normalizeRaster: impossible d'ouvrir " + str(rasterName))
            return None

        band = ds.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        # ReadAsArray then mask nodata to compute real min/max
        data = band.ReadAsArray().astype(float)
        ds = None
        if nodata is not None:
            data = np.where(data == nodata, np.nan, data)
        valid = data[~np.isnan(data)]
        if valid.size == 0:
            Debug.error("normalizeRaster: raster entièrement nodata, skipping")
            return None
        min = float(np.min(valid))
        max = float(np.max(valid))

        Debug.warning("normalizeRaster: min=" + str(min) + " max=" + str(max))
        if max - min == 0:
            if min != 0:
                min = 0
            else:
                max = 1
        Debug.warning("normalizeRaster: normalized min=" + str(min) + " max=" + str(max))

        formula = '(A-{})/({}-{})'.format(min, max, min)
        if (invert): formula = '1-' + formula
        formula = '(' + formula + ')*' + str(coef)

        result = processing.run("gdal:rastercalculator",
                                {'BAND_A': 1, 'BAND_B': -1, 'BAND_C': -1, 'BAND_D': -1, 'BAND_E': -1, 'BAND_F': -1,
                                 'EXTRA': '',
                                 'FORMULA': formula,
                                 'INPUT_A': rasterName,
                                 'INPUT_B': None, 'INPUT_C': None, 'INPUT_D': None, 'INPUT_E': None, 'INPUT_F': None,
                                 'NO_DATA': -9999,
                                 'OPTIONS': '',
                                 'OUTPUT': outputName,
                                 'RTYPE': 5})
        print('normalizeRaster ' + result['OUTPUT'])
        return result['OUTPUT']

    ## @brief binarize raster using threashold
    # @param rasterName name of the input raster file
    # @param outputName name of the output raster file
    # @param coef threshold value
    # @return the name of the output raster file
    def thresholdRaster(self, rasterName, outputName, coef):
        # Replace gdal:rastercalculator to avoid UnicodeDecodeError on French Windows
        # (gdal_calc.bat emits CP1252 warnings that QGIS 3.40 tries to decode as UTF-8).
        # Use gdal+numpy directly — thread-safe and encoding-independent.
        from osgeo import gdal, osr
        import numpy as np

        if (outputName == None): outputName = self.getNewFileName('.tif')

        ds_in = gdal.Open(rasterName)
        if ds_in is None:
            Debug.error("thresholdRaster: impossible d'ouvrir " + str(rasterName))
            return None

        band = ds_in.GetRasterBand(1)
        data = band.ReadAsArray().astype(np.float32)
        nodata = band.GetNoDataValue()
        if nodata is None: nodata = -9999.0

        # Keep values below threshold, set nodata above
        result_data = np.where((data != nodata) & (data < coef), data, np.float32(nodata))

        driver = gdal.GetDriverByName('GTiff')
        ds_out = driver.Create(outputName, ds_in.RasterXSize, ds_in.RasterYSize, 1, gdal.GDT_Float32)
        ds_out.SetGeoTransform(ds_in.GetGeoTransform())
        ds_out.SetProjection(ds_in.GetProjection())
        band_out = ds_out.GetRasterBand(1)
        band_out.SetNoDataValue(nodata)
        band_out.WriteArray(result_data)
        band_out.FlushCache()
        ds_out = None
        ds_in = None

        Debug.print('thresholdRaster: ' + outputName)
        return outputName

    ## @brief calculate constraints with proximity
    # @param layerName : rasterized layer where data cells are the source of the distance calculation and the no-data cells are the area to fill with distance value
    # @param invertedLayerName: same as layerName but invert no-data and data
    # @param mapName: rasterized layer which keep where data cells corresponds to the global area to fill
    # @param outputName: output rasterized data
    # @param invert: if False then near cells use the minimum value; if True then near cells use the maximum value
    # @param coef: coef to apply at the output raster
    # @return the name of the output raster file
    def calculateTheConstraintOfProximity(self, layerName, invertedLayerName, mapName, outputName, invert, coef):
        Debug.warning("proximity: layerName=" + str(layerName))
        Debug.warning("proximity: invertedLayerName=" + str(invertedLayerName))
        Debug.warning("proximity: mapName=" + str(mapName))
        RasterProximity = self.proximity(layerName, None)
        Debug.warning("proximity result=" + str(RasterProximity))
        RasterProximityClip1 = self.clip(RasterProximity, mapName, None)
        Debug.warning("clip1 result=" + str(RasterProximityClip1))
        RasterProximityClip2 = self.clip(RasterProximityClip1, invertedLayerName, None)
        Debug.warning("clip2 result=" + str(RasterProximityClip2))
        return self.normalizeRaster(RasterProximityClip2, None, invert, coef)

    ## @brief calculate constraints with constant
    # @param layerName rasterized input layer
    # @param mapName rasterized layer which keep where data cells corresponds to the global area to fill
    # @param outputName output rasterized data
    # @param coef value of the raster layer
    # @return the name of the output raster file
    def calculateTheConstraintWithConstant(self, layerName, mapName, outputName, coef):
        if (outputName == None): outputName = self.getNewFileName('.tif')
        # Apply constant value (coef) to the area defined by layerName, clipped by mapName.
        # Formula uses A (layerName) to define the area and B (mapName) to clip.
        # In QGIS 3.40+, all declared BAND inputs must point to existing files.
        # We use only INPUT_A and INPUT_B with a formula that actually references them.
        result = processing.run("gdal:rastercalculator",
                                {'BAND_A': 1, 'BAND_B': 1, 'BAND_C': -1, 'BAND_D': -1, 'BAND_E': -1, 'BAND_F': -1,
                                 'EXTRA': '',
                                 'FORMULA': 'numpy.where((A == 0) & (B != -9999), ' + str(coef) + ', -9999)',
                                 'INPUT_A': layerName,
                                 'INPUT_B': mapName,
                                 'INPUT_C': None, 'INPUT_D': None, 'INPUT_E': None, 'INPUT_F': None,
                                 'NO_DATA': -9999,
                                 'OPTIONS': '',
                                 'OUTPUT': outputName,
                                 'RTYPE': 5})
        print('calculateTheConstraintWithConstant ' + result['OUTPUT'])
        return result['OUTPUT']

    ## @brief cumulate values of raster layers
    # @param listLayerName rasterized layers to merge
    # @param outputName output rasterized data
    # @return the name of the output raster file
    def cummulateLayers(self, listLayerName, outputName):
        Debug.begin("SuricateAlgo::cummulateLayers (nb layer:" + str(len(listLayerName)) + ")")
        count = len(listLayerName)

        if (count == 0):
            Debug.end("SuricateAlgo::cummulateLayers (1)")
            return None

        baseLayer = listLayerName[0]
        result = None
        for i in range(1, count, 5):
            A = baseLayer
            print('cummulateLayers-A ' + A)
            B = C = D = E = F = G = None
            formula = 'A'
            if (i < count):
                B = listLayerName[i]
                formula += '+B'
                print('cummulateLayers-B ' + B)
            if (i + 1 < count):
                C = listLayerName[i + 1]
                formula += '+C'
                print('cummulateLayers-C ' + C)
            if (i + 2 < count):
                D = listLayerName[i + 2]
                formula += '+D'
                print('cummulateLayers-D ' + D)
            if (i + 3 < count):
                E = listLayerName[i + 3]
                formula += '+E'
                print('cummulateLayers-E ' + E)
            if (i + 4 < count):
                F = listLayerName[i + 4]
                formula += '+F'
                print('cummulateLayers-F ' + F)

            if (i + 5 < count or outputName == None):
                tmp = self.getNewFileName('.tif')
            else:
                tmp = outputName

            # Replace simple addition (A+B+C) with nodata-aware sum:
            # treat nodata (-9999) as 0 so cells covered by only some layers still accumulate.
            def nd(var):
                return 'numpy.where({}==-9999, 0, {})'.format(var, var)

            formula_nd = nd('A')
            if B: formula_nd += '+' + nd('B')
            if C: formula_nd += '+' + nd('C')
            if D: formula_nd += '+' + nd('D')
            if E: formula_nd += '+' + nd('E')
            if F: formula_nd += '+' + nd('F')

            result = processing.run("gdal:rastercalculator",
                                    {'BAND_A': 1, 'BAND_B': 1 if B else -1, 'BAND_C': 1 if C else -1,
                                     'BAND_D': 1 if D else -1, 'BAND_E': 1 if E else -1, 'BAND_F': 1 if F else -1,
                                     'EXTRA': '',
                                     'FORMULA': formula_nd,
                                     'INPUT_A': A, 'INPUT_B': B, 'INPUT_C': C, 'INPUT_D': D, 'INPUT_E': E, 'INPUT_F': F,
                                     'NO_DATA': -9999,
                                     'OPTIONS': '',
                                     'OUTPUT': tmp,
                                     'RTYPE': 5})
            baseLayer = result['OUTPUT']
            print('cummulateLayers-tmp:' + baseLayer)
            print(formula)
        print('cummulateLayers-result' + baseLayer)

        Debug.end("SuricateAlgo::cummulateLayers (2)")
        return baseLayer

    ## @brief calculate the number of layers to create the wished layer specific to the ContraintType
    # @param constraintType constraint type
    # @return the number of layers to create
    def calculateConstraintSteps(self, constraintType):
        if constraintType == ConstraintType.Attractive or constraintType == ConstraintType.Repulsive:
            return 4
        if constraintType == ConstraintType.Included or constraintType == ConstraintType.Excluded:
            return 1
        return 0

    ## @brief calculate the number of layers to create the list of constraint `self.constraints`
    # @return number of layer to create
    def calculateMaxProgress(self):
        self.maxprogress = 0
        for constraint in self.constraints:
            if constraint.typeIn == ConstraintType.Sanctuarized and constraint.typeOut == ConstraintType.Sanctuarized:
                continue

            # rasterizewithbuffer
            if (constraint.buffer == 0):
                self.maxprogress += 1
            else:
                self.maxprogress += 2
            # invert
            if (constraint.typeIn != ConstraintType.Map):
                self.maxprogress += 2

            # specific computations
            self.maxprogress += self.calculateConstraintSteps(constraint.typeIn)
            self.maxprogress += self.calculateConstraintSteps(constraint.typeOut)

            # merge layer
            if constraint.typeIn != ConstraintType.Sanctuarized and constraint.typeOut != ConstraintType.Sanctuarized:
                self.maxprogress += 1

        # merge layers
        for i in range(1, len(self.constraints), 5):
            self.maxprogress += 1

        # normalize & threadhols process
        self.maxprogress += 1

        return self.maxprogress

    ## @brief create raster depending of the constraint type
    # @param constraintType the constraint type
    # @param priority max value of the output raster
    # @param rasterMap raster layer which represents the global area
    # @param rasterLayer raster layer which respresents zones to consider
    # @param rasterLayer_1 inverse data/no-data of the rasterLayer
    # @return the layer name created
    ## @brief compute raster for a zone (inside or outside the constraint geometry)
    # @param zone 'inside' or 'outside'
    # @param constraintType the type applied to this zone
    # rasterLayer   : 0 inside constraint geometry, nodata outside
    # rasterLayer_1 : 0 outside constraint geometry (inverse), nodata inside
    #
    # Sanctuarized = nodata  (transparent, forbidden)
    # Excluded     = priority (high value)
    # Included     = 0       (low value)
    # The mask used depends on the zone:
    #   inside  -> rasterLayer   (0 where constraint is)
    #   outside -> rasterLayer_1 (0 where constraint is NOT)
    def computeRaster(self, zone, constraintType, priority, rasterMap, rasterLayer, rasterLayer_1):
        # For proximity types, the clip mask depends on the zone:
        #   inside  -> clip by rasterLayer   (keep gradient inside  the constraint)
        #   outside -> clip by rasterLayer_1 (keep gradient outside the constraint)

        if constraintType == ConstraintType.Repulsive:
            # mask = rasterLayer if zone == 'inside' else rasterLayer_1
            if zone == "inside":
                tmp = rasterLayer
                rasterLayer = rasterLayer_1
                rasterLayer_1 = tmp
            return self.calculateTheConstraintOfProximity(rasterLayer, rasterLayer_1, rasterMap, None, True, priority)
        if constraintType == ConstraintType.Attractive:
            if zone == "inside":
                tmp = rasterLayer
                rasterLayer = rasterLayer_1
                rasterLayer_1 = tmp
            # mask = rasterLayer if zone == 'inside' else rasterLayer_1
            return self.calculateTheConstraintOfProximity(rasterLayer, rasterLayer_1, rasterMap, None, False, priority)

        # For constant types, select the right mask for this zone
        mask = rasterLayer if zone == 'inside' else rasterLayer_1

        if constraintType == ConstraintType.Sanctuarized:
            return None  # nodata everywhere in this zone
        if constraintType == ConstraintType.Excluded:
            return self.calculateTheConstraintWithConstant(mask, rasterMap, None, priority)
        if constraintType == ConstraintType.Included:
            return self.calculateTheConstraintWithConstant(mask, rasterMap, None, 0)
        return None

    ## @brief check that all constraint layers share the same CRS as the map layer,
    #  and that this CRS uses metres (not degrees).
    # @return True if all checks pass, False otherwise (errors logged)
    def checkCRS(self):
        from osgeo import ogr, osr

        # Find the map layer (typeIn == Map)
        map_constraint = None
        for c in self.constraints:
            if c.typeIn == ConstraintType.Map:
                map_constraint = c
                break
        if map_constraint is None:
            Debug.error("checkCRS: aucune couche de type Map trouvée")
            return False

        # Read map CRS via OGR
        ds = ogr.Open(map_constraint.name)
        if ds is None:
            Debug.error("checkCRS: impossible d'ouvrir la couche Map: " + map_constraint.name)
            return False
        map_srs = ds.GetLayer(0).GetSpatialRef()
        ds = None
        if map_srs is None:
            Debug.error("checkCRS: CRS indéfini sur la couche Map: " + map_constraint.name)
            return False

        map_auth = (map_srs.GetAuthorityName(None) or '?') + ':' + (map_srs.GetAuthorityCode(None) or '?')

        # Check that map CRS uses metres, not degrees
        units = map_srs.GetLinearUnitsName() if not map_srs.IsGeographic() else 'degree'
        if map_srs.IsGeographic():
            Debug.error("checkCRS: la couche Map est en coordonnées géographiques (degrés): "
                        + map_auth + " => " + map_constraint.name
                        + " — reprojeter en CRS projeté (mètres) avant de continuer.")
            return False

        # Check all other layers
        ok = True
        report_lines = ["checkCRS: bilan des CRS (référence Map = " + map_auth + "):"]
        for c in self.constraints:
            ds = ogr.Open(c.name)
            if ds is None:
                report_lines.append("  [ERREUR] impossible d'ouvrir: " + c.name)
                ok = False
                continue
            lyr_srs = ds.GetLayer(0).GetSpatialRef()
            ds = None
            if lyr_srs is None:
                report_lines.append("  [ERREUR] CRS indéfini: " + c.name)
                ok = False
                continue
            lyr_auth = (lyr_srs.GetAuthorityName(None) or '?') + ':' + (lyr_srs.GetAuthorityCode(None) or '?')
            match = lyr_srs.IsSame(map_srs)
            status = "OK" if match else "MISMATCH"
            report_lines.append("  [" + status + "] " + lyr_auth + " => " + c.name)
            if not match:
                ok = False

        # Always log the full report
        for line in report_lines:
            if "MISMATCH" in line or "ERREUR" in line:
                Debug.error(line)
            else:
                Debug.warning(line)

        return ok

    ## @brief method used when task started: create raster which corresponds to the list of constraints
    # @return true if done
    def run(self):
        Debug.begin("SuricatesAlgo:run")

        # --- CRS pre-check ---
        if not self.checkCRS():
            Debug.error("run: vérification CRS échouée — calcul annulé.")
            Debug.end("SuricatesAlgo:run (error CRS)")
            return False

        self.calculateMaxProgress()

        rasterMap = None
        threshold = 0.5
        Debug.print("nb constraints:" + str(len(self.constraints)))
        # search map
        for constraint in self.constraints:
            Debug.print("It is the map? " + constraint.name)
            if constraint.typeIn == ConstraintType.Map:
                rasterMap = self.rasterizeWithBuffer(constraint.name, None, constraint.buffer, True)
                threshold = float(constraint.priority) / 100.0
                self.createdFiles.remove(rasterMap)
                Debug.print("- Yes")
                Debug.print("- result: " + rasterMap)
                Debug.print("- threshold: " + str(threshold))

        if (rasterMap == None):
            Debug.end("SuricatesAlgo:run (error 1)")
            return False

        layers = list()  # list of layer to merge

        # for each constraint create raster layer
        self.outputs = dict()

        for constraint in self.constraints:
            Debug.print("Operate " + constraint.name)

            if constraint.typeIn == ConstraintType.Sanctuarized and constraint.typeOut == ConstraintType.Sanctuarized:
                Debug.print("- Skip")
                continue
            if constraint.typeIn == ConstraintType.Map:
                Debug.print("- Skip")
                continue

            rasterLayer = self.rasterizeWithBuffer(constraint.name, None, constraint.buffer, False)
            rasterLayer_1 = self.invert(rasterLayer, None)

            # Protect rasterLayer and rasterLayer_1 from deleteTmpFile() during this iteration.
            # In QGIS 3.40+, all intermediate files must exist for the duration of all
            # gdal:rastercalculator calls that reference them.
            protected = []
            if rasterLayer in self.createdFiles:
                self.createdFiles.remove(rasterLayer)
                protected.append(rasterLayer)
            if rasterLayer_1 in self.createdFiles:
                self.createdFiles.remove(rasterLayer_1)
                protected.append(rasterLayer_1)

            print("begin raster out")
            outside = self.computeRaster('outside', constraint.typeOut, constraint.priority, rasterMap, rasterLayer,
                                         rasterLayer_1)
            print("begin raster in")
            inside = self.computeRaster('inside', constraint.typeIn, constraint.priority, rasterMap, rasterLayer,
                                        rasterLayer_1)
            print("end")

            if inside is None and outside is None:
                Debug.warning(
                    "computeRaster: inside et outside sont None pour " + constraint.name + " — contrainte ignorée")
                self.createdFiles.extend(protected)
                continue
            elif inside is None:
                outputlayer = outside
            elif outside is None:
                outputlayer = inside
            else:
                outputlayer = self.mergeLayers(inside, outside, None)

            bn = QFileInfo(constraint.name).baseName()
            self.outputs[bn] = outputlayer
            layers.append(outputlayer)

            # Re-add protected files so deleteTmpFile() can clean them up
            self.createdFiles.extend(protected)

            if outputlayer in self.createdFiles:
                self.createdFiles.remove(outputlayer)

            if self.deleteTmp:
                self.deleteTmpFile()

        rasterCumul = self.cummulateLayers(layers, None)
        rasterCumulFinal = self.normalizeRaster(rasterCumul, None, False, 1)
        if rasterCumulFinal is None:
            Debug.error(
                "run: normalizeRaster returned None (raster cumulatif vide ou tout-nodata) — thresholdRaster ignoré")
            self.outputs["raster"] = None
            self.outputs["threshold(" + str(threshold) + ")"] = None
            return False
        rasterCumulFinal2 = self.thresholdRaster(rasterCumulFinal, None, threshold)

        self.outputs["raster"] = rasterCumulFinal
        self.outputs["threshold(" + str(threshold) + ")"] = rasterCumulFinal2

        self.setProgress(100)
        Debug.end("SuricatesAlgo:run")
        return True

    ## @brief executed when task is finished
    ## @param result is the return of the method Suricates.run
    ##
    ## - display a message to announce success or error during task;
    ## - copy many temporary files (layer raster, normalized cumulation of raster and a thresholded version of this one;
    ## - display a message bow which asks if temporary files must be removed;
    def finished(self, result):
        Debug.begin("SuricatesAlgo::finished")
        if result:
            self.suricatesInstance.iface.messageBar().pushMessage("Success", "Rasters Created", level=Qgis.Success)
        else:
            self.suricatesInstance.iface.messageBar().pushMessage("Error", "Rasters Creation failled",
                                                                  level=Qgis.Critical)

        if result:
            root = self.suricatesInstance.getProject(self.projectName)

            for name, filename in self.outputs.items():
                dir = QDir(QgsProject.instance().absolutePath())
                filename2 = QFileInfo(filename).fileName()

                filename3 = dir.filePath(name + "-" + filename2)

                QFile.copy(filename, filename3)

                layer_shp = QgsRasterLayer(filename3, name)
                QgsProject.instance().addMapLayer(layer_shp, False)
                root.addLayer(layer_shp)

        self.suricatesInstance.tasks.remove(self)

        # ◙if self.deleteTmp:
        #    self.deleteAllTmpFile()

        Debug.end("SuricatesAlgo::finished")
