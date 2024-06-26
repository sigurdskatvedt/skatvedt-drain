from qgis.core import QgsProcessingFeedback, QgsRasterLayer, QgsVectorLayer
from dual_logger import log, ProgressBar
import logging
import sys
import os
import tempfile
import shutil
from datetime import datetime
from .base_task import BaseTask

# Add the path to Processing framework
sys.path.append('/usr/share/qgis/python/plugins/')

import processing
from processing.core.Processing import Processing


class RasterizeVectorTask(BaseTask):

    def __init__(self,
                 description,
                 gml_path,
                 layer_names,
                 reference_raster_path,
                 raster_output_path,
                 crs,
                 height=10):
        super().__init__(description)
        self.gml_path = gml_path
        self.layer_names = layer_names
        self.reference_raster_path = reference_raster_path
        self.raster_output_path = raster_output_path
        self.crs = crs
        self.height = height
        self.feedback = QgsProcessingFeedback()
        self.progress_bar = ProgressBar(
            description)  # Initialize the progress bar here

        # Connect the progressChanged signal to the progress_changed method
        self.feedback.progressChanged.connect(self.progress_changed)

    def progress_changed(self, progress):
        self.progress_bar.update(progress)

    def task(self):
        tempdir = tempfile.mkdtemp()

        # Load the reference raster layer
        reference_raster_layer = QgsRasterLayer(self.reference_raster_path,
                                                "Reference Raster")

        if not reference_raster_layer.isValid():
            log(f"Failed to load reference raster: {self.reference_raster_path}",
                level=logging.ERROR)
            return False

        try:
            rasters = []
            for name in self.layer_names:
                layer_path = f"{self.gml_path}|layername={name}"
                layer = QgsVectorLayer(layer_path, name, "ogr")
                if not layer.isValid():
                    log(f"Failed to load layer: {name} from {layer_path}",
                        level=logging.ERROR)
                    continue

                # Reproject the layer to EPSG:25833
                reprojected_layer_path = os.path.join(
                    tempdir, f"{name}_reprojected.gpkg")
                params = {
                    'INPUT': layer,
                    'TARGET_CRS': self.crs,
                    'OUTPUT': reprojected_layer_path
                }
                result = processing.run("native:reprojectlayer", params)
                if not result:
                    log(f"Failed to reproject layer: {name}",
                        level=logging.ERROR)
                    continue

                reprojected_layer = QgsVectorLayer(reprojected_layer_path,
                                                   f"{name}_reprojected",
                                                   "ogr")
                if not reprojected_layer.isValid():
                    log(f"Failed to load reprojected layer: {name}",
                        level=logging.ERROR)
                else:
                    log(f'Reprojected {name} to {self.crs.toProj()}')

                temp_raster_path = os.path.join(tempdir, f"{name}_raster.tif")

                params = {
                    'INPUT': reprojected_layer,
                    'BURN': self.height,
                    'UNITS': 0,
                    'WIDTH': reference_raster_layer.width(),
                    'HEIGHT': reference_raster_layer.height(),
                    'EXTENT': reference_raster_layer.extent(),
                    'INIT': 0,
                    'OPTIONS': '',
                    'DATA_TYPE': 5,
                    'OUTPUT': temp_raster_path
                }

                result = processing.run("gdal:rasterize", params)
                if result:
                    rasters.append(temp_raster_path)
                    log(f'Rasterized to {temp_raster_path}')

            if rasters:
                expression = ""
                for name in self.layer_names:
                    expression += f'"{name}_raster@1" + '
                expression = expression.rstrip(" +")

                params = {
                    'LAYERS': rasters,
                    'EXPRESSION': expression,
                    'OUTPUT': self.raster_output_path
                }

                result = processing.run("native:rastercalc",
                                        params,
                                        feedback=self.feedback)

                if result and os.path.exists(self.raster_output_path):
                    log(f"Rasterization and merging completed successfully. Output saved to: {self.raster_output_path}",
                        level=logging.INFO)
                    return True
                else:
                    log("Error, no result")
                    return False
            else:
                log("No rasters were created.", level=logging.ERROR)
                return False

        except Exception as e:
            self.exception = e
            log(f"Task {self.description()}, an error occurred: {e}", level=logging.ERROR)
            return False
        finally:
            shutil.rmtree(tempdir)  # Clean up the temporary directory
