## @file SuricatesApp.py
#
# @date 2020-2021
# @version 1
# @author Vincent MAJORCZYK
# @copyright Copyright 2020-2022 CDI-Technologies (France), all right reserved.
# @par License:
# code released under GNU General Public License v3
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# @par CDI-Technologies:
# *23 avenue de la créativité, 59650 Villeneuve d'Ascq, France*
# https://cditech.fr/raies/

from qgis.core import *
from qgis.gui import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import *
from enum import Enum
import processing
import copy

import os

## @brief toolbox for debug functions
#
# this class aims to debug in the context of the python editor of QGis: there are not evolved tools to facilitate this task.
#
# developer can add calls static method of this class to display in the console the access to methods or functions:
# ```py
# def dummyFunction():
#     Debug.begin("dummyFunction")
#     i = 1 + 1
#     if i != 2:
#          Debug.end("dummyFunction")
#          return
#     Debug.print( str(i) + "==2" )
#     Debug.end("dummyFunction")
#     return
# ```
#
# the console output:
# ```
# dummyFunction begin
#  2==2
# dummyFunction end
# ```
#
# in the case of functions or methods which calls others functions or method using this system, a indent is used:
# ```
# dummyFunction begin
#  dummyFunction2 begin
#   dummyFunction3 begin
#    it says: helloword!
#   dummyFunction3 end
#  dummyFunction2 end
# dummyFunction end
# ```
class Debug():
    ## @brief display debug text is true
    enabled = False

    ## @brief indentation variable
    __indentDebug = 0;

    ## @brief display text (start of a function) if debug mode
    @staticmethod
    def begin(text):
        if Debug.enabled:
            for i in range(0, Debug.__indentDebug):
                text = " " + text;
            print(text + " begin")
            Debug.__indentDebug = Debug.__indentDebug + 1

    ## @brief display text if debug mode
    @staticmethod
    def print(text):
        if Debug.enabled:
            for i in range(0, Debug.__indentDebug):
                text = " " + text;
            print(text)

    ## @brief display text (end of a function) if debug mode
    @staticmethod
    def end(text):
        if Debug.enabled:
            Debug.__indentDebug = Debug.__indentDebug - 1
            for i in range(0, Debug.__indentDebug):
                text = " " + text;
            print(text + " end")

## @brief corresponds to the differents constraint types
#
# These constraint types are applyed to inside and outside of the area delimited by layer. There are 5 constraint types, so 25 possible combinations
# ![constraint combinations](assets\constraints.svg)
class ConstraintType(Enum):
    ## @brief exclude the area
    Sanctuarized=0
    ## @brief near location to the area is prefered
    Attractive=1
    ## @brief far location to the area is prefered
    Repulsive=2
    ## @brief inside the area
    Included=3
    ## @brief uside the area
    Excluded=4
    ## @brief global working area of the project
    Map=5

