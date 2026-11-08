# -*- coding: utf-8 -*-
"""FeatureHopper - simpel feature-til-feature navigation for QGIS."""


def classFactory(iface):
    from .feature_hopper import FeatureHopper
    return FeatureHopper(iface)
