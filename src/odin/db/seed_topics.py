"""Catálogo semilla de temas.

PLACEHOLDER: esta lista es un punto de partida plausible para prensa
dominicana. Reemplazar `SEED_TOPICS` por la lista real que entregue el cliente
antes de poner esto en producción. `load_seed()` es insert-only, así que
agregar entradas aquí y reiniciar la API las suma sin tocar las existentes;
quitar una de aquí NO la borra de la BD (eso es baja lógica desde la UI).

Formato: (name, slug, parent_slug|None, [aliases...]).
"""
from __future__ import annotations

SEED_TOPICS: list[tuple[str, str, str | None, list[str]]] = [
    ("Agua", "agua", None,
     ["agua potable", "acueducto", "suministro de agua", "escasez de agua",
      "INAPA", "CAASD", "corte de agua"]),
    ("Energía eléctrica", "energia-electrica", None,
     ["apagón", "apagones", "EDESUR", "EDENORTE", "EDEESTE", "factura eléctrica",
      "tarifa eléctrica", "servicio eléctrico"]),
    ("Seguridad ciudadana", "seguridad-ciudadana", None,
     ["delincuencia", "criminalidad", "Policía Nacional", "atraco", "homicidio",
      "inseguridad"]),
    ("Salud", "salud", None,
     ["hospital", "SNS", "Salud Pública", "dengue", "servicios de salud",
      "Ministerio de Salud"]),
    ("Educación", "educacion", None,
     ["MINERD", "escuela", "tanda extendida", "maestros", "ADP", "año escolar"]),
    ("Transporte", "transporte", None,
     ["OMSA", "INTRANT", "metro", "teleférico", "peaje", "transporte público"]),
    ("Corrupción", "corrupcion", None,
     ["PEPCA", "soborno", "lavado de activos", "Punta Catalina", "Odebrecht",
      "malversación"]),
]