## @brief structure for constraint information
#
# This structure is an interface between the file of the layer *config_project*, the ConstraintWidget (user interface) and the SuricatesAlgo (task)
#
# There is minor difference between the requierement of the SuricatesAlgo and the other (*config_project* and ConstraintWidget).
# This concerns the attribute name:
# - for SuricatesAlgo: the name must be the absolute path of the layer
# - for the others: the name is the one used in the layer file *config_project*, that means the name of the layer in the panel of layers.
#
# typeIn and typeOut are the constraint types applyed to the layer
# If typeIn is set to the special type ConstraintType.Map, then typeOut is ignored in the process and the priority attribute contains the threshold parameter instead (thresholf used on the cumulation of rasters)
class ConstraintItem:
    ## @var name
    # name of the layer: either the absolute path of the layer for the SuricatesAlgo, or the name displayed in the panel of layers

    ## @var buffer
    # distance considered from layer items

    ## @var priority
    # priority of the current layer.
    # This set a weight to each layers of the list of constrained layers to define the importance of the layer in the computation result.
    #
    # In the case of a layer with the special type ConstraintType.Map, the attribute is used to store the threshold value.

    ## @var typeIn
    # constraint type used inside the zone of the layer (ConstraintType)

    ## @var typeOut
    # typeOut constraint type used outside the zone of the layer (ConstraintType)

    ## @var exists
    # used to determine if the layer associated to the constraint already exists.

    ## @brief constructor
    # @param name name of the layer
    # @param buffer distance considered from layer items
    # @param priority priority of the current layer
    # @param typeIn constraint type used inside the zone of the layer
    # @param typeOut constraint type used outside the zone of the layer
    def __init__(self, name, buffer = 50, priority = 100, typeIn = ConstraintType.Sanctuarized, typeOut = ConstraintType.Sanctuarized):
        self.name = name
        self.buffer = buffer
        self.priority = priority
        self.typeIn = typeIn
        self.typeOut = typeOut
        self.exists = True

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
        return;

    ## @brief create the path to temporary files
    #
    # a folder 'tmp' is created in the QGIS project folder
    def createTmpPath(self):
        Debug.begin("SuricatesAlgo::createTmpPath")
        projectPath = QDir(QgsProject.instance().absolutePath())
        if not projectPath.exists("tmp/"):
            projectPath.mkdir("tmp");
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

            dir.setNameFilters(filter);
            dir.setFilter(QDir.Files | QDir.NoDotAndDotDot | QDir.NoSymLinks);

            fileList = dir.entryInfoList();
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
        rlayer = QgsVectorLayer(layerName, "tmp")
        if(not rlayer.isValid()):
           rlayer = QgsRasterLayer(layerName, "tmp")

        if(not rlayer.isValid()):
           self.extent = None
        else: self.extent = str(rlayer.extent().xMinimum()-100) + ',' + str(rlayer.extent().xMaximum()+100) + ',' + str(rlayer.extent().yMaximum()-100)	 + ',' + str(rlayer.extent().yMinimum()+100) + ' [' + rlayer.crs().authid() + ']'
        return self.extent

    ## @brief create a random name for temporary file
    # @param extension of the file (example: .sdat, .tif)
    # @return a filename
    #
    # this is also used to count and display progress of the task
    #
    def getNewFileName(self, extension):
        self.counter = self.counter + 1
        self.setProgress(100.0 * float(self.counter) / (self.maxprogress+1))
        filename = QDir(self.tmpPath).filePath('{}-{}{:02d}-{}{}'.format(self.date, self.time, self.counter, QUuid.createUuid().toString(), extension))
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
        if(outputName == None) : outputName = self.getNewFileName('.shp')
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
        if(outputName == None) : outputName = self.getNewFileName('.tif')
        result = processing.run("gdal:rasterize", { 'BURN' : 0,
                'DATA_TYPE' : 5,
                'EXTENT' : self.extent,
                'EXTRA' : '',
                'FIELD' : None,
                'HEIGHT' : 100,
                'INIT' : None,
                'INPUT' : vectorName,
                'INVERT' : False,
                'NODATA' : -9999,
                'OPTIONS' : '',
                'OUTPUT' : outputName,
                'UNITS' : 1,
                'WIDTH' : 100 })
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
        if(buffer > 0):
            tmp = self.bufferVector(vectorName, None, buffer)
            if(saveExtent): self.setExtentString(tmp)
            r = self.rasterize(tmp, outputName)
            Debug.end("SuricatesAlgo:rasterizeWithBuffer (1)")
            return r
        else:
            if(saveExtent): self.setExtentString(vectorName)
            r = self.rasterize(vectorName, outputName)
            Debug.end("SuricatesAlgo:rasterizeWithBuffer (2)")
            return r

    ## @brief proximity vector layer
    # @param rasterName name of the input raster file
    # @param outputName name of the output raster file
    # @return the name of the output raster file
    def proximity(self, rasterName, outputName):
        if(outputName == None) : outputName = self.getNewFileName('.tif')
        result = processing.run("gdal:proximity", { 'BAND' : 1,
              'DATA_TYPE' : 5,
              'EXTRA' : '',
              'INPUT' : rasterName,
              'MAX_DISTANCE' : 0,
              'NODATA' : -9999,
              'OPTIONS' : '',
              'OUTPUT' : outputName,
              'REPLACE' : 0,
              'UNITS' : 1,
              'VALUES' : '0, 1' })
        print('proximity ' + result['OUTPUT']);
        return result['OUTPUT']

    ## @brief clip a raster layer
    # @param rasterName name of the input raster file
    # @param clipRasterName name of the input raster file used to clip
    # @param outputName name of the output raster file
    # @return the name of the output raster file
    def clip(self, rasterName, clipRasterName, outputName):
        if(outputName == None) : outputName = self.getNewFileName('.tif')
        print("clip-start" + rasterName + " " + clipRasterName + " " + outputName)
        result = processing.run("gdal:rastercalculator", { 'BAND_A' : 1, 'BAND_B' : 1, 'BAND_C' : -1, 'BAND_D' : -1, 'BAND_E' : -1, 'BAND_F' : -1,
                'EXTRA' : '',
                'FORMULA' : 'B',
                'INPUT_A' : clipRasterName,
                'INPUT_B' : rasterName,
                'INPUT_C' : None, 'INPUT_D' : None, 'INPUT_E' : None, 'INPUT_F' : None,
                'NO_DATA' : -9999,
                'OPTIONS' : '',
                'OUTPUT' : outputName,
                'RTYPE' : 5 })
        print('clip ' + result['OUTPUT']);
        return result['OUTPUT']

    ## @brief invert data/nodata cells of a	 raster layer
    # @param rasterName name of the input raster file
    # @param outputName name of the output raster file
    # @return the name of the output raster file
    def invert(self, rasterName, outputName):
        tmpName = self.getNewFileName('.sdat')
        if(outputName == None) : outputName = self.getNewFileName('.tif')
        result = processing.run('saga:invertdatanodata', { 'INPUT': rasterName, 'OUTPUT' : tmpName } )
        print('invert ' + result['OUTPUT']);
        return self.convertSagaOutput( result['OUTPUT'], outputName )

    ## @brief convert sdat raster layer to tif
    # @param rasterName name of the input raster file
    # @param outputName name of the output raster file
    # @return the name of the output raster file
    def convertSagaOutput(self, rasterName, outputName):
        if(outputName == None) : outputName = self.getNewFileName('.tif')
        result = processing.run("gdal:translate", { 'COPY_SUBDATASETS' : False,
                'DATA_TYPE' : 6,
                'EXTRA' : '',
                'INPUT' : rasterName,
                'NODATA' : -9999,
                'OPTIONS' : '',
                'OUTPUT' : outputName,
                'TARGET_CRS' : None } )
        print('convertSagaOutput' + result['OUTPUT']);
        return result['OUTPUT']

    ## @brief merge two raster layer (complete no-data celles by the values of the second raster)
    # @param rasterName1 name of the input raster file
    # @param rasterName2 name of the input raster file to merge
    # @param outputName name of the output raster file
    # @return the name of the output raster file
    def mergeLayers(self, rasterName1, rasterName2, outputName):
        if(outputName == None) : outputName = self.getNewFileName('.tif')
        result = processing.run("gdal:merge", { 'DATA_TYPE' : 5, 'EXTRA' : '',
                'INPUT' : [rasterName1,rasterName2],
                'NODATA_INPUT' : -9999,
                'NODATA_OUTPUT' : -9999,
                'OPTIONS' : '',
                'OUTPUT' : outputName,
                'PCT' : False,
                'SEPARATE' : False } )
        print('mergeLayers' + result['OUTPUT']);
        return result['OUTPUT']

    ## @brief normalize raster between min and max
    # @param rasterName name of the input raster file
    # @param outputName name of the output raster file
    # @param invert invert min (0) and max (coef)
    # @param coef maximum value
    # @return the name of the output raster file
    def normalizeRaster(self, rasterName, outputName, invert, coef):
        if(outputName == None) : outputName = self.getNewFileName('.tif')

        layer = QgsRasterLayer(rasterName, "tmp")
        if(not layer.isValid()):
           return None

        provider = layer.dataProvider()

        stats = provider.bandStatistics(1, QgsRasterBandStats.All, layer.extent(), 0)
        min = stats.minimumValue
        max = stats.maximumValue
        print("s" + str(min) + " " + str(max))
        if max-min == 0:
            if min != 0: min = 0
            else: max = 1
        print("e" + str(min) + " " + str(max))

        formula = '(A-{})/({}-{})'.format(min,max,min)
        if(invert): formula = '1-' + formula
        formula = '(' + formula + ')*' + str(coef)

        result = processing.run("gdal:rastercalculator", { 'BAND_A' : 1, 'BAND_B' : 1, 'BAND_C' : -1, 'BAND_D' : -1, 'BAND_E' : -1, 'BAND_F' : -1,
                'EXTRA' : '',
                'FORMULA' : formula,
                'INPUT_A' : rasterName,
                'INPUT_B' : None,'INPUT_C' : None, 'INPUT_D' : None, 'INPUT_E' : None, 'INPUT_F' : None,
                'NO_DATA' : -9999,
                'OPTIONS' : '',
                'OUTPUT' : outputName,
                'RTYPE' : 5 })
        print('normalizeRaster ' + result['OUTPUT']);
        return result['OUTPUT']

    ## @brief binarize raster using threashold
    # @param rasterName name of the input raster file
    # @param outputName name of the output raster file
    # @param coef threshold value
    # @return the name of the output raster file
    def thresholdRaster(self, rasterName, outputName, coef):
        if(outputName == None) : outputName = self.getNewFileName('.tif')

        formula = '(A<{0})*A+(A>={1})*-9999'
        print("formula")
        print(formula)
        print(coef)
        formula = formula.format(coef,coef)
        print(formula)

        result = processing.run("gdal:rastercalculator", { 'BAND_A' : 1, 'BAND_B' : 1, 'BAND_C' : -1, 'BAND_D' : -1, 'BAND_E' : -1, 'BAND_F' : -1,
                'EXTRA' : '',
                'FORMULA' : formula,
                'INPUT_A' : rasterName,
                'INPUT_B' : None,'INPUT_C' : None, 'INPUT_D' : None, 'INPUT_E' : None, 'INPUT_F' : None,
                'NO_DATA' : -9999,
                'OPTIONS' : '',
                'OUTPUT' : outputName,
                'RTYPE' : 5 })
        print('thresholdRaster ' + result['OUTPUT']);
        return result['OUTPUT']

    ## @brief calculate constraints with proximity
    # @param layerName : rasterized layer where data cells are the source of the distance calculation and the no-data cells are the area to fill with distance value
    # @param invertedLayerName: same as layerName but invert no-data and data
    # @param mapName: rasterized layer which keep where data cells corresponds to the global area to fill
    # @param outputName: output rasterized data
    # @param invert: if False then near cells use the minimum value; if True then near cells use the maximum value
    # @param coef: coef to apply at the output raster
    # @return the name of the output raster file
    def calculateTheConstraintOfProximity(self, layerName, invertedLayerName, mapName, outputName, invert, coef):
        RasterProximity = self.proximity(layerName, None)
        RasterProximityClip1 = self.clip(RasterProximity,mapName,None)
        RasterProximityClip2 = self.clip(RasterProximityClip1,invertedLayerName,None)
        return self.normalizeRaster(RasterProximityClip2, None, invert, coef)


    ## @brief calculate constraints with constant
    # @param layerName rasterized input layer
    # @param mapName rasterized layer which keep where data cells corresponds to the global area to fill
    # @param outputName output rasterized data
    # @param coef value of the raster layer
    # @return the name of the output raster file
    def calculateTheConstraintWithConstant(self, layerName, mapName, outputName, coef):
        if(outputName == None) : outputName = self.getNewFileName('.tif')
        result = processing.run("gdal:rastercalculator", { 'BAND_A' : 1, 'BAND_B' : 1, 'BAND_C' : -1, 'BAND_D' : -1, 'BAND_E' : -1, 'BAND_F' : -1,
                'EXTRA' : '',
                'FORMULA' : str(coef),
                'INPUT_A' : layerName,
                'INPUT_B' : mapName,
                'INPUT_C' : None, 'INPUT_D' : None, 'INPUT_E' : None, 'INPUT_F' : None,
                'NO_DATA' : -9999,
                'OPTIONS' : '',
                'OUTPUT' : outputName,
                'RTYPE' : 5 })
        print('calculateTheConstraintWithConstant ' + result['OUTPUT']);
        return result['OUTPUT']

    ## @brief cumulate values of raster layers
    # @param listLayerName rasterized layers to merge
    # @param outputName output rasterized data
    # @return the name of the output raster file
    def cummulateLayers(self, listLayerName, outputName):
        Debug.begin("SuricateAlgo::cummulateLayers (nb layer:" + str(len(listLayerName)) + ")")
        count = len(listLayerName)

        if(count == 0):
            Debug.end("SuricateAlgo::cummulateLayers (1)")
            return None;

        baseLayer = listLayerName[0]
        result = None
        for i in range(1, count, 5):
            A = baseLayer
            print('cummulateLayers-A ' + A)
            B = C = D = E = F = G = None
            formula = 'A'
            if(i < count):
                B = listLayerName[i]
                formula += '+B'
                print('cummulateLayers-B ' + B)
            if(i+1 < count):
                C = listLayerName[i+1]
                formula += '+C'
                print('cummulateLayers-C ' + C)
            if(i+2 < count):
                D = listLayerName[i+2]
                formula += '+D'
                print('cummulateLayers-D ' + D)
            if(i+3 < count):
                E = listLayerName[i+3]
                formula += '+E'
                print('cummulateLayers-E ' + E)
            if(i+4 < count):
                F = listLayerName[i+4]
                formula += '+F'
                print('cummulateLayers-F ' + F)

            if(i+5 < count or outputName == None): tmp = self.getNewFileName('.tif')
            else: tmp = outputName
            result = processing.run("gdal:rastercalculator", { 'BAND_A' : 1, 'BAND_B' : 1, 'BAND_C' : 1, 'BAND_D' : 1, 'BAND_E' : 1, 'BAND_F' : 1,
                    'EXTRA' : '',
                    'FORMULA' : formula,
                    'INPUT_A' : A, 'INPUT_B' : B,'INPUT_C' : C, 'INPUT_D' : D, 'INPUT_E' : E, 'INPUT_F' : F,
                    'NO_DATA' : -9999,
                    'OPTIONS' : '',
                    'OUTPUT' : tmp,
                    'RTYPE' : 5 })
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
            if(constraint.buffer == 0): self.maxprogress += 1
            else: self.maxprogress += 2
            # invert
            if(constraint.typeIn != ConstraintType.Map):
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
    def computeRaster(self, constraintType, priority, rasterMap, rasterLayer, rasterLayer_1):
        if constraintType == ConstraintType.Repulsive:
            return self.calculateTheConstraintOfProximity(rasterLayer, rasterLayer_1, rasterMap, None, True, priority)
        if constraintType == ConstraintType.Attractive:
            return self.calculateTheConstraintOfProximity(rasterLayer, rasterLayer_1, rasterMap, None, False, priority)
        if constraintType == ConstraintType.Excluded:
            return self.calculateTheConstraintWithConstant(rasterLayer_1,rasterMap,None,priority)
        if constraintType == ConstraintType.Included:
            return self.calculateTheConstraintWithConstant(rasterLayer_1,rasterMap,None,0)
        return None

    ## @brief method used when task started: create raster which corresponds to the list of constraints
    # @return true if done
    def run(self):
        Debug.begin("SuricatesAlgo:run")
        
        self.calculateMaxProgress()

        rasterMap = None
        threshold = 0.5
        Debug.print("nb constraints:" + str(len(self.constraints)))
        # search map
        for constraint in self.constraints:
            Debug.print("It is the map? " + constraint.name)
            if constraint.typeIn == ConstraintType.Map:
                rasterMap = self.rasterizeWithBuffer(constraint.name, None, constraint.buffer, True)
                threshold = float(constraint.priority)/100.0
                self.createdFiles.remove(rasterMap)
                Debug.print("- Yes")
                Debug.print("- result: " + rasterMap)
                Debug.print("- threshold: " + str(threshold))

        if(rasterMap == None):
            Debug.end("SuricatesAlgo:run (error 1)")
            return False

        layers = list() # list of layer to merge

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

            print("begin raster out")
            outside = self.computeRaster(constraint.typeOut, constraint.priority, rasterMap, rasterLayer, rasterLayer_1) # create layer for inside area
            print("begin raster in")
            inside = self.computeRaster(constraint.typeIn, constraint.priority, rasterMap, rasterLayer_1, rasterLayer) # create layer for outside area
            print("end")
            
            if(inside == None):
                outputlayer = outside
            elif(outside == None):
                outputlayer = inside
            else:
                outputlayer = self.mergeLayers(inside, outside, None)

            bn = QFileInfo(constraint.name).baseName()
            self.outputs[bn] = outputlayer
            layers.append(outputlayer)
            
            print("before remove" + str( len(self.createdFiles)))
            self.createdFiles.remove(outputlayer)
            print("before remove" + str( len(self.createdFiles)))
            
            if self.deleteTmp:
                self.deleteTmpFile()
            print("after remove" + str( len(self.createdFiles)))

        rasterCumul = self.cummulateLayers(layers, None)
        rasterCumulFinal = self.normalizeRaster(rasterCumul,None,False,1)
        rasterCumulFinal2 = self.thresholdRaster(rasterCumulFinal, None, threshold)


        self.outputs["raster"] = rasterCumulFinal
        self.outputs["threshold("+ str(threshold) + ")"] = rasterCumulFinal2

        self.setProgress(100)
        Debug.end("SuricatesAlgo:run")
        return True

    ## @brief executed when task is finished
    ## @param result is the return of the method Suricates.run
    ##
    ## - display a message to announce success or error during task;
    ## - copy many temporary files (layer raster, normalized cumulation of raster and a thresholded version of this one;
    ## - display a message bow which asks if temporary files must be removed;
    def finished(self,result):
        Debug.begin("SuricatesAlgo::finished")
        if result: self.suricatesInstance.iface.messageBar().pushMessage("Success", "Rasters Created", level=Qgis.Success)
        else: self.suricatesInstance.iface.messageBar().pushMessage("Error", "Rasters Creation failled", level=Qgis.Critical)

        if result:
            root = self.suricatesInstance.getProject(self.projectName);

            for name, filename in self.outputs.items():

                dir = QDir(QgsProject.instance().absolutePath())
                filename2 = QFileInfo(filename).fileName()

                filename3 = dir.filePath(name + "-" + filename2)

                QFile.copy(filename, filename3)

                layer_shp = QgsRasterLayer(filename3, name)
                QgsProject.instance().addMapLayer(layer_shp, False)
                root.addLayer(layer_shp)

        self.suricatesInstance.tasks.remove( self )
        
        #◙if self.deleteTmp:
        #    self.deleteAllTmpFile()

        Debug.end("SuricatesAlgo::finished")

