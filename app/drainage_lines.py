from qgis.analysis import QgsNativeAlgorithms
import processing
from processing.tools import dataobjects
import csv
from PyQt5.QtCore import QEventLoop
import os
from processing.core.Processing import Processing
import sys
import cProfile
import pstats
from tasks.find_touching_polygons_task import FindTouchingPolygonsTask
from tasks.create_layer_from_threshold import CreateLayerFromThresholdTask
from tasks.layer_difference_task import LayerDifferenceTask
from tasks.accumulation_task import AccumulationTask
from tasks.load_layer_task import LoadLayerTask
from tasks.create_mosaic_task import CreateMosaicTask, ClipMosaicByVectorTask
from tasks.depression_fill_task import DepressionFillTask
from tasks.catchment_task import AccumulationTask
import logging
from qgis.core import QgsApplication, QgsVectorLayer, QgsVectorFileWriter, QgsProject, QgsVectorFileWriter, QgsProcessingFeedback, QgsFeatureRequest, QgsFeature, QgsMessageLog, QgsTaskManager, QgsTask, QgsCoordinateReferenceSystem, QgsProviderRegistry
from dual_logger import log  # Make sure dual_logger.py is accessible
from processing_saga_nextgen.processing.provider import SagaNextGenAlgorithmProvider

# Initialize the QGIS Application
qgs = QgsApplication([], False)
qgs.initQgis()

# Initialize QGIS and Processing framework
Processing.initialize()
feedback = QgsProcessingFeedback()


def write_log_message(message, tag, level):
    with open(logfile_name, 'a') as logfile:
        logfile.write('{tag}({level}): {message}'.format(tag=tag, level=level, message=message))


def addLayerToStorage(layer):
    log(f"Saved layer '{layer.name()}' to folder '{saving_folder}'. Feature count is: {layer.featureCount()}", level=logging.INFO)
    QgsVectorFileWriter.writeAsVectorFormatV3(layer, f"{saving_folder}{layer.name()}", QgsProject.instance(
    ).transformContext(), QgsVectorFileWriter.SaveVectorOptions())


def save_algos_to_csv():
    algos = []  # Store algorithm details
    print(qgs.processingRegistry().algorithms())

    for alg in qgs.processingRegistry().algorithms():
        algos.append([alg.id(), alg.displayName()])

    # Save to CSV file
    with open('algos.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Algorithm ID', 'Display Name'])  # Header row
        writer.writerows(algos)


def main():
    provider = SagaNextGenAlgorithmProvider()
    QgsApplication.processingRegistry().addProvider(provider)

    # Initialize the project instance
    project = QgsProject.instance()
    project.clear()  # Clear any existing project data

    # Create the load layer tasks
    catchment_layer_name = "REGINEenhet"

    catchment_polygon_task = LoadLayerTask("Loading catchment data", catchment_layer_name,
                                           '../data/regine_enhet/NVEData/Nedborfelt_RegineEnhet.gml')
    catchment_polygon_task.layerLoaded.connect(addLayerToStorage)

    municipality_layer_name = "Kommune"
    municipality_polygon_task = LoadLayerTask("Loading municipality polygon", municipality_layer_name,
                                              '../data/kommune/Basisdata_3238_Nannestad_25832_Kommuner_GML.gml')
    municipality_polygon_task.layerLoaded.connect(addLayerToStorage)

    touching_layer_name = "CompleteWatersheds"
    # Create the find touching polygons task without adding it to the task manager yet
    touching_task = FindTouchingPolygonsTask(
        "Find Touching Polygons", touching_layer_name, catchment_layer_name, municipality_layer_name)
    touching_task.layerLoaded.connect(addLayerToStorage)

    raster_files = [os.path.join("../data/dtm1/dtm1/data/", f)
                    for f in os.listdir("../data/dtm1/dtm1/data/") if f.endswith('.tif')]

    complete_mosaic_path = "../data/dtm1/dtm1/clipped2/mosaic.tif"
    clipped_mosaic_path = "../data/dtm1/dtm1/clipped2/mosaic_clipped.tif"

    create_mosaic_task = CreateMosaicTask("Create Mosaic of raster files",
                                          raster_files, complete_mosaic_path)

    clip_mosaic_task = ClipMosaicByVectorTask("Clip mosaic by vector polygon",
                                              complete_mosaic_path, touching_layer_name, clipped_mosaic_path)

    water_layer_name = "Elv"
    water_task = LoadLayerTask("Test open layer task", water_layer_name,
                               "../data/vann/Basisdata_3238_Nannestad_5972_FKB-Vann_GML.gml")

    # Add load layer tasks as subtasks to the find touching polygons task
    # Note: Adjust the addSubTask method according to your task class implementation
    touching_task.addSubTask(catchment_polygon_task, [], QgsTask.ParentDependsOnSubTask)
    touching_task.addSubTask(municipality_polygon_task, [], QgsTask.ParentDependsOnSubTask)
    clip_mosaic_task.addSubTask(create_mosaic_task, [], QgsTask.ParentDependsOnSubTask)

    depression_filled_path = "../data/dtm1/dtm1/clipped2/depression_filled.tif"
    accumulation_path = "../data/dtm1/dtm1/clipped2/accumulation.tif"
    catchment_task = AccumulationTask("Catchment layer task", depression_filled_path, 2, accumulation_path)

    # # Now add the main task to the task manager, which includes its subtasks
    # QgsApplication.taskManager().addTask(touching_task)
    #
    # QgsApplication.taskManager().addTask(clip_mosaic_task)

    QgsApplication.taskManager().addTask(catchment_task)

    # Setup the event loop to wait for tasks to finish
    loop = QEventLoop()
    QgsApplication.taskManager().allTasksFinished.connect(loop.quit)
    loop.exec_()

    # Cleanup QGIS application
    qgs.exitQgis()


if __name__ == "__main__":
    main()
