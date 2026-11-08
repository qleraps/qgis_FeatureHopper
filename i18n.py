# -*- coding: utf-8 -*-
"""User-interface texts in English and Danish.

The language follows QGIS' own language setting (Settings > Options >
General): Danish if QGIS runs in Danish, otherwise English. QGIS only changes
language on restart, so it is decided once, the first time a text is needed.
Texts are looked up by key; a key missing in Danish falls back to English.
"""

_language = None


def _detect_language():
    try:
        from qgis.core import QgsSettings
        from qgis.PyQt.QtCore import QLocale

        settings = QgsSettings()
        if settings.value("locale/overrideFlag", False, type=bool):
            locale = str(settings.value("locale/userLocale", "") or "")
        else:
            locale = QLocale.system().name()
    except Exception:
        locale = ""
    return "da" if locale.lower().startswith("da") else "en"


def language():
    global _language
    if _language is None:
        _language = _detect_language()
    return _language


def set_language(lang):
    global _language
    _language = lang


def tr(key, *args):
    text = STRINGS.get(language(), {}).get(key)
    if text is None:
        text = STRINGS["en"].get(key, key)
    return text % args if args else text


STRINGS = {
    "en": {
        "use_active_layer": "⤓ Switch to active layer",
        "use_active_layer_tip": "Set the layer selection to the layer that is currently active in the Layers panel",
        "layer_label": "Layer:",
        "previous": "◀ Previous",
        "previous_tip": "Previous feature (left arrow key)",
        "next": "Next ▶",
        "next_tip": "Next feature (right arrow key)",
        "count_none": "- of -",
        "count_total": "- of %d",
        "count_position": "%d of %d",
        "auto_select": "Select feature automatically when hopping",
        "search_field_label": "Search in field:",
        "search_placeholder": "Type the beginning of the value...",
        "show_label": "Show label with the value from the search field",
        "show_label_tip": "Shows a label on the map at the selected feature, with the value from the field chosen in 'Search in field'",
        "warn_no_active_layer": "No vector layer is active in the Layers panel.",
        "warn_layer_not_listed": "The active layer is not in FeatureHopper's layer list.",
        "warn_no_geometry": "The feature has no geometry - cannot zoom/pan.",
        "warn_no_match": "No match found.",
    },
    "da": {
        "use_active_layer": "⤓ Skift til aktivt lag",
        "use_active_layer_tip": "Sæt lag-valget til det lag, der lige nu er aktivt i Lag-panelet",
        "layer_label": "Lag:",
        "previous": "◀ Forrige",
        "previous_tip": "Forrige feature (venstre piletast)",
        "next": "Næste ▶",
        "next_tip": "Næste feature (højre piletast)",
        "count_none": "- af -",
        "count_total": "- af %d",
        "count_position": "%d af %d",
        "auto_select": "Vælg feature automatisk ved hop",
        "search_field_label": "Søg i felt:",
        "search_placeholder": "Indtast begyndelsen af værdien...",
        "show_label": "Vis label med værdi fra søgefeltet",
        "show_label_tip": "Viser en label på kortet ved den valgte feature, med værdien fra feltet valgt i 'Søg i felt'",
        "warn_no_active_layer": "Intet vektorlag er aktivt i Lag-panelet.",
        "warn_layer_not_listed": "Det aktive lag findes ikke i FeatureHoppers lagliste.",
        "warn_no_geometry": "Featuren har ingen geometri - kan ikke zoome/panorere.",
        "warn_no_match": "Ingen match fundet.",
    },
}