## @brief widget which contains parameter interface for constrains configuration
#
# this interface contains:
# - a list interface to add, remove and select a constraints;
# - a group with radiobox and field to select type and parameter of the selected constraint (from the list interface);
# - a field for threshold selection and a button to start computation;
#
# ![User interface classes imbrication](assets\GuiStructure.png)
#
# ![User interface: list of constrained layers](assets\UserManual_ListOfConstraints.png)
#
# ![User interface: constraints configuration](assets\UserManual_ConstraintConfiguration.png)
class ConstraintWidget(QWidget):
    ## @var suricates
    # current SuricatesInstance

    ## @var w_listConstraints
    # QTreeWidget for a list of constrained layers

    ## @var w_buttonAdd
    # QPushButton for adding new constrained layer

    ## @var w_buttonDel
    # QPushButton for deletion of the selected constrained layer

    ## @var w_nearInRB
    # QRadioButton for the 'Near' option for the 'Inside' area

    ## @var w_farInRB
    # QRadioButton for the 'Far' option for the 'Inside' area

    ## @var w_inInRB
    # QRadioButton for the 'In' option for the 'Inside' area

    ## @var w_outInRB
    # QRadioButton for the 'Out' option for the 'Inside' area

    ## @var w_excludeInRB
    # QRadioButton for the 'Exclude' option for the 'Inside' area

    ## @var w_nearOutRB
    # QRadioButton for the 'Near' option for the 'Outside' area

    ## @var w_farOutRB
    # QRadioButton for the 'Far' option for the 'Outside' area

    ## @var w_inOutRB
    # QRadioButton for the 'In' option for the 'Outside' area

    ## @var w_outOutRB
    # QRadioButton for the 'Out' option for the 'Outside' area

    ## @var w_excludeOutRB
    # QRadioButton for the 'Exclude' option for the 'Outside' area

    ## @var w_buffer
    # QSpinBox for the buffer (distance around layer items)

    ## @var w_priority
    # QSpinBox for the priority/weight of the raster

    ## @var w_save
    # QPushButton to save the parameters of the constrained layer

    ## @var w_compute
    # QPushButton to run computation
    # @see SuricatesAlgo.run()

    ## @var w_threshold
    # QSpinBox for the threshold used on the cumulation raster

    ## @var currentProject
    # name of the current project (string)

    ## @brief constructor of the widget
    # @param parent parent widget (QWidget)
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        Debug.begin("ConstraintWidget::__init__")

        self.suricates = parent.suricates

        selectl = QVBoxLayout(self)
        selectl2 = QHBoxLayout(self)
        self.w_buttonAdd = QPushButton("Add",self)
        self.w_buttonDel = QPushButton("Del",self)
        selectl2.addWidget(self.w_buttonAdd)
        selectl2.addWidget(self.w_buttonDel)
        selectl.addLayout(selectl2)

        self.w_listConstraints	= QTreeWidget(self)
        self.w_listConstraints.setHeaderLabels(["Name","Inside","Outside", "Distance","Weight"])
        selectl.addWidget(self.w_listConstraints)

        groupw = QGroupBox("Constraints on selected layer:",self)
        groupl = QVBoxLayout()
        groupc = QHBoxLayout()
        groupc1 = QVBoxLayout()
        groupc2 = QVBoxLayout()

        self.w_farInRB = QRadioButton("Repulsive",self)
        self.w_nearInRB = QRadioButton("Attractive", self)
        self.w_inInRB = QRadioButton("Included",self)
        self.w_outInRB = QRadioButton("Excluded", self)
        self.w_outInRB.setToolTip("only applies to one selected layer whereas ")
        self.w_excludeInRB = QRadioButton("Sanctuarized", self)
        self.w_excludeInRB.setToolTip("applies accross all project layers.")
      
        self.w_farOutRB = QRadioButton("Repulsive",self)
        self.w_nearOutRB = QRadioButton("Attractive", self)
        self.w_inOutRB = QRadioButton("Included",self)
        self.w_outOutRB = QRadioButton("Excluded", self)
        self.w_outOutRB.setToolTip("only applies to one selected layer whereas ")
        self.w_excludeOutRB = QRadioButton("Sanctuarized", self)
        self.w_excludeOutRB.setToolTip("applies accross all project layers.")

        groupclw = QGroupBox("Inside the object")
        groupc1.addWidget(self.w_farInRB)
        groupc1.addWidget(self.w_nearInRB)
        groupc1.addWidget(self.w_inInRB)
        groupc1.addWidget(self.w_outInRB)
        groupc1.addWidget(self.w_excludeInRB)

        groupc2.addWidget(self.w_farOutRB)
        groupc2.addWidget(self.w_nearOutRB)
        groupc2.addWidget(self.w_inOutRB)
        groupc2.addWidget(self.w_outOutRB)
        groupc2.addWidget(self.w_excludeOutRB)

        groupc1b = QGroupBox("Inside:")
        groupc1b.setToolTip("Contraint inside the object")
        groupc1b.setLayout(groupc1)
        groupc2b = QGroupBox("Outside:")
        groupc2b.setToolTip("Contraint on the outside of object")
        groupc2b.setLayout(groupc2)

        groupc.addWidget(groupc1b)
        groupc.addWidget(groupc2b)
        groupl.addLayout(groupc)

        formL = QFormLayout()
        self.w_buffer = QSpinBox()
        self.w_buffer.setMinimum(0)
        self.w_buffer.setMaximum(30000)
        self.w_buffer.setSingleStep(100)
        self.w_buffer.setSuffix(" m")

        self.w_priority = QSpinBox()
        self.w_priority.setMinimum(1)
        self.w_priority.setMaximum(10)
        self.w_priority.setSingleStep(1)

        formL.addRow("Neighborhood distance (m)", self.w_buffer)
        formL.addRow("Layer’s weight (1-10)", self.w_priority)

        self.w_save = QPushButton("Save")
        layout = QHBoxLayout()
        layout.addStretch()
        layout.addWidget(self.w_save)

        self.w_compute = QPushButton("Compute")

        self.w_threshold = QSpinBox()
        self.w_threshold.setMinimum(0)
        self.w_threshold.setMaximum(100)
        self.w_threshold.setSingleStep(10)
        thresholdform = QFormLayout()
        thresholdform.addRow("Final Accepted Constraint (0<FAC>100)", self.w_threshold)

        groupl.addLayout(formL)
        groupl.addLayout(layout)
        groupw.setLayout(groupl)
        selectl.addWidget(groupw)
        selectl.addLayout(thresholdform)
        selectl.addWidget(self.w_compute)
        self.setLayout(selectl)

        self.w_buttonAdd.clicked.connect(self.onAddNewConstraint)
        self.w_buttonDel.clicked.connect(self.onDeleteConstraint)
        self.w_listConstraints.itemSelectionChanged.connect(self.onSelectedConstraintChanged)
        self.w_save.clicked.connect(self.onSave)
        self.w_compute.clicked.connect(self.onCompute)
        self.w_threshold.valueChanged.connect(self.onChangeThreshold)

        Debug.end("ConstraintWidget::__init__")

    ## @brief set the current project and update the list of constraints
    # @param name of the current project
    def setProject(self, name):
        if name != None: Debug.begin("ConstraintWidget::setProject:" + name)
        else: Debug.begin("ConstraintWidget::setProject: (Empty project)")

        self.currentProject = name
        self.updateProject()
        Debug.end("ConstraintWidget::setProject")

    ## @brief update the list of constraints
    def updateProject(self):
        Debug.begin("ConstraintWidget::updateProject")
        self.w_save.setEnabled(False)

        self.setOptionEnabled(False)
        if self.currentProject == None:
            self.setEnabled(False)
            Debug.end("ConstraintWidget::updateProject (Empty project)")
            return;
        else: self.setEnabled(True)

        project = self.suricates.getProject(self.currentProject)
        if project == None:
            Debug.end("ConstraintWidget::updateProject (Error 1)")
            return
        Debug.print("selection:" + project.name())
        configLayer = self.suricates.getConfig(project)
        if configLayer == None:
            Debug.end("ConstraintWidget::updateProject (Error 2)")
            return;

        constraintsList = self.suricates.getConstraintsFromConfig(project, configLayer)

        self.w_listConstraints.clear()
        # current code here
        for constraint in constraintsList:
            twi = QTreeWidgetItem([constraint.name, SuricatesInstance.ConstraintTypeToString(constraint.typeIn), SuricatesInstance.ConstraintTypeToString(constraint.typeOut), str(constraint.buffer), str(constraint.priority)])
            if not constraint.exists:
                twi.setIcon(0,QIcon(":/images/themes/default/mActionRemove.svg"))
            self.w_listConstraints.addTopLevelItem(twi)
            if constraint.typeIn == ConstraintType.Map:
                Debug.print("threshold:" + str(constraint.priority) + " " + str(constraint.priority))
                self.w_threshold.blockSignals(True)
                self.w_threshold.setValue(constraint.priority)
                self.w_threshold.blockSignals(False)

        Debug.end("ConstraintWidget::updateProject")

    ## @brief update the properties of the selected constraint
    # @param name name of the constraint
    def updateOption(self, name):
        Debug.begin("ConstraintWidget::updateOption")
        project = self.suricates.getProject(self.currentProject)
        if project == None:
            Debug.end("ConstraintWidget::updateOption (Error 1)")
            return
        Debug.print("selection:" + project.name())
        configLayer = self.suricates.getConfig(project)
        if configLayer == None:
            Debug.end("ConstraintWidget::updateOption (Error 2)")
            return;

        constraintsList = self.suricates.getConstraintsFromConfig(project, configLayer)

        current = None
        for constraint in constraintsList:
            if constraint.name == name:
                current = constraint

        if current == None:
            setOptionEnabled(False)
            Debug.end("ConstraintWidget::updateOption (Error 3)")
            return;

        self.w_save.setEnabled(True)

        if current.typeIn == ConstraintType.Map:
            self.w_nearInRB.setEnabled(False)
            self.w_farInRB.setEnabled(False)
            self.w_inInRB.setEnabled(False)
            self.w_outInRB.setEnabled(False)
            self.w_excludeInRB.setEnabled(False)
            
            self.w_nearInRB.setChecked(False)
            self.w_farInRB.setChecked(False)
            self.w_inInRB.setChecked(False)
            self.w_outInRB.setChecked(False)
            self.w_excludeInRB.setChecked(False)

            self.w_nearOutRB.setEnabled(False)
            self.w_farOutRB.setEnabled(False)
            self.w_inOutRB.setEnabled(False)
            self.w_outOutRB.setEnabled(False)
            self.w_excludeOutRB.setEnabled(False)

            self.w_nearOutRB.setChecked(False)
            self.w_farOutRB.setChecked(False)
            self.w_inOutRB.setChecked(False)
            self.w_outOutRB.setChecked(False)
            self.w_excludeOutRB.setChecked(False)

            self.w_buffer.setEnabled(True)
            self.w_priority.setEnabled(False)
        else:
            self.setOptionEnabled(True)
            if current.typeIn == ConstraintType.Attractive: self.w_nearInRB.setChecked(True)
            elif current.typeIn == ConstraintType.Repulsive: self.w_farInRB.setChecked(True)
            elif current.typeIn == ConstraintType.Included: self.w_inInRB.setChecked(True)
            elif current.typeIn == ConstraintType.Excluded: self.w_outInRB.setChecked(True)
            elif current.typeIn == ConstraintType.Sanctuarized: self.w_excludeInRB.setChecked(True)

            if current.typeOut == ConstraintType.Attractive: self.w_nearOutRB.setChecked(True)
            elif current.typeOut == ConstraintType.Repulsive: self.w_farOutRB.setChecked(True)
            elif current.typeOut == ConstraintType.Included: self.w_inOutRB.setChecked(True)
            elif current.typeOut == ConstraintType.Excluded: self.w_outOutRB.setChecked(True)
            elif current.typeOut == ConstraintType.Sanctuarized: self.w_excludeOutRB.setChecked(True)

        self.w_buffer.setValue(current.buffer)
        self.w_priority.setValue(current.priority/10)

        Debug.end("ConstraintWidget::updateOption")

    ## @brief enable radiobuttons and fields of constraints configuration
    # @param enabled activate (or desactivate) the radiobox (contraints type) and spinbox (buffer ans priority)
    def setOptionEnabled(self, enabled):
        Debug.begin("ConstraintWidget::setOptionEnabled")
        self.w_nearInRB.setEnabled(enabled)
        self.w_farInRB.setEnabled(enabled)
        self.w_inInRB.setEnabled(enabled)
        self.w_outInRB.setEnabled(enabled)
        self.w_excludeInRB.setEnabled(enabled)

        self.w_nearOutRB.setEnabled(enabled)
        self.w_farOutRB.setEnabled(enabled)
        self.w_inOutRB.setEnabled(enabled)
        self.w_outOutRB.setEnabled(enabled)
        self.w_excludeOutRB.setEnabled(enabled)

        self.w_buffer.setEnabled(enabled)
        self.w_priority.setEnabled(enabled)
        Debug.end("ConstraintWidget::setOptionEnabled")

    ## get the configuration from name
    # @param name name of the constraint
    # @return the constraint data
    def getConstraintFromName(self, name):
        Debug.begin("ConstraintWidget::getConstraintFromName")
        project = self.suricates.getProject(self.currentProject)
        if project == None:
            Debug.end("ConstraintWidget::getConstraintFromName (Error 1)")
            return
        Debug.print("selection:" + project.name())
        configLayer = self.suricates.getConfig(project)
        if configLayer == None:
            Debug.end("ConstraintWidget::getConstraintFromName (Error 2)")
            return;

        constraintsList = self.suricates.getConstraintsFromConfig(project, configLayer)

        current = None
        for constraint in constraintsList:
            if constraint.name == name:
                current = constraint

        if current == None:
            setOptionEnabled(False)
            Debug.end("ConstraintWidget::getConstraintFromName (Error 3)")
            return;

        Debug.end("ConstraintWidget::getConstraintFromName")
        return current

    ## @brief compute constraints when user click button
    #
    # execute the process to create raster of constraints
    def onCompute(self):
        Debug.begin("ConstraintWidget::onCompute")
        project = self.suricates.getProject(self.currentProject)
        if project == None:
            Debug.end("ConstraintWidget::onCompute (Error 1)")
            return
        Debug.print("selection:" + project.name())
        configLayer = self.suricates.getConfig(project)
        if configLayer == None:
            Debug.end("ConstraintWidget::onCompute (Error 2)")
            return;

        constraintsList = self.suricates.getConstraintsFromConfig(project, configLayer)
        intputList = list();

        for constraint in constraintsList:
            layer = self.suricates.getLayer(project, constraint.name)
            if(layer != None and layer.layer() != None):
                constraint.name = layer.layer().source()
                intputList.append(constraint)


        a = SuricatesAlgo(intputList, self.currentProject, self.suricates)
        a.deleteTmp = QMessageBox.question(None, "delete temporary files?", "do you want delete temporary file?") == QMessageBox.StandardButton.Yes
        
        self.suricates.tasks.append( a )
        #a.run()
        #a.finished(True)
        QgsApplication.taskManager().addTask(a)

        Debug.end("ConstraintWidget::onCompute")

    ## @brief save parameters of the current constraint when user click button
    def onSave(self):
        # get the type
        Debug.begin("ConstraintWidget::onSave")
        if not self.w_priority.isEnabled():
            typeIn = ConstraintType.Map
        elif self.w_nearInRB.isChecked(): typeIn = ConstraintType.Attractive
        elif self.w_farInRB.isChecked(): typeIn = ConstraintType.Repulsive
        elif self.w_inInRB.isChecked(): typeIn = ConstraintType.Included
        elif self.w_outInRB.isChecked(): typeIn = ConstraintType.Excluded
        elif self.w_excludeInRB.isChecked(): typeIn = ConstraintType.Sanctuarized
        else:
            Debug.end("ConstraintWidget::onSave (Error 1)")
            return;

        if typeIn == ConstraintType.Map: typeOut = ConstraintType.Excluded
        elif self.w_nearOutRB.isChecked(): typeOut = ConstraintType.Attractive
        elif self.w_farOutRB.isChecked(): typeOut = ConstraintType.Repulsive
        elif self.w_inOutRB.isChecked(): typeOut = ConstraintType.Included
        elif self.w_outOutRB.isChecked(): typeOut = ConstraintType.Excluded
        elif self.w_excludeOutRB.isChecked(): typeOut = ConstraintType.Sanctuarized
        else:
            Debug.end("ConstraintWidget::onSave (Error 1)")
            return;

        Debug.print("type:" + SuricatesInstance.ConstraintTypeToString(type))

        # get the distance
        distance = self.w_buffer.value()
        Debug.print("distance:" + str(distance))

        # get the priority
        priority = self.w_priority.value()*10
        Debug.print("priority:" + str(priority))

        list = self.w_listConstraints.selectedItems()
        if len(list) == 0:
            self.setOptionEnabled(False)
            Debug.end("ConstraintWidget::onSave (Error 2)")
            return

        treeitem = list[0]
        name = treeitem.text(0)

        constraint = self.getConstraintFromName(name)
        if constraint == None:
            Debug.end("ConstraintWidget::onSave (Error 3)")
            return

        constraint.typeIn = typeIn
        constraint.typeOut = typeOut
        constraint.priority = priority
        constraint.buffer = distance

        if not self.suricates.saveConstraint(self.currentProject, constraint, False):
            self.suricates.iface.messageBar().pushMessage("Faillure!", "save constraint:", level=Qgis.Critical)
            Debug.end("ConstraintWidget::onSave (Error 4)")
            return;

        treeitem.setText(1, SuricatesInstance.ConstraintTypeToString(constraint.typeIn))
        treeitem.setText(2, SuricatesInstance.ConstraintTypeToString(constraint.typeOut))
        treeitem.setText(3, str(distance))
        treeitem.setText(4, str(priority))

        Debug.end("ConstraintWidget::onSave")
        return

    ## @brief click on the button to create a new constraint
    #
    # @msc
    # Sender,Receiver;
    # Sender->Receiver [label="Command()", URL="\ref Receiver::Command()"];
    # Sender<-Receiver [label="Ack()", URL="\ref Ack()", ID="1"];
    # @endmsc
    #
    def onAddNewConstraint(self):
        Debug.begin("ConstraintWidget::onAddNewConstraint")
        project = self.suricates.getProject(self.currentProject)
        if project == None:
            Debug.end("ConstraintWidget::onAddNewConstraint (Error 1)")
            return
        Debug.print("selection:" + project.name())
        configLayer = self.suricates.getConfig(project)
        if configLayer == None:
            Debug.end("ConstraintWidget::onAddNewConstraint (Error 2)")
            return;

        constraintsList = self.suricates.getConstraintsFromConfig(project, configLayer)

        haveMap = False
        for c in constraintsList:
            if c.typeIn == ConstraintType.Map:
                haveMap = True

        layer = self.suricates.copyCurrentLayer(self.currentProject)
        if layer == None:
            Debug.end("ConstraintWidget::onAddNewConstraint (faillure)")
            return

        if haveMap:
            constraint = ConstraintItem(layer.name())
        else:
            constraint = ConstraintItem(layer.name(), 0, 5, ConstraintType.Map)

        if not self.suricates.saveConstraint(self.currentProject, constraint, True):
            self.suricates.iface.messageBar().pushMessage("Faillure!", "create new constraint:", level=Qgis.Critical)
            Debug.end("ConstraintWidget::onAddNewConstraint (faillure)")
            return;

        twi = QTreeWidgetItem([constraint.name, SuricatesInstance.ConstraintTypeToString(constraint.typeIn), SuricatesInstance.ConstraintTypeToString(constraint.typeOut), str(constraint.buffer),str(constraint.priority)])
        self.w_listConstraints.addTopLevelItem(twi)

        self.suricates.iface.messageBar().pushMessage("Success!", "create new constraint", level=Qgis.Success, duration=3)
        Debug.end("ConstraintWidget::onAddNewConstraint (success)")
        return

    ## @brief click on a item of the constraint list
    def onSelectedConstraintChanged(self):
        Debug.begin("ConstraintWidget::onSelectedConstraintChanged")
        list = self.w_listConstraints.selectedItems()
        if len(list) == 0:
            self.setOptionEnabled(False)
            Debug.end("ConstraintWidget::onSelectedConstraintChanged")
            return

        current = list[0]
        name = current.text(0)
        Debug.print(name)
        self.updateOption(name)

        Debug.end("ConstraintWidget::onSelectedConstraintChanged")
        return

    ## @brief click on the button to delete constraint
    def onDeleteConstraint(self):
        Debug.begin("ConstraintWidget::onDeleteConstraint")
        list = self.w_listConstraints.selectedItems()
        if len(list) == 0:
            self.setOptionEnabled(False)
            Debug.end("ConstraintWidget::onSelectedConstraintChanged")
            return

        current = list[0]
        name = current.text(0)

        self.suricates.deleteConstraint(self.currentProject, name)
        self.updateProject()

        Debug.end("ConstraintWidget::onDeleteConstraint")
        return

    ## @brief change the value of the threshold
    def onChangeThreshold(self, value):
        Debug.begin("ConstraintWidget::onChangeThreshold")
        project = self.suricates.getProject(self.currentProject)
        if project == None:
            Debug.end("ConstraintWidget::onChangeThreshold (Error 1)")
            return
        Debug.print("selection:" + project.name())
        configLayer = self.suricates.getConfig(project)
        if configLayer == None:
            Debug.end("ConstraintWidget::onChangeThreshold (Error 2)")
            return;

        constraintsList = self.suricates.getConstraintsFromConfig(project, configLayer)

        current = None
        for constraint in constraintsList:
            if constraint.typeIn == ConstraintType.Map:
                current = constraint

        if current == None:
            Debug.end("ConstraintWidget::onChangeThreshold (Error 3)")
            return;

        current.priority = value

        ok = self.suricates.saveConstraint(self.currentProject, current, False)
        if not ok:
            self.suricates.iface.messageBar().pushMessage("Faillure!", "save constraint:", level=Qgis.Critical)
            Debug.end("ConstraintWidget::onChangeThreshold (Error 4)")
            return;

        Debug.end("ConstraintWidget::onChangeThreshold")
        return

