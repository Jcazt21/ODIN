"""Catálogo semilla de siglas dominicanas (alias -> nombre canónico).

Se usa una sola vez para poblar la tabla `entity_aliases`; a partir de ahí la
lista es editable desde el frontend (CRUD), no desde este archivo. Volver a
correr la carga no duplica: solo inserta las siglas que aún no existen.

Por qué una lista curada si ya hay fusión automática por iniciales
(`LocalAnalyzer._merge_aliases`):

  * Siglas por iniciales (JCE, PLD, DGII, FDD, ONU...) las resuelve el
    algoritmo solo — están aquí igual para poder canonizar ENTRE artículos,
    no solo dentro de uno.
  * Siglas silábicas (MINERD, INTRANT, SENASA, INDOTEL, EDESUR, LIDOM...)
    NO se derivan de las iniciales del nombre completo. Estas solo se pueden
    resolver con un catálogo explícito como este.

Formato: (sigla, nombre_canónico, tipo)
"""
from __future__ import annotations

# fmt: off
SEED_ALIASES: list[tuple[str, str, str]] = [
    # --- Partidos políticos ---
    ("PRM",   "Partido Revolucionario Moderno", "ORG"),
    ("PLD",   "Partido de la Liberación Dominicana", "ORG"),
    ("FP",    "Fuerza del Pueblo", "ORG"),
    ("PRD",   "Partido Revolucionario Dominicano", "ORG"),
    ("PRSC",  "Partido Reformista Social Cristiano", "ORG"),

    # --- Órganos electorales, judiciales y de investigación ---
    ("JCE",      "Junta Central Electoral", "ORG"),
    ("TSE",      "Tribunal Superior Electoral", "ORG"),
    ("TC",       "Tribunal Constitucional", "ORG"),
    ("SCJ",      "Suprema Corte de Justicia", "ORG"),
    ("CNM",      "Consejo Nacional de la Magistratura", "ORG"),
    ("PGR",      "Procuraduría General de la República", "ORG"),
    ("DNCD",     "Dirección Nacional de Control de Drogas", "ORG"),
    ("DICRIM",   "Dirección Central de Investigaciones Criminales", "ORG"),
    ("DIGESETT", "Dirección General de Seguridad de Tránsito y Transporte Terrestre", "ORG"),

    # --- Ministerios ---
    ("MINERD",  "Ministerio de Educación de la República Dominicana", "ORG"),
    ("MISPAS",  "Ministerio de Salud Pública y Asistencia Social", "ORG"),
    ("MOPC",    "Ministerio de Obras Públicas y Comunicaciones", "ORG"),
    ("MESCYT",  "Ministerio de Educación Superior, Ciencia y Tecnología", "ORG"),
    ("MIREX",   "Ministerio de Relaciones Exteriores", "ORG"),
    ("MIDE",    "Ministerio de Defensa", "ORG"),
    ("MICM",    "Ministerio de Industria, Comercio y Mipymes", "ORG"),
    ("MEPYD",   "Ministerio de Economía, Planificación y Desarrollo", "ORG"),
    ("MINPRE",  "Ministerio de la Presidencia", "ORG"),
    ("MAP",     "Ministerio de Administración Pública", "ORG"),
    ("MITUR",   "Ministerio de Turismo", "ORG"),
    ("MIVED",   "Ministerio de la Vivienda y Edificaciones", "ORG"),
    ("MIMARENA", "Ministerio de Medio Ambiente y Recursos Naturales", "ORG"),

    # --- Recaudación y finanzas públicas ---
    ("DGII",        "Dirección General de Impuestos Internos", "ORG"),
    ("DGA",         "Dirección General de Aduanas", "ORG"),
    ("DGCP",        "Dirección General de Contrataciones Públicas", "ORG"),
    ("BCRD",        "Banco Central de la República Dominicana", "ORG"),
    ("BANRESERVAS", "Banco de Reservas de la República Dominicana", "ORG"),
    ("SB",          "Superintendencia de Bancos", "ORG"),
    ("SIMV",        "Superintendencia del Mercado de Valores", "ORG"),
    ("ABA",         "Asociación de Bancos Múltiples de la República Dominicana", "ORG"),

    # --- Seguridad social y salud ---
    ("TSS",      "Tesorería de la Seguridad Social", "ORG"),
    ("CNSS",     "Consejo Nacional de Seguridad Social", "ORG"),
    ("SISALRIL", "Superintendencia de Salud y Riesgos Laborales", "ORG"),
    ("SENASA",   "Seguro Nacional de Salud", "ORG"),
    ("SNS",      "Servicio Nacional de Salud", "ORG"),
    ("PROMESE",  "Programa de Medicamentos Esenciales", "ORG"),

    # --- Educación, niñez y formación ---
    ("INABIE", "Instituto Nacional de Bienestar Estudiantil", "ORG"),
    ("INFOTEP", "Instituto Nacional de Formación Técnico Profesional", "ORG"),
    ("CONANI", "Consejo Nacional para la Niñez y la Adolescencia", "ORG"),
    ("INAIPI", "Instituto Nacional de Atención Integral a la Primera Infancia", "ORG"),

    # --- Universidades ---
    ("UASD",  "Universidad Autónoma de Santo Domingo", "ORG"),
    ("PUCMM", "Pontificia Universidad Católica Madre y Maestra", "ORG"),
    ("INTEC", "Instituto Tecnológico de Santo Domingo", "ORG"),
    ("UNPHU", "Universidad Nacional Pedro Henríquez Ureña", "ORG"),
    ("UNIBE", "Universidad Iberoamericana", "ORG"),
    ("UTESA", "Universidad Tecnológica de Santiago", "ORG"),

    # --- Agua, energía y obras ---
    ("INAPA",    "Instituto Nacional de Aguas Potables y Alcantarillados", "ORG"),
    ("CAASD",    "Corporación del Acueducto y Alcantarillado de Santo Domingo", "ORG"),
    ("CORAASAN", "Corporación del Acueducto y Alcantarillado de Santiago", "ORG"),
    ("INDRHI",   "Instituto Nacional de Recursos Hidráulicos", "ORG"),
    ("SIE",      "Superintendencia de Electricidad", "ORG"),
    ("ETED",     "Empresa de Transmisión Eléctrica Dominicana", "ORG"),
    ("EGEHID",   "Empresa de Generación Hidroeléctrica Dominicana", "ORG"),
    ("EDESUR",   "Empresa Distribuidora de Electricidad del Sur", "ORG"),
    ("EDENORTE", "Empresa Distribuidora de Electricidad del Norte", "ORG"),
    ("EDEESTE",  "Empresa Distribuidora de Electricidad del Este", "ORG"),
    ("CDEEE",    "Corporación Dominicana de Empresas Eléctricas Estatales", "ORG"),
    ("ADIE",     "Asociación Dominicana de la Industria Eléctrica", "ORG"),

    # --- Transporte, tránsito y puertos ---
    ("INTRANT", "Instituto Nacional de Tránsito y Transporte Terrestre", "ORG"),
    ("OMSA",    "Oficina Metropolitana de Servicios de Autobuses", "ORG"),
    ("IDAC",    "Instituto Dominicano de Aviación Civil", "ORG"),
    ("JAC",     "Junta de Aviación Civil", "ORG"),
    ("APORDOM", "Autoridad Portuaria Dominicana", "ORG"),

    # --- Cuerpos especializados, emergencias y migración ---
    ("CESAC",    "Cuerpo Especializado en Seguridad Aeroportuaria", "ORG"),
    ("CESTUR",   "Cuerpo Especializado de Seguridad Turística", "ORG"),
    ("CESFRONT", "Cuerpo Especializado en Seguridad Fronteriza Terrestre", "ORG"),
    ("DGM",      "Dirección General de Migración", "ORG"),
    ("COE",      "Centro de Operaciones de Emergencias", "ORG"),
    ("ONAMET",   "Oficina Nacional de Meteorología", "ORG"),

    # --- Fuerzas del orden ---
    ("PN",   "Policía Nacional", "ORG"),
    ("FFAA", "Fuerzas Armadas", "ORG"),
    ("ERD",  "Ejército de República Dominicana", "ORG"),
    ("ARD",  "Armada de República Dominicana", "ORG"),
    ("FARD", "Fuerza Aérea de República Dominicana", "ORG"),

    # --- Regulación, estadística y consumo ---
    ("INDOTEL",       "Instituto Dominicano de las Telecomunicaciones", "ORG"),
    ("ONAPI",         "Oficina Nacional de la Propiedad Industrial", "ORG"),
    ("ONE",           "Oficina Nacional de Estadística", "ORG"),
    ("INDOCAL",       "Instituto Dominicano para la Calidad", "ORG"),
    ("PROCONSUMIDOR", "Instituto Nacional de Protección de los Derechos del Consumidor", "ORG"),

    # --- Programas sociales y agro ---
    ("SIUBEN",    "Sistema Único de Beneficiarios", "ORG"),
    ("INESPRE",   "Instituto Nacional de Estabilización de Precios", "ORG"),
    ("IAD",       "Instituto Agrario Dominicano", "ORG"),
    ("BAGRICOLA", "Banco Agrícola de la República Dominicana", "ORG"),

    # --- Gremios y sector privado ---
    ("CONEP",      "Consejo Nacional de la Empresa Privada", "ORG"),
    ("ANJE",       "Asociación Nacional de Jóvenes Empresarios", "ORG"),
    ("AIRD",       "Asociación de Industrias de la República Dominicana", "ORG"),
    ("ADOZONA",    "Asociación Dominicana de Zonas Francas", "ORG"),
    ("ASONAHORES", "Asociación de Hoteles y Turismo de la República Dominicana", "ORG"),
    ("ADP",        "Asociación Dominicana de Profesores", "ORG"),
    ("CMD",        "Colegio Médico Dominicano", "ORG"),
    ("CDP",        "Colegio Dominicano de Periodistas", "ORG"),
    ("FDD",        "Fundación Dominicana de Desarrollo", "ORG"),
    ("ADOMPRETUR", "Asociación Dominicana de Prensa Turística", "ORG"),

    # --- Deportes ---
    ("LIDOM",      "Liga de Béisbol Profesional de la República Dominicana", "ORG"),
    ("COD",        "Comité Olímpico Dominicano", "ORG"),
    ("FEDOFUTBOL", "Federación Dominicana de Fútbol", "ORG"),

    # --- Organismos internacionales de mención frecuente ---
    ("ONU",     "Organización de las Naciones Unidas", "ORG"),
    ("OEA",     "Organización de los Estados Americanos", "ORG"),
    ("OMS",     "Organización Mundial de la Salud", "ORG"),
    ("OPS",     "Organización Panamericana de la Salud", "ORG"),
    ("UNICEF",  "Fondo de las Naciones Unidas para la Infancia", "ORG"),
    ("PNUD",    "Programa de las Naciones Unidas para el Desarrollo", "ORG"),
    ("FMI",     "Fondo Monetario Internacional", "ORG"),
    ("BID",     "Banco Interamericano de Desarrollo", "ORG"),
    ("CEPAL",   "Comisión Económica para América Latina y el Caribe", "ORG"),
    ("OIM",     "Organización Internacional para las Migraciones", "ORG"),
    ("ACNUR",   "Alto Comisionado de las Naciones Unidas para los Refugiados", "ORG"),
    ("UNESCO",  "Organización de las Naciones Unidas para la Educación, la Ciencia y la Cultura", "ORG"),
    ("FAO",     "Organización de las Naciones Unidas para la Alimentación y la Agricultura", "ORG"),
    ("CARICOM", "Comunidad del Caribe", "ORG"),
    ("UE",      "Unión Europea", "ORG"),

    # --- Figuras públicas que la prensa suele nombrar solo por apellido o
    # nombre de pila. Solo formas INEQUÍVOCAS: apellidos compartidos por
    # varias figuras activas ("Mejía", "Fernández") NO van aquí — esos los
    # resuelve (o los deja en paz) la regla de apellido único contra la BD
    # en analysis/canonicalize.py. ---
    ("Abinader", "Luis Abinader", "PERSON"),
    ("Danilo",   "Danilo Medina", "PERSON"),
    ("Leonel",   "Leonel Fernández", "PERSON"),
]
# fmt: on
