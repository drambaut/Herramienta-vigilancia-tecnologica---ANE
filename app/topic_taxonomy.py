"""Taxonomías controladas y normalización para la capa de datos del dashboard."""
from __future__ import annotations
import ast
import json
import re
import unicodedata
from typing import Any, Mapping

TEMAS_ESTRATEGICOS = ["Disponibilidad de espectro para IMT", "Conectividad satelital, NTN y D2D", "Bandas medias y altas para servicios móviles", "6 GHz, Wi-Fi e IMT", "Spectrum sharing y mecanismos flexibles", "Redes privadas y verticales industriales", "Armonización y gestión internacional", "Necesidades transversales y capacidades institucionales", "Otros temas de seguimiento"]
LINEAS_PMGE = ["Disponibilidad de espectro", "Conectividad satelital", "Innovación en gestión y uso del espectro", "Gestión internacional del espectro", "Necesidades transversales"]
TIPOS_INSUMO_AGENDA = ["Nueva iniciativa", "Ajuste a iniciativa existente", "Nota técnica", "Seguimiento", "No prioritario"]
RELEVANCIA_LABELS = ["Alta", "Media", "Baja"]
TIPOS_EVENTO_REGULATORIO = ["Subasta", "Consulta pública", "Refarming", "Asignación de espectro", "Compartición de espectro", "Renovación", "Topes de espectro", "Tasas / fees", "Condiciones técnicas", "Armonización internacional", "Salud / EMF", "Otro"]

def _key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return re.sub(r"\s+", " ", "".join(c for c in text if not unicodedata.combining(c)).strip().casefold())

TECHNOLOGY_NORMALIZATION = {
    "5g": "5G", "5g sa": "5G", "5g stand alone": "5G", "5g-advanced": "5G-Advanced", "5g advanced": "5G-Advanced", "6g": "6G",
    "d2d": "D2D", "direct-to-device": "D2D", "direct to device": "D2D", "ntn": "NTN", "non-terrestrial networks": "NTN", "redes no terrestres": "NTN",
    "iot": "IoT", "nb-iot": "NB-IoT", "nb iot": "NB-IoT", "wi-fi": "Wi-Fi", "wifi": "Wi-Fi", "wi fi": "Wi-Fi", "wi-fi 6e": "Wi-Fi 6E", "wifi 6e": "Wi-Fi 6E", "wi-fi 7": "Wi-Fi 7", "wifi 7": "Wi-Fi 7",
    "open ran": "Open RAN", "open-ran": "Open RAN", "haps": "HAPS", "leo": "LEO", "meo": "MEO", "geo": "GEO", "tvws": "TVWS",
    "ia": "IA", "ai": "IA", "inteligencia artificial": "IA", "artificial intelligence": "IA", "mmwave": "mmWave", "mm wave": "mmWave",
    "redes privadas": "Redes privadas", "private networks": "Redes privadas", "spectrum sharing": "Spectrum sharing", "comparticion de espectro": "Spectrum sharing",
}
BAND_NORMALIZATION = {
    "600 mhz": "600 MHz", "700 mhz": "700 MHz", "800 mhz": "800 MHz", "900 mhz": "900 MHz", "1800 mhz": "1800 MHz",
    "2.1 ghz": "2.1 GHz", "2,1 ghz": "2.1 GHz", "2.3 ghz": "2.3 GHz", "2,3 ghz": "2.3 GHz", "2.6 ghz": "2.6 GHz", "2,6 ghz": "2.6 GHz",
    "3.3-3.8 ghz": "3.3-3.8 GHz", "3,3-3,8 ghz": "3.3-3.8 GHz", "3.5 ghz": "3.5 GHz", "3,5 ghz": "3.5 GHz", "6 ghz": "6 GHz", "upper 6 ghz": "upper 6 GHz", "6 ghz superior": "upper 6 GHz",
    "26 ghz": "26 GHz", "28 ghz": "28 GHz", "37 ghz": "37 GHz", "40 ghz": "40 GHz", "mmwave": "mmWave", "mm wave": "mmWave", "uhf": "UHF", "vhf": "VHF",
    "banda ka": "banda Ka", "ka-band": "banda Ka", "ka band": "banda Ka", "banda ku": "banda Ku", "ku-band": "banda Ku", "ku band": "banda Ku",
}

def normalize_text_label(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:1].upper() + text[1:] if text else ""