## @brief widget with controls to select, create and delete projects
#
# ![User interface classes imbrication](assets\GuiStructure.png)
#
# ![User interface: management of projects](assets\UserManuel_Project.png)
class HeaderWidget(QGroupBox):
    ## @var suricates
    # current SuricatesInstance

    ## @brief constructor
    # @param parent parent (QWidget)
    def __init__(self, parent=None):
        QGroupBox.__init__(self, "Projects", parent)
        Debug.begin("HeaderWidget::__init__")

        self.suricates = parent.suricates

        # build content of the widget
        ## first line
        ### create the label 'selection'
        label1 = QLabel("Selection",self)

        ### create a combobox to list projects
        self.combobox_project = QComboBox(self)

        ### create button to remove the project selected by the combobox
        self.button_delproject = QPushButton(self)
        self.button_delproject.setIcon(QIcon(":/images/themes/default/mActionRemove.svg"))
        self.button_delproject.setToolTip("Delete project")
        self.button_delproject.setMaximumWidth(self.button_delproject.sizeHint().height())

        ## second line
        ### create the label 'new'
        label2 = QLabel("New",self)

        ### create a combobox to list projects
        self.newlineedit_project = QLineEdit(self)

        ### create button to add a new project
        self.button_newproject = QPushButton(self)
        self.button_newproject.setIcon(QIcon(":/images/themes/default/mActionAdd.svg"))
        self.button_newproject.setToolTip("New project")
        self.button_newproject.setMaximumWidth(self.button_newproject.sizeHint().height())
        self.button_newproject.setEnabled(False);

        ### create global layout (grid) to order widgets:
        ### 'Selection', combobox, button 'delete'
        ### 'New', text field, button 'new'
        selectl = QGridLayout(self)
        selectl.addWidget(label1,0,0)
        selectl.addWidget(self.combobox_project,0,1)
        selectl.addWidget(self.button_delproject,0,2)
        selectl.addWidget(label2,1,0)
        selectl.addWidget(self.newlineedit_project,1,1)
        selectl.addWidget(self.button_newproject,1,2)

        ## set the layout at the groupbox
        self.setLayout(selectl)

        ## connections
        ### if user clicks on the button 'new' then program calls the method 'onCreateNewProject'
        self.button_newproject.clicked.connect(self.onCreateNewProject)
        ### if user clicks on the button 'delete' then program calls the method 'onDeleteProject'
        self.button_delproject.clicked.connect(self.onDeleteProject)
        ### if user edit the text field then the program calls the method 'onTextEdited'
        self.newlineedit_project.textChanged.connect(self.onTextEdited)
        ### if user change the selected item of the combobox then the program call the method 'onSelectionChange'
        self.combobox_project.currentTextChanged.connect(self.onSelectionChange)
        Debug.end("HeaderWidget::__init__")
        return

    ## @brief display projects in the combobox
    # @param projects map of the projects
    def setProjects(self, projects):
        Debug.begin("HeaderWidget::setProjects")
        self.combobox_project.clear();
        for x in projects.keys():
            self.combobox_project.addItem(x);
        Debug.end("HeaderWidget::setProjects")
        return

    ## @brief called if user edit text in line edit (name of the new project)
    # if the text is empty or corresponds to an existing project name then the button 'new project' is desactivated;
    # else the button 'new project' is enabled;
    def onTextEdited(self):
        Debug.begin("HeaderWidget::onTextEdited")
        t = self.newlineedit_project.text()
        if t == "" or self.suricates.projectNameExists(t):
            self.button_newproject.setEnabled(False)
        else:
            self.button_newproject.setEnabled(True)
        Debug.end("HeaderWidget::onTextEdited")
        return

    ## @brief called if button 'new project' is clicked
    # create a new group in layer in the layer panel with the name contained in the QTextEdit
    def onCreateNewProject(self):
        Debug.begin("HeaderWidget::onCreateNewProject")
        t = self.newlineedit_project.text()
        self.newlineedit_project.setText("")
        self.suricates.createNewProject(t)
        index = self.combobox_project.findText(t)
        self.combobox_project.setCurrentIndex(index)
        Debug.end("HeaderWidget::onCreateNewProject")
        return

    ## @brief called if button 'delete project' is clicked
    # delete the selected group
    def onDeleteProject(self):
        Debug.begin("HeaderWidget::onDeleteProject")
        t = self.combobox_project.currentText()
        self.suricates.deleteProject(t)
        Debug.end("HeaderWidget::onDeleteProject")
        return

    ## @brief called if the selected item of the combobox id changed
    # delete the selected group
    # @param text the value of the combobox
    def onSelectionChange(self, text):
        Debug.begin("HeaderWidget::onSelectionChange")
        self.suricates.selectProject(text)
        Debug.end("HeaderWidget::onSelectionChange")
        return

