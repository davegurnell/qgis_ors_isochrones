import os

from PyQt5 import uic
from PyQt5 import QtWidgets

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'isochronesDialogBase.ui'))

class IsochronesDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super(IsochronesDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.src_layer.setText('src_layer_name')
        self.des_layer.setText('des_layer_name')
        print(self.button_box)