def parse_list_field(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and value != value): return []
    if isinstance(value, (list, tuple, set)): return [str(x).strip() for x in value if str(x).strip()]
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "null", "[]"}: return []
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
            if isinstance(parsed, (list, tuple, set)): return [str(x).strip() for x in parsed if str(x).strip()]
        except (ValueError, SyntaxError, TypeError, json.JSONDecodeError): pass
    return [x.strip() for x in re.split(r"[;,|]", text) if x.strip()]

def normalize_list(values: Any, normalization_dict: Mapping[str, str]) -> list[str]:
    lookup = {_key(k): v for k, v in normalization_dict.items()}
    result: list[str] = []
    for raw in parse_list_field(values):
        key = _key(raw)
        canonical = lookup.get(key)
        if canonical is None:
            matches = [(len(alias), value) for alias, value in lookup.items() if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", key)]
            canonical = max(matches, default=(0, normalize_text_label(raw)))[1]
        if canonical and canonical not in result: result.append(canonical)
    return result

def normalize_technologies(values: Any) -> list[str]: return normalize_list(values, TECHNOLOGY_NORMALIZATION)
def normalize_bands(values: Any) -> list[str]: return normalize_list(values, BAND_NORMALIZATION)

def infer_tema_estrategico(tecnologias: Any, bandas: Any, senal_regulatoria: Any, tema_principal: str = "", resumen: str = "") -> str:
    haystack = " " + _key(" ".join(normalize_technologies(tecnologias) + normalize_bands(bandas) + [str(senal_regulatoria), tema_principal, resumen])) + " "
    rules = [
        (["d2d", "ntn", "satelit", "leo", "meo", "geo", "haps"], TEMAS_ESTRATEGICOS[1]),
        (["700 mhz", "3.5 ghz", "imt", "5g", "5g-advanced"], TEMAS_ESTRATEGICOS[0]),
        (["26 ghz", "28 ghz", "37 ghz", "40 ghz", "mmwave"], TEMAS_ESTRATEGICOS[2]),
        (["6 ghz", "wi-fi", "wifi", "wi fi 6e", "wi fi 7"], TEMAS_ESTRATEGICOS[3]),
        (["spectrum sharing", "comparticion", "dynamic sharing", " ia ", " ai ", "inteligencia artificial"], TEMAS_ESTRATEGICOS[4]),
        (["redes privadas", "private networks", "verticales industriales"], TEMAS_ESTRATEGICOS[5]),
        (["armonizacion", "wrc", "cmr", "uit", "citel", "itu"], TEMAS_ESTRATEGICOS[6]),
    ]
    for needles, topic in rules:
        if any(n in haystack for n in needles): return topic
    return TEMAS_ESTRATEGICOS[-1]

def map_tema_to_linea_pmge(tema_estrategico: str) -> str:
    mapping = {TEMAS_ESTRATEGICOS[0]: LINEAS_PMGE[0], TEMAS_ESTRATEGICOS[2]: LINEAS_PMGE[0], TEMAS_ESTRATEGICOS[3]: LINEAS_PMGE[0], TEMAS_ESTRATEGICOS[1]: LINEAS_PMGE[1], TEMAS_ESTRATEGICOS[4]: LINEAS_PMGE[2], TEMAS_ESTRATEGICOS[5]: LINEAS_PMGE[2], TEMAS_ESTRATEGICOS[6]: LINEAS_PMGE[3], TEMAS_ESTRATEGICOS[7]: LINEAS_PMGE[4], TEMAS_ESTRATEGICOS[8]: LINEAS_PMGE[4]}
    return mapping.get(tema_estrategico, LINEAS_PMGE[4])

def infer_tipo_evento_regulatorio(text: str) -> list[str]:
    haystack = _key(text)
    rules = [("Subasta", ["subasta", "auction"]), ("Consulta pública", ["consulta publica", "public consultation"]), ("Refarming", ["refarming", "reordenamiento"]), ("Asignación de espectro", ["asignacion", "licenciamiento", "assignment"]), ("Compartición de espectro", ["comparticion", "spectrum sharing"]), ("Renovación", ["renovacion", "renewal"]), ("Topes de espectro", ["tope de espectro", "spectrum cap"]), ("Tasas / fees", ["tasa", "tarifa", "fee", "pricing"]), ("Condiciones técnicas", ["condiciones tecnicas", "technical condition"]), ("Armonización internacional", ["armonizacion", "wrc", "cmr", "uit", "itu", "citel"]), ("Salud / EMF", ["emf", "campo electromagnet", "salud"])]
    found = [label for label, terms in rules if any(term in haystack for term in terms)]
    return found or ["Otro"]
