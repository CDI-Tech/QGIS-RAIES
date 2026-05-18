## @file SuricatesApp.py
#
# @date 2020-2024
# @version 1.01
# @author Vincent MAJORCZYK
# @copyright Copyright 2020-2024 CDI-Technologies (France), all right reserved.
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
import processing

from .debug import Debug
from .suricates_dock import SuricatesDock
from .constraint_item import ConstraintItem, ConstraintType

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

        # Disconnect from the project 'cleared' signal first, to avoid re-entrancy
        # if closeInstance is somehow called twice (e.g. during QGIS shutdown).
        try: QgsProject.instance().cleared.disconnect(self.closeInstance)
        except: pass

        # Disconnect all layer name signals before the layer tree is destroyed.
        # In QGIS 3.40, the C++ objects backing QgsLayerTreeGroup nodes are
        # destroyed during QgsProject::clear() — any dangling Python reference
        # to them causes an access violation.  We must release them here.
        if self.projectNode is not None:
            try:
                projects = self.readProjects()
                for x in projects.values():
                    try: x.nameChanged.disconnect(self.onNameChanged)
                    except: pass
            except: pass

            try: self.projectNode.removedChildren.disconnect(self.onNodeDeleted)
            except: pass
            try: self.projectNode.addedChildren.disconnect(self.onNodeCreated)
            except: pass

            # Release the C++ object reference so Python cannot access it after
            # QgsProject::clear() destroys the underlying layer tree.
            self.projectNode = None

        # Cancel any running tasks to avoid callbacks into a destroyed project
        for task in list(self.tasks):
            try: task.cancel()
            except: pass
        self.tasks.clear()

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
                # C++ object may have been destroyed (e.g. after project clear);
                # reset and re-initialize below.
                self.projectNode = None
                Debug.end("SuricatesInstance::initializeProjectNode (error)")

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

        # Re-connect to project cleared signal in case it was disconnected
        # (e.g. after a previous closeInstance call).
        try: QgsProject.instance().cleared.disconnect(self.closeInstance)
        except: pass
        QgsProject.instance().cleared.connect(self.closeInstance)

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
        projects = dict()
        # verify that project have different names
        self.verifyProjectName()
        # fill the dictionary with projects (children of the group 'Project')
        for child in self.projectNode.children():
            if isinstance(child, QgsLayerTreeGroup):
                projects[child.name()] = child
        Debug.end("SuricatesInstance::readProjects")
        return projects

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
        if self.blockSignals: return
        Debug.begin("SuricatesInstance::onNameChanged")
        self.updateProjects()
        Debug.end("SuricatesInstance::onNameChanged")

    ## @brief called when a project node is created (layer panel)
    # @see updateProjects()
    def onNodeCreated(self):
        if self.blockSignals: return
        Debug.begin("SuricatesInstance::onNodeCreated")
        self.updateProjects()
        Debug.end("SuricatesInstance::onNodeCreated")

    ## @brief called when a project node is deleted (layer panel)
    # @see updateProjects()
    def onNodeDeleted(self):
        if self.blockSignals: return
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
        return layers

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
            c = ConstraintItem( name,feature["buffer"],feature["priority"], SuricatesInstance.ConstraintTypeFromString(feature["typeIn"]), SuricatesInstance.ConstraintTypeFromString(feature["typeOut"]))
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
        i = 0

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
        save_options = QgsVectorFileWriter.SaveVectorOptions()
        save_options.driverName = "ESRI Shapefile"
        save_options.fileEncoding = "utf-8"
        transform_context = QgsProject.instance().transformContext()
        error, error_message, new_filename, new_layer_name = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, file.absoluteFilePath(), transform_context, save_options)

        # manage error
        if error == QgsVectorFileWriter.NoError:
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
            self.iface.messageBar().pushMessage("Faillure!", "writing new config file:" + str(error) + " " + str(error_message), level=Qgis.Critical)
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
            return None

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
            return None

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
        layer.setCrs(layer_shp.crs())

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
        save_options = QgsVectorFileWriter.SaveVectorOptions()
        save_options.driverName = "ESRI Shapefile"
        save_options.fileEncoding = "utf-8"

        transform_context = QgsProject.instance().transformContext()
        error, error_message, new_filename, new_layer_name = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, file.absoluteFilePath(), transform_context, save_options)

        # manage error
        if error == QgsVectorFileWriter.NoError:
            self.iface.messageBar().pushMessage("Success!", "writing new layer", level=Qgis.Success, duration=3)
            # --------------------------
            # open the created file
            # --------------------------
            uri = file.absoluteFilePath()
            layer_shp = QgsVectorLayer(uri, layername, 'ogr')
            print("items: " + str(layer_shp.featureCount()))

            QgsProject.instance().addMapLayer(layer_shp, False)
            l = root.addLayer(layer_shp)
            Debug.end("SuricatesInstance::copyCurrentLayer (success)")
            self.blockSignals = False
            return l
        else:
            self.iface.messageBar().pushMessage("Faillure!", "writing new layer:" + str(error) + " " + str(error_message), level=Qgis.Critical)
            print(str(error) + " " + str(error_message))
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