## @brief main widget for suricates, it containts a HeaderWidget and a ConstraintWidget
#
# ![User interface classes imbrication](assets\GuiStructure.png)
class SuricatesWidget(QWidget):
    ## @var suricates
    ## current SuricatesInstance

    ## @var projectWidget
    ## the HeaderWidget at the top of the widget: manage the projects and select the current project

    ## @var constraintWidget
    ## the ConstraintWidget at the bottom of the widget: manage the constrains of the selected project

    ## @brief constructor
    # @param parent parent of the widget (QWidget)
    def __init__(self, parent):
        Debug.begin("SuricatesWidget::__init__")
        QWidget.__init__(self,parent)

        self.suricates = parent.suricates

        globalLayout = QVBoxLayout(self)
        self.stackedWidget = QStackedWidget(self)
        globalLayout.addWidget(self.stackedWidget)

        # "credit" widget
        self.creditWidget = QWidget(self.stackedWidget)
        self.stackedWidget.addWidget(self.creditWidget)
        creditlayout = QVBoxLayout(self.creditWidget)

        self.logoWidget3 = QLabel(self.creditWidget)
        self.logoPixmap3 = QPixmap(":/plugins/suricates/logo_suricates.svg").scaledToWidth(400, Qt.SmoothTransformation)
        self.logoWidget3.setPixmap(self.logoPixmap3)
        self.logoWidget3.setAlignment(Qt.AlignHCenter)
        creditlayout.addWidget(self.logoWidget3)

        self.logoWidget = QLabel(self.creditWidget)
        self.logoPixmap = QPixmap(":/plugins/suricates/logo_cdi.svg").scaledToHeight(100, Qt.SmoothTransformation)
        self.logoWidget.setPixmap(self.logoPixmap)
        self.logoWidget.setAlignment(Qt.AlignHCenter)

        self.logo2Widget = QLabel(self.creditWidget)
        self.logo2Pixmap = QPixmap(":/plugins/suricates/logo_Universite_de_Lille.svg").scaledToHeight(100, Qt.SmoothTransformation)
        self.logo2Widget.setPixmap(self.logo2Pixmap)
        self.logo2Widget.setAlignment(Qt.AlignHCenter)

        selecth = QHBoxLayout(self.creditWidget)
        selecth.addWidget(self.logo2Widget)
        selecth.addWidget(self.logoWidget)
        creditlayout.addSpacing(50)
        creditlayout.addLayout(selecth)
        creditlayout.addStretch()
        self.stackedWidget.addWidget(self.creditWidget)

        # "main" widget
        self.mainWidget = QWidget(self.stackedWidget)
        selectl = QVBoxLayout(self.mainWidget)
        self.mainWidget.setLayout(selectl)

        self.projectWidget = HeaderWidget(self)
        self.constraintWidget = ConstraintWidget(self)

        selectl.addWidget(self.projectWidget)
        selectl.addWidget(self.constraintWidget)
        self.stackedWidget.addWidget(self.mainWidget)

        self.setLayout(globalLayout)
        self.suricates.iface.currentLayerChanged.connect(self.handleLayerChanged)

        QTimer.singleShot(4000, self.goToMainWidget)

        Debug.end("SuricatesWidget::__init__")

    def goToMainWidget(self):
        Debug.begin("SuricatesWidget::goToMainWidget")
        self.stackedWidget.setCurrentIndex(1)
        Debug.end("SuricatesWidget::goToMainWidget")

    ## @brief executed when a layer is changed, this was a test
    def handleLayerChanged(self):
        Debug.begin("SuricatesWidget::handleLayerChanged")
        # mylayer = self.suricates.iface.activeLayer()
        # if not (mylayer is None):
        #	 name = mylayer.name()
        #	 self.suricates.iface.messageBar().pushMessage("Layer changed", name, level = Qgis.Info, duration=3)
        # print(type(iface.activeLayer()))
        Debug.end("SuricatesWidget::handleLayerChanged")

    ## @brief select the curent project
    # @name name of the project
    def setProject(self, name):
        Debug.begin("SuricatesWidget::setProject")
        self.constraintWidget.setProject(name)
        Debug.end("SuricatesWidget::setProject")

