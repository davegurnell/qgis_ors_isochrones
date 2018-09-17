import os.path
from time import sleep

from qgis.core import QgsExpression, QgsFeature, QgsFeatureRequest, QgsMessageLog, QgsProject

from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction

from .isochronesDialog import IsochronesDialog

# ============================================= #
# CONFIGURATION                                 #
# ============================================= #

# API URL template:
TEMPLATE_URL  = "https://api.openrouteservice.org/isochrones?api_key={API_KEY}&locations={LNG}%2C{LAT}&profile={PROFILE}&range_type={RANGE_TYPE}&range={RANGE}&interval={INTERVAL}&units={UNITS}&location_type={LOCATION_TYPE}&attributes={ATTRIBUTES}&options={OPTIONS}&intersections={INTERSECTIONS}&id={ID}"

# URL template parameters:
API_KEY       = os.environ["OPENROUTESERVICE_API_KEY"] # set this environment variable or replace this key with a literal string
PROFILE       = "foot-walking"
RANGE_TYPE    = "distance"
RANGE         = "300"
INTERVAL      = "100"
UNITS         = "m"
LOCATION_TYPE = "start"
ATTRIBUTES    = ""
OPTIONS       = ""
ID            = ""
INTERSECTIONS = ""

# Other parameters:
THROTTLE      = 2  # seconds between requests
STOP_AFTER    = 10 # max isochrones to generate (ignores existing ones, set to 0 to remove max)

# ============================================= #
# END OF CONFIGURATION                          #
# ============================================= #

class Isochrones:
    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface

        # Initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        QgsMessageLog.logMessage("Initialising isochrones")

        # Declare instance attributes
        self.actions = []
        self.menu = u'&Isochrones'

        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'Isochrones')
        self.toolbar.setObjectName(u'Isochrones')

        self.dialog = IsochronesDialog()

        self.bypass_dialog()

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToVectorMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        icon_path = ':/plugins/isochrones/icon.png'
        self.add_action(
            icon_path,
            text=u'Generate isochrones',
            callback=self.show_dialog,
            parent=self.iface.mainWindow())

    def unload(self):
        for action in self.actions:
            self.iface.removePluginVectorMenu(u'&Isochrones', action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar


    def show_dialog(self):
        QgsMessageLog.logMessage('show_dialog')

        src_layer = self.iface.activeLayer()

        if src_layer is None:
            self.dialog.src_layer.setText('')
            self.dialog.des_layer.setText('')
        else:
            self.dialog.src_layer.setText(src_layer.name())
            self.dialog.des_layer.setText('')

        self.dialog.show()
        result = self.dialog.exec_()

        QgsMessageLog.logMessage('  - result ' + str(result))

        if result == 1:
            self.find_layers(self.dialog.src_layer.text(), self.dialog.des_layer.text())

    def bypass_dialog(self):
        QgsMessageLog.logMessage('bypass_dialog')
        self.find_layers('PublicOpenspaceAccessPoints', 'Isochrones')

    def find_layers(self, src_layer_name, des_layer_name):
        src_layers = QgsProject.instance().mapLayersByName(src_layer_name)
        des_layers = QgsProject.instance().mapLayersByName(des_layer_name)

        if len(src_layers) < 0 or len(des_layers) < 0:
            self.iface.messageBar().pushMessage("Isochrones", "Sorry! I can't find those layers.")
            return

        src_layer = src_layers[0]
        des_layer = des_layers[0]

        shared_fields = []
        for field in src_layer.fields():
            name = field.name()
            QgsMessageLog.logMessage("Inprogresszo ((" + name + "))")
            if des_layer.fields().lookupField(name) >= 0:
                shared_fields.append(name)

        QgsMessageLog.logMessage('  - src_layer ' + src_layer.name())
        QgsMessageLog.logMessage('  - des_layer ' + des_layer.name())
        QgsMessageLog.logMessage('  - shared_fields ' + str(shared_fields))

        self.iface.messageBar().pushMessage("Isochrones", "Generating isochrones, taking source data from '{}', writing target data to '{}', copying the following attributes: {}".format(src_layer.name(), des_layer.name(), ", ".join(shared_fields)))

        self.process_all_features(src_layer, des_layer, shared_fields)

    def process_all_features(self, src_layer, des_layer, shared_fields):
        counter = 0
        for src_feature in src_layer.getFeatures():
            counter = counter + self.process_feature(counter, src_feature, des_layer, shared_fields)
            if STOP_AFTER > 0 and counter > STOP_AFTER:
                return

    def process_feature(self, counter, src_feature, des_layer, shared_fields):
        QgsMessageLog.logMessage("process_feature " + str(counter))

        point = src_feature.geometry().asPoint()
        if point is None:
            QgsMessageLog.logMessage("  - not a point feature")
            return 0

        search_expr = self.search_expr(src_feature, des_layer, shared_fields)
        QgsMessageLog.logMessage("  - search_expr " + search_expr)

        des_features = des_layer.getFeatures(QgsFeatureRequest(QgsExpression(search_expr)))

        if des_features.compileFailed():
            self.iface.messageBar().pushMessage("Isochrones", "Failed to compile search_expr: " + search_expr)
            return 0

        for des_feature in des_features:
            QgsMessageLog.logMessage("  - already present")
            des_features.close()
            return 0

        des_features.close()
        QgsMessageLog.logMessage("  - not present")

        temp_layer = self.create_geojson_layer(counter, point, des_layer)

        QgsMessageLog.logMessage("  - temp layer " + temp_layer.name())

        des_features = []
        for temp_feature in temp_layer.getFeatures():
            QgsMessageLog.logMessage("  - next temp feature")
            des_feature = QgsFeature(des_layer.fields())
            des_feature.setGeometry(temp_feature.geometry())
            QgsMessageLog.logMessage("    - copying fields " + str(shared_fields))
            for field in shared_fields:
                src_field = src_feature.attribute(field)
                QgsMessageLog.logMessage("    - field " + field + " = " + str(src_field))
                des_feature.setAttribute(field, src_field)
            des_features.append(des_feature)

        des_layer.dataProvider().addFeatures(des_features)

        self.delete_geojson_layer(temp_layer)

        return 1

    def create_geojson_layer(self, counter, point, des_layer):
        QgsMessageLog.logMessage("create_geojson_layer " + str(counter))
        if THROTTLE > 0:
            sleep(THROTTLE)
        url = TEMPLATE_URL.format(LNG = point.x(), LAT = point.y(), API_KEY = API_KEY, PROFILE = PROFILE, RANGE_TYPE = RANGE_TYPE, RANGE = RANGE, INTERVAL = INTERVAL, UNITS = UNITS, LOCATION_TYPE = LOCATION_TYPE, ATTRIBUTES = ATTRIBUTES, OPTIONS = OPTIONS, ID = ID, INTERSECTIONS = INTERSECTIONS)
        QgsMessageLog.logMessage("  - url " + url)
        return self.iface.addVectorLayer(url, "Isochrones temp " + str(counter), 'ogr')

    def delete_geojson_layer(self, layer):
        QgsProject.instance().removeMapLayers([ layer.name() ])

    def search_expr(self, feature, des_layer, shared_fields):
        search_terms = []
        for name in shared_fields:
            value = feature.attribute(name)
            search_term = ""
            search_term += '"' + name + '"'
            search_term += " = "
            search_term += self.quote_literal(value)
            search_terms.append(search_term)
        return " and ".join(search_terms)

    def quote_literal(self, literal):
        if isinstance(literal, str):
            return "'" + literal.replace("'", "''") + "'"
        else:
            return str(literal)