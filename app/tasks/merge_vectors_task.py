import logging
from qgis.core import QgsProcessingFeedback, QgsProject
from qgis import processing
from .base_task import BaseTask
from dual_logger import log

class MergeVectorLayersTask(BaseTask):

    def __init__(self, description, output_name, layer_names, crs):
        super().__init__(description, output_name)
        self.layer_names = layer_names if isinstance(
            layer_names, list) and len(layer_names) >= 2 else None
        self.output_name = output_name
        self.crs = crs
        self.merged_layer = None

    def task(self):
        if not self.layer_names:
            log('Error: layer_names must be a list with at least two layer names.',
                level=logging.ERROR)
            return False

        layers_to_merge = []

        # Search for the layers by name
        for layer_name in self.layer_names:
            layer = next((l for l in QgsProject.instance().mapLayers().values() if l.name() == layer_name), None)
            if not layer:
                log(f'Could not find layer with name {layer_name}', level=logging.ERROR)
                return False
            layers_to_merge.append(layer)

        log(f'Task "{self.description()}" starting, merging layers: {", ".join(self.layer_names)}',
            level=logging.INFO)

        params = {
            'LAYERS': layers_to_merge,
            'CRS': self.crs,
            'OUTPUT': 'memory:'
        }
        feedback = QgsProcessingFeedback()
        try:
            result = processing.run("native:mergevectorlayers",
                                    params,
                                    feedback=feedback)
            self.merged_layer = result['OUTPUT']
            self.merged_layer.setName(self.output_name)
            log(f'Completed task "{self.description()}", merged layers into {self.output_name}.gml',
                level=logging.INFO)
            QgsProject.instance().addMapLayer(self.merged_layer)
            return True
        except Exception as e:
            log(f'Error in task "{self.description()}": {e}',
                level=logging.ERROR)
            return False