## @brief simple dockwidget (panel) which contains a SuricatesWidget
#
# #
# ![User interface classes imbrication](assets\GuiStructure.png)
class SuricatesDock(QDockWidget):
    ## @var suricates
    ## current SuricatesInstance

    ## @var w_suricates
    ## the SuricatesWidget contained in the panel

    ## @brief constructor
    # @param suricates current SuricatesInstance
    def __init__(self, suricates):
        Debug.begin("SuricatesDock::__init__")
        QDockWidget.__init__(self, "RAIES Model" ,suricates.iface.mainWindow())
        self.suricates = suricates
        self.w_suricates = SuricatesWidget(self)
        self.setWidget(self.w_suricates)
        Debug.end("SuricatesDock::__init__")

## @brief contains gui commands
class SuricatesInstance():
    ## @var projectNode
    # the node which corresponds to the group 'Projects'

    ## @var tasks
    # list of tasks (SuricatesAlgo) which are currently in progress

    ## @var blockSignals
    # used to block signal to avoid conflicts between user manipulation and program process

    ## @var projectsNodeName
    # default name of the group 'Project' of the panel of layers

    ## @var dock
    # the SuricatesDock created in the current instance

    ## @brief constructor
    def __init__(self, iface):
        Debug.begin("SuricatesInstance::__init__")
        self.iface = iface

        # initialize variables
        self.tasks = list()

        self.blockSignals = False
        self.projectsNodeName = "Projects"
        self.projectNode = None

        # dock the new instance
        self.dock = SuricatesDock(self)
        self.dock.setAttribute(Qt.WA_DeleteOnClose) # set behavior: delete dock widget when closed
        self.iface.addDockWidget(Qt.RightDockWidgetArea,self.dock)
        QgsProject.instance().cleared.connect(self.closeInstance)
        Debug.end("SuricatesInstance::__init__")

    ## @brief close suricates instance
    #
    # disconnect signals
    def closeInstance(self):
        Debug.begin("SuricatesInstance::closeInstance")
        # disconnect projects
        projects = self.readProjects()
        for x in projects.values():
            try: x.nameChanged.disconnect(self.onNameChanged)
            except: pass
        # disconnect projects node
        try: self.projectNode.removedChildren.disconnect(self.onNodeDeleted)
        except: pass

        try: self.projectNode.addedChildren.disconnect(self.onNodeCreated)
        except: pass

        # close widget
        try: self.iface.mainWindow().removeDockWidget(self.dock)
        except: pass
        #self.dock.close()
        Debug.end("SuricatesInstance::closeInstance")

    ## @brief return group 'Projects' if exists or create a node 'Project'
    def initializeProjectNode(self):
        Debug.begin("SuricatesInstance::initializeProjectNode")
        # verify is projectNode already initialized
        if self.projectNode != None:
            try:
                name = self.projectNode.name()
                Debug.end("SuricatesInstance::initializeProjectNode (1)")
                return self.projectNode
            except:
                Debug.end("SuricatesInstance::initializeProjectNode (error)")
                pass

        root = QgsProject.instance().layerTreeRoot()
        found = False
        # search the group 'Project'
        for child in root.children():
            if isinstance(child, QgsLayerTreeGroup):
                if child.name() == self.projectsNodeName:
                    self.projectNode = child
                    found = True

        # create a group 'Project' if it is not exist
        if not found:
            self.projectNode = root.addGroup(self.projectsNodeName)
        # connection:
        # if user remove a child of the group 'Project' then the program call the method 'onNodeDeleted'
        self.projectNode.removedChildren.connect(self.onNodeDeleted)
        # if user create a child in the group 'Project' then the program call the method 'onNodeCreated'
        self.projectNode.addedChildren.connect(self.onNodeCreated)
        Debug.end("SuricatesInstance::initializeProjectNode (2)")
        return self.projectNode


    ## @brief  return the list of the projects
    def readProjects(self):
        Debug.begin("SuricatesInstance::readProjects")
        # dictionary to return
        projects = dict();
        # verify that project have different names
        self.verifyProjectName()
        # fill the dictionary with projects (children of the group 'Project')
        for child in self.projectNode.children():
            if isinstance(child, QgsLayerTreeGroup):
                projects[child.name()] = child
        Debug.end("SuricatesInstance::readProjects")
        return projects;

    ## @brief update project signals
    def updateProjects(self):
        Debug.begin("SuricatesInstance::updateProjects")
        # get the list of projects
        projects = self.readProjects()
        # send it to the combobox of the HeaderWidget
        self.dock.w_suricates.projectWidget.setProjects(projects)

        if len(projects) == 0:
             self.dock.w_suricates.projectWidget.onSelectionChange(None)

        # connections for each project
        for x in projects.values():
            # disconnect to avoid multiple connections if it is possible
            try: x.nameChanged.disconnect(self.onNameChanged)
            except: pass
            # if user edits the name of the project then the program calls the method 'onNameChanged'
            x.nameChanged.connect(self.onNameChanged)
        Debug.end("SuricatesInstance::updateProjects")

    ## @brief called when a project node is renamed (layer panel)
    # @see updateProjects()
    def onNameChanged(self):
        if self.blockSignals: return;
        Debug.begin("SuricatesInstance::onNameChanged")
        self.updateProjects()
        Debug.end("SuricatesInstance::onNameChanged")

    ## @brief called when a project node is created (layer panel)
    # @see updateProjects()
    def onNodeCreated(self):
        if self.blockSignals: return;
        Debug.begin("SuricatesInstance::onNodeCreated")
        self.updateProjects()
        Debug.end("SuricatesInstance::onNodeCreated")

    ## @brief called when a project node is deleted (layer panel)
    # @see updateProjects()
    def onNodeDeleted(self):
        if self.blockSignals: return;
        Debug.begin("SuricatesInstance::onNodeDeleted")
        self.updateProjects()
        Debug.end("SuricatesInstance::onNodeDeleted")

    ## @brief create a new project node
    # @param projectName name of the new project
    def createNewProject(self, projectName):
        Debug.begin("SuricatesInstance::createNewProject")
        # create a new group for project
        project = self.projectNode.addGroup(projectName)
        # connection
        # if user rename the project then the program calls the method 'onNameChanged'
        project.nameChanged.connect(self.onNameChanged)
        Debug.end("SuricatesInstance::createNewProject")

    ## @brief delete a project node
    # @param projectName (string) name of the project to delete
    def deleteProject(self, projectName):
        Debug.begin("SuricatesInstance::deleteProject")
        # get the list of projects
        projects = self.readProjects()
        # search the selected project (projectName) and remove it
        for x,y in projects.items():
            if x == projectName:
                self.projectNode.removeChildNode(y)

        self.updateProjects()
        Debug.end("SuricatesInstance::deleteProject")

    ## @brief return if a name already exists in projects
    # @param projectName (string) name of the projet to search
    def projectNameExists(self, projectName):
        Debug.begin("SuricatesInstance::projectNameExists")
        projects = self.readProjects()
        result = False
        if projectName in projects:
            result = True
        Debug.end("SuricatesInstance::projectNameExists")
        return result

    ## @brief verify if many project have the same name and fix this
    def verifyProjectName(self):
        Debug.begin("SuricatesInstance::verifyProjectName")
        # list the projects
        projects = list()
        self.initializeProjectNode()
        for child in self.projectNode.children():
            if isinstance(child, QgsLayerTreeGroup):
                projects.append(child)

        # compare the name of each project to rename when the names are identic
        renamedList = list()
        for i in projects:
            for j in projects:
                if i != j:
                    if i.name() == j.name():
                        j.setName(j.name() + "'")
                        if not j in renamedList:
                            renamedList.append(j)

        # display informations for users
        if len(renamedList) > 0:
            str = "renamed projects:"
            for k in renamedList:
                str += "\n -" + k.name()

            self.iface.messageBar().pushMessage("Warning", str, level = Qgis.Warning, duration=5)
        Debug.end("SuricatesInstance::verifyProjectName")

    ## @brief get the project defined by a name
    # @param name name of the project to search
    def getProject(self, name):
        Debug.begin("SuricatesInstance::getProject " + name)
        list_projects = self.readProjects()

        # display list of project if debug
        if Debug.enabled: SuricatesInstance.displayProjects(list_projects)

        # verify if project folder exist
        if name in list_projects:
            Debug.end("SuricatesInstance::getProject (project exists)")
            return list_projects[name]
        else:
            Debug.end("SuricatesInstance::getProject (project doesn't exist)")
            return None
        Debug.end("SuricatesInstance::getProject")

    ## @brief get the list of layers of a group
    # @param group group
    def getLayers(self, group):
        Debug.begin("SuricatesInstance::getLayers")
        layers = list()

        for child in group.children():
            if isinstance(child, QgsLayerTreeLayer):
                layers.append(child)

        self.displayLayers(layers)

        Debug.end("SuricatesInstance::getLayers")
        return layers;

    ## @brief get a specific layer (tree node) by name of a group
    # @param group group
    # @param name name of the layer
    def getLayer(self, group, name):
        Debug.begin("SuricatesInstance::getLayer: " + group.name() + " " + name)
        for child in group.children():
            Debug.print("child: " + child.name() )
            if isinstance(child, QgsLayerTreeLayer):
                if child.name() == name:
                    Debug.end("SuricatesInstance::getLayer (layer exists)")
                    return child
            else: Debug.print("ko: " + str(type(child)) )

        Debug.end("SuricatesInstance::getLayer (layer doesn't exist)")
        return None

    ## @brief get the configuration (tree node) of the project or create a new one
    # @param project node of the project
    def getConfig(self,project):
        Debug.begin("SuricatesInstance::getConfig")
        configLayer = self.getLayer(project, "project_config")
        if configLayer == None:
            Debug.end("SuricatesInstance::getConfig (new)")
            return self.createConfig(project)
        Debug.end("SuricatesInstance::getConfig (existing)")
        return configLayer

    ## @brief get the list of constraints from the layer tree node
    def getConstraintsFromConfig(self, projectNode, configLayer):
        Debug.begin("SuricatesInstance::getConstraintsFromConfig")
        constraints = list()

        configs = QgsProject.instance().mapLayer(configLayer.layerId())
        features = configs.getFeatures()

        Debug.print(projectNode.name())

        for feature in features:
            name = feature["base"]
            c = ConstraintItem( name,feature["buffer"],feature["priority"],SuricatesInstance.ConstraintTypeFromString(feature["typeIn"]),SuricatesInstance.ConstraintTypeFromString(feature["typeOut"]))
            if self.getLayer(projectNode, name) == None: c.exists = False
            else: c.exists = True
            constraints.append(c)

        SuricatesInstance.displayConstraints(constraints)

        Debug.end("SuricatesInstance::getConstraintsFromConfig")
        return constraints

    ## @brief save a constraint in a group
    def saveConstraint(self, currentProjectName, newconstraint, isNew):
        Debug.begin("SuricatesInstance::saveConstraint")
        project = self.getProject(currentProjectName)
        if project == None:
            Debug.end("SuricatesInstance::saveConstraint (faillure 1)")
            return False
        config = self.getConfig(project)
        if config == None:
            Debug.end("SuricatesInstance::saveConstraint (faillure 2)")
            return False

        if isNew:
            ok = self.appendConstraintInConfig(config, newconstraint)
        else:
            ok = self.modifyConstraintInConfig(config, newconstraint)

        if ok: Debug.end("SuricatesInstance::saveConstraint (success)")
        else: Debug.end("SuricatesInstance::saveConstraint (faillure 3)")
        return ok

    ## @brief create a new filename which doesn't exist in the qgis project
    # this return either *projectName_baseName.extention* or *projectName_baseName_n.extention* (where n is an integer)
    # @param projectName project which receipt the new layer (string)
    # @param baseName base name of the file
    # @param extention extension of the file
    # @return a new filename
    def createFileName(self, projectName, baseName, extention):
        Debug.begin("SuricatesInstance::createFileName")
        projectPath = QDir(QgsProject.instance().absolutePath())
        file = QFileInfo(projectPath, projectName + "_" + baseName + "." + extention)
        i=1
        while file.exists():
            file = QFileInfo(projectPath, projectName + "_" + baseName + "_" + str(i) + "." + extention)
            i = i + 1
        Debug.end("SuricatesInstance::createFileName")
        return file

    ## @brief create a layer name which doesn't exist in the project group
    #
    # this return either *layerBaseName* or *layerBaseName_n* (where n is an integer)
    # @param projectName: project which receipt the new layer (string)
    # @param layerBaseName: base name for the layer (string)
    # @return a name for a new layer (string)
    def createLayerName(self, projectName, layerBaseName):
        Debug.begin("SuricatesInstance::createLayerName")
        project = self.getProject(projectName)

        name = layerBaseName
        i = 0;

        while self.getLayer(project, name) != None:
            name = layerBaseName + "_" + str(i)
            i = i + 1

        Debug.end("SuricatesInstance::createLayerName")
        return name

    ## @brief convert the enum ConstraintType to text
    # @param type (ConstraintType)
    # @return type (string)
    @staticmethod
    def ConstraintTypeToString(type):
       if(type == ConstraintType.Attractive): return "Attractive"
       if(type == ConstraintType.Repulsive): return "Repulsive"
       if(type == ConstraintType.Included): return "Included"
       if(type == ConstraintType.Excluded): return "Excluded"
       if(type == ConstraintType.Sanctuarized): return "Sanctuarized"
       if(type == ConstraintType.Map): return "Map"
       return "None"

    ## @brief convert text to the enum ConstraintType
    # @param typeName (string)
    # @return (ConstraintType)
    @staticmethod
    def ConstraintTypeFromString(typeName):
        print(typeName)
        if(typeName == "Attractive"): return ConstraintType.Attractive
        if(typeName == "Repulsive"): return ConstraintType.Repulsive
        if(typeName == "Included"): return ConstraintType.Included
        if(typeName == "Excluded"): return ConstraintType.Excluded
        if(typeName == "Sanctuarized"): return ConstraintType.Sanctuarized
        if(typeName == "Map"): return ConstraintType.Map
        return None

    ## @brief create a configuration file for a project
    # @param project node of the project (QgsLayerTreeGroup)
    # @return the created layer if registration done (QgsVectorLayer)
    def createConfig(self, project):
        Debug.begin("SuricatesInstance::createConfig")
        self.blockSignals = True
        # ------------------------
        # create memory layer
        # ------------------------
        layer = QgsVectorLayer("Point", "tp2", "memory")
        pr = layer.dataProvider()

        # Enter editing mode
        layer.startEditing()

        # add fields
        pr.addAttributes([QgsField("base", QVariant.String),
                          QgsField("typeIn", QVariant.String),
                          QgsField("typeOut", QVariant.String),
                          QgsField("buffer", QVariant.Int),
                          QgsField("priority", QVariant.Double)])

        # Commit changes
        # this is required to update attributes
        layer.commitChanges()

        # get absolute file path
        file = self.createFileName(project.name(), "config", "shp")

        # ------------------------
        # save the layer as file ans delete the layer
        # ------------------------
        error = QgsVectorFileWriter.writeAsVectorFormat(layer, file.absoluteFilePath(), "utf-8",
                                                        driverName="ESRI Shapefile")

        # manage error
        if error[0] == QgsVectorFileWriter.NoError:
            self.iface.messageBar().pushMessage("Success!", "writing new config file", level=Qgis.Success, duration=3)
            print("success! writing new memory layer")
            # --------------------------
            # open the created file
            # --------------------------
            uri = file.absoluteFilePath()
            layer_shp = QgsVectorLayer(uri, 'project_config', 'ogr')

            QgsProject.instance().addMapLayer(layer_shp, False)
            l = project.addLayer(layer_shp)
            Debug.end("SuricatesInstance::createConfig (success)")
            self.blockSignals = False
            return l
        else:
            self.iface.messageBar().pushMessage("Faillure!", "writing new config file:" + str(error), level=Qgis.Critical)
            Debug.end("SuricatesInstance::createConfig (faillure)")
            self.blockSignals = False
            return None

    ## @brief create a layer from selected layer
    # @param projectName project name (string)
    # @return the created layer if registration done (QgsVectorLayer)
    def copyCurrentLayer(self, projectName):
        Debug.begin("SuricatesInstance::copyCurrentLayer")
        self.blockSignals = True
        root = self.getProject(projectName)
        # current layer
        layer_shp = self.iface.activeLayer()
        #↨ verify if current layer is valid
        if not type(layer_shp) is QgsVectorLayer:
            Debug.end("SuricatesInstance::copyCurrentLayer (layer not valid)")
            return None;

        print("name:" +  layer_shp.name())

        # ------------------------
        # create memory layer
        # ------------------------
        geomtype = layer_shp.wkbType()
        print("type " + str(layer_shp.geometryType()))
        print("datacomment " + layer_shp.dataComment())
        print("sourcename " + layer_shp.sourceName())
        print("storagetype " + layer_shp.storageType())
        print("subsetString " + layer_shp.subsetString())
        print("wkbType " + str(layer_shp.wkbType()))

        if geomtype == QgsWkbTypes.Unknown or geomtype == QgsWkbTypes.NoGeometry:
            Debug.end("SuricatesInstance::copyCurrentLayer (layer not valid)")
            return None;

        # if geomtype == QgsWkbTypes.Point:
        #    layer = QgsVectorLayer("Point", "tp2", "memory")
        #if geomtype == QgsWkbTypes.LineString:
        #    layer = QgsVectorLayer("Line", "tp2", "memory")
        #if geomtype == QgsWkbTypes.Polygon:
        #    layer = QgsVectorLayer("Polygon", "tp2", "memory")
        #if geomtype == QgsWkbTypes.MultiLineString:
        #    layer = QgsVectorLayer("MultiLine", "tp2", "memory")
        #if geomtype == QgsWkbTypes.MultiPoint:
        #    layer = QgsVectorLayer("MultiPoint", "tp2", "memory")
        #if geomtype == QgsWkbTypes.MultiPolygon:
        #    layer = QgsVectorLayer("MultiPolygon", "tp2", "memory")

        layer_type = QgsWkbTypes.displayString(layer_shp.wkbType())
        layer = QgsVectorLayer(layer_type,"tp2","memory")

        pr = layer.dataProvider()

        # Enter editing mode
        layer.startEditing()

        # add fields
        pr.addAttributes(layer_shp.fields())

        # Commit changes
        # this is required to update attributes
        layer.commitChanges()

        # --------------------------
        # copy
        # ---------------------------
        count = 0
        if layer_shp.selectedFeatureCount() != 0:
            count = layer_shp.selectedFeatureCount()
            pr.addFeatures(layer_shp.selectedFeatures())
        else:
            count = layer_shp.featureCount()
            feat = []
            for t in layer_shp.getFeatures():
                feat.append(t)
            pr.addFeatures(feat)
        print("copy : " + str(count) + "/" + str(layer_shp.featureCount()))

        layer.commitChanges()

        # get absolute file path
        file = self.createFileName(projectName, layer_shp.name(), "shp")
        layername = self.createLayerName(projectName, layer_shp.name())

        # ------------------------
        # save the layer as file ans delete the layer
        # ------------------------
        error = QgsVectorFileWriter.writeAsVectorFormat(layer, file.absoluteFilePath(), "utf-8",
                                                        driverName="ESRI Shapefile")

        # manage error
        if error[0] == QgsVectorFileWriter.NoError:
            self.iface.messageBar().pushMessage("Success!", "writing new layer", level=Qgis.Success, duration=3)
            # --------------------------
            # open the created file
            # --------------------------
            uri = file.absoluteFilePath()
            crs = layer_shp.crs()
            layer_shp = QgsVectorLayer(uri, layername, 'ogr')
            layer_shp.setCrs(crs)
            print("items: " + str(layer_shp.featureCount()))

            QgsProject.instance().addMapLayer(layer_shp, False)
            l = root.addLayer(layer_shp)
            Debug.end("SuricatesInstance::copyCurrentLayer (success)")
            self.blockSignals = False
            return l
        else:
            self.iface.messageBar().pushMessage("Faillure!", "writing new layer:" + str(error), level=Qgis.Critical)
            print(str(error))
            Debug.end("SuricatesInstance::copyCurrentLayer (faillure)")
            self.blockSignals = False
            return None

    ## @brief save modifications of the modified constraint
    def modifyConstraintInConfig(self, configNode, constraint):
        Debug.begin("SuricatesInstance::modifyConstraintInConfig")
        layer = QgsProject.instance().mapLayer(configNode.layerId())

        features = layer.getFeatures()
        ok = False
        for feature in features:
            if feature["base"] == constraint.name:
                fid = feature.id()
                ok = True

        if not ok: return False

        if layer.dataProvider().capabilities() & QgsVectorDataProvider.ChangeAttributeValues:
            attrs = {1: SuricatesInstance.ConstraintTypeToString(constraint.typeIn),
                    2: SuricatesInstance.ConstraintTypeToString(constraint.typeOut),
                    3:constraint.buffer,
                    4:constraint.priority}
            layer.dataProvider().changeAttributeValues({fid: attrs})

        layer.updateExtents()
        layer.updateFields()
        layer.commitChanges()

        Debug.end("SuricatesInstance::modifyConstraintInConfig")
        return True

    ## @brief append a constraint in 'project_config'
    # @param configNode node of the 'project_config' (QgsLayerTreeLayer)
    # @param constraint constraint to save (ConstraintItem)
    # @return true
    def appendConstraintInConfig(self, configNode, constraint):
        Debug.begin("SuricatesInstance::appendConstraintInConfig")
        layer_shp =	 QgsProject.instance().mapLayer(configNode.layerId())

        pr = layer_shp.dataProvider()

        feat = QgsFeature(layer_shp.fields())
        feat.setAttribute('base', constraint.name)
        print(constraint.typeIn)
        print(constraint.typeOut)
        feat.setAttribute('typeIn', SuricatesInstance.ConstraintTypeToString(constraint.typeIn) )
        feat.setAttribute('typeOut', SuricatesInstance.ConstraintTypeToString(constraint.typeOut) )
        feat.setAttribute('buffer', constraint.buffer)
        feat.setAttribute('priority', constraint.priority)
        geom = QgsGeometry()
        feat.setGeometry(geom)

        pr.addFeatures([feat])
        layer_shp.updateExtents()
        layer_shp.updateFields()
        layer_shp.commitChanges()
        Debug.end("SuricatesInstance::appendConstraintInConfig")
        return True

    ## @brief delete a constraint from project_config
    # @param projectName name of the project (string)
    # @param constraintName name of the constraint (string)
    def deleteConstraint(self, projectName, constraintName):
        Debug.begin("SuricatesInstance::deleteConstraint")
        projectnode = self.getProject(projectName)
        # remove item from the file config
        confignode = self.getConfig(projectnode)
        if confignode == None: return
        layer = QgsProject.instance().mapLayer(confignode.layerId())
        if layer == None: return

        ok = False
        for feature in layer.getFeatures():
            if feature["base"] == constraintName:
                fid = feature.id()
                ok = True

        if not ok: return

        if layer.dataProvider().capabilities() & QgsVectorDataProvider.DeleteFeatures:
            res = layer.dataProvider().deleteFeatures([fid])

        layer.updateExtents()
        layer.updateFields()
        layer.commitChanges()

        Debug.end("SuricatesInstance::deleteConstraint")
        return

    ## @brief select project from text
    # @param projectName of the project to process (string)
    def selectProject(self, projectName):
        Debug.begin("SuricatesInstance::selectProject")

        if projectName != None : Debug.print("selection:" + projectName)
        else: Debug.print("selection: empty")

        self.dock.w_suricates.setProject(projectName)

        Debug.end("SuricatesInstance::selectProject")
        return

    ## @brief display a list of projects (Debug mode)
    # @param projects dictionary: projectName (string); group node (QgsLayerTreeGroup)
    @staticmethod
    def displayProjects(projects):
        Debug.begin("SuricatesInstance::displayProjects: " + str(len(projects)))
        for projectName, group in projects.items():
            Debug.print(projectName)
        Debug.end("SuricatesInstance::displayProjects")

    ## @brief display a list of layers (Debug mode)
    # @param layers list of layers node (list of QgsLayerTreeLayer)
    @staticmethod
    def displayLayers(layers):
        Debug.begin("SuricatesInstance::displayLayers: " + str(len(layers)))
        for i in layers:
            Debug.print(i.name())
        Debug.end("SuricatesInstance::displayLayers")

    ## @brief display a list of layers (Debug mode)
    # @param constraints list of constrained layers (list of ConstraintItem)
    @staticmethod
    def displayConstraints(constraints):
        Debug.begin("SuricatesInstance::displayConstraints: " + str(len(constraints)))
        for i in constraints:
            Debug.print(i.name + " " + SuricatesInstance.ConstraintTypeToString(i.typeIn) + " " + SuricatesInstance.ConstraintTypeToString(i.typeOut) + " " + str(i.buffer) + " " + str(i.priority) )
        Debug.end("SuricatesInstance::displayConstraints")

## @brief main program: close previous instance if exists and start a new one
def mainProgram(iface):
    global pmanager
    # close previous suricates instance if exist
    try:
        if not pmanager is None:
            pmanager.closeInstance()
    except:
        pass

    # create new suricates instance
    pmanager = SuricatesInstance(iface)
    # search group 'Projects' and its contents
    pmanager.initializeProjectNode()
    pmanager.updateProjects()

# mainProgram(iface)
