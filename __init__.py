def classFactory(iface):
  from .isochrones import Isochrones
  return Isochrones(iface)
