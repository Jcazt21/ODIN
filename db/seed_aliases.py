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
    ("PRM",     "Partido Revolucionario Moderno", "ORG"),
    ("PLD",     "Partido de la Liberación Dominicana", "ORG"),
    ("FP",      "Fuerza del Pueblo", "ORG"),
    ("PRD",     "Partido Revolucionario Dominicano", "ORG"),
    ("PRSC",    "Partido Reformista Social Cristiano", "ORG"),
    ("ALPAIS",  "Alianza País", "ORG"),
    ("DxC",     "Dominicanos por el Cambio", "ORG"),
    ("BIS",     "Bloque Institucional Social Demócrata", "ORG"),
    ("PHD",     "Partido Humanista Dominicano", "ORG"),
    ("MODA",    "Movimiento Democrático Alternativo", "ORG"),
    ("PRSD",    "Partido Revolucionario Social Demócrata", "ORG"),
    ("PQDC",    "Partido Quisqueyano Demócrata Cristiano", "ORG"),
    ("PAL",     "Partido de Acción Liberal", "ORG"),
    ("UDC",     "Unión Demócrata Cristiana", "ORG"),
    ("FNP",     "Fuerza Nacional Progresista", "ORG"),
    ("PNVC",    "Partido Nacional Voluntad Ciudadana", "ORG"),
    ("PPG",     "Partido Primero la Gente", "ORG"),
    ("PED",     "Partido Esperanza Democrática", "ORG"),
    ("PPC",     "Partido Popular Cristiano", "ORG"),
    ("PRI",     "Partido Revolucionario Independiente", "ORG"),

    # --- Órganos electorales, judiciales, de investigación y ética ---
    ("JCE",      "Junta Central Electoral", "ORG"),
    ("TSE",      "Tribunal Superior Electoral", "ORG"),
    ("TC",       "Tribunal Constitucional", "ORG"),
    ("SCJ",      "Suprema Corte de Justicia", "ORG"),
    ("CNM",      "Consejo Nacional de la Magistratura", "ORG"),
    ("PGR",      "Procuraduría General de la República", "ORG"),
    ("PEPCA",    "Procuraduría Especializada de Persecución de la Corrupción Administrativa", "ORG"),
    ("INACIF",   "Instituto Nacional de Ciencias Forenses", "ORG"),
    ("DNCD",     "Dirección Nacional de Control de Drogas", "ORG"),
    ("DICRIM",   "Dirección Central de Investigaciones Criminales", "ORG"),
    ("DIGESETT", "Dirección General de Seguridad de Tránsito y Transporte Terrestre", "ORG"),
    ("DIGEIG",   "Dirección General de Ética e Integridad Gubernamental", "ORG"),
    ("DP",       "Defensor del Pueblo", "ORG"),

    # --- Ministerios ---
    ("MINERD",      "Ministerio de Educación de la República Dominicana", "ORG"),
    ("MISPAS",      "Ministerio de Salud Pública y Asistencia Social", "ORG"),
    ("MOPC",        "Ministerio de Obras Públicas y Comunicaciones", "ORG"),
    ("MESCYT",      "Ministerio de Educación Superior, Ciencia y Tecnología", "ORG"),
    ("MIREX",       "Ministerio de Relaciones Exteriores", "ORG"),
    ("MIDE",        "Ministerio de Defensa", "ORG"),
    ("MICM",        "Ministerio de Industria, Comercio y Mipymes", "ORG"),
    ("MEPYD",       "Ministerio de Economía, Planificación y Desarrollo", "ORG"),
    ("MINPRE",      "Ministerio de la Presidencia", "ORG"),
    ("MAPRE",       "Ministerio Administrativo de la Presidencia", "ORG"),
    ("MAP",         "Ministerio de Administración Pública", "ORG"),
    ("MITUR",       "Ministerio de Turismo", "ORG"),
    ("MIVED",       "Ministerio de la Vivienda y Edificaciones", "ORG"),
    ("MIVHED",      "Ministerio de la Vivienda y Edificaciones", "ORG"),
    ("MIMARENA",    "Ministerio de Medio Ambiente y Recursos Naturales", "ORG"),
    ("MH",          "Ministerio de Hacienda", "ORG"),
    ("MIP",         "Ministerio de Interior y Policía", "ORG"),
    ("MMUJER",      "Ministerio de la Mujer", "ORG"),
    ("MIDEREC",     "Ministerio de Deportes, Educación Física y Recreación", "ORG"),
    ("MINC",        "Ministerio de Cultura", "ORG"),
    ("MEM",         "Ministerio de Energía y Minas", "ORG"),
    ("MJ",          "Ministerio de la Juventud", "ORG"),
    ("MT",          "Ministerio de Trabajo", "ORG"),
    ("AGRICULTURA", "Ministerio de Agricultura", "ORG"),

    # --- Recaudación, finanzas públicas y sector financiero ---
    ("DGII",        "Dirección General de Impuestos Internos", "ORG"),
    ("DGA",         "Dirección General de Aduanas", "ORG"),
    ("DGCP",        "Dirección General de Contrataciones Públicas", "ORG"),
    ("DGP",         "Dirección General de Presupuesto", "ORG"),
    ("DIGECOG",     "Dirección General de Contabilidad Gubernamental", "ORG"),
    ("CAPGEFI",     "Centro de Capacitación en Política y Gestión Fiscal", "ORG"),
    ("BCRD",        "Banco Central de la República Dominicana", "ORG"),
    ("BANRESERVAS", "Banco de Reservas de la República Dominicana", "ORG"),
    ("BANDEX",      "Banco de Desarrollo y Exportaciones", "ORG"),
    ("SB",          "Superintendencia de Bancos", "ORG"),
    ("SIMV",        "Superintendencia del Mercado de Valores", "ORG"),
    ("SIPEN",       "Superintendencia de Pensiones", "ORG"),
    ("ABA",         "Asociación de Bancos Múltiples de la República Dominicana", "ORG"),
    ("BHD",         "Banco BHD", "ORG"),
    ("BPD",         "Banco Popular Dominicano", "ORG"),

    # --- Seguridad social, salud y riesgos laborales ---
    ("TSS",         "Tesorería de la Seguridad Social", "ORG"),
    ("CNSS",        "Consejo Nacional de Seguridad Social", "ORG"),
    ("SISALRIL",    "Superintendencia de Salud y Riesgos Laborales", "ORG"),
    ("SENASA",      "Seguro Nacional de Salud", "ORG"),
    ("SNS",         "Servicio Nacional de Salud", "ORG"),
    ("PROMESE",     "Programa de Medicamentos Esenciales", "ORG"),
    ("IDOPPRIL",    "Instituto Dominicano de Prevención y Protección de Riesgos Laborales", "ORG"),
    ("IDOPPRAL",    "Instituto Dominicano de Prevención y Protección de Riesgos Laborales", "ORG"),
    ("CONAVIHSIDA", "Consejo Nacional para el VIH y el SIDA", "ORG"),
    ("DIGEMAPS",    "Dirección General de Medicamentos, Alimentos y Productos Sanitarios", "ORG"),

    # --- Educación, niñez, cultura y bienestar social ---
    ("INABIE",    "Instituto Nacional de Bienestar Estudiantil", "ORG"),
    ("INFOTEP",   "Instituto Nacional de Formación Técnico Profesional", "ORG"),
    ("INAFOCAM",  "Instituto Nacional de Formación y Capacitación del Magisterio", "ORG"),
    ("INEFI",     "Instituto Nacional de Educación Física", "ORG"),
    ("INABIMA",   "Instituto Nacional de Bienestar Magisterial", "ORG"),
    ("COOPNAMA",  "Cooperativa Nacional de Servicios Múltiples de los Maestros", "ORG"),
    ("CONANI",    "Consejo Nacional para la Niñez y la Adolescencia", "ORG"),
    ("INAIPI",    "Instituto Nacional de Atención Integral a la Primera Infancia", "ORG"),
    ("CONADIS",   "Consejo Nacional de Discapacidad", "ORG"),
    ("DGCINE",    "Dirección General de Cine", "ORG"),

    # --- Universidades ---
    ("UASD",   "Universidad Autónoma de Santo Domingo", "ORG"),
    ("PUCMM",  "Pontificia Universidad Católica Madre y Maestra", "ORG"),
    ("INTEC",  "Instituto Tecnológico de Santo Domingo", "ORG"),
    ("UNPHU",  "Universidad Nacional Pedro Henríquez Ureña", "ORG"),
    ("UNIBE",  "Universidad Iberoamericana", "ORG"),
    ("UTESA",  "Universidad Tecnológica de Santiago", "ORG"),
    ("UCSD",   "Universidad Católica Santo Domingo", "ORG"),
    ("UCNE",   "Universidad Católica Nordestana", "ORG"),
    ("UNAPEC", "Universidad APEC", "ORG"),
    ("UFHEC",  "Universidad Federico Henríquez y Carvajal", "ORG"),

    # --- Agua, energía, medio ambiente y climatología ---
    ("INAPA",       "Instituto Nacional de Aguas Potables y Alcantarillados", "ORG"),
    ("CAASD",       "Corporación del Acueducto y Alcantarillado de Santo Domingo", "ORG"),
    ("CORAASAN",    "Corporación del Acueducto y Alcantarillado de Santiago", "ORG"),
    ("CORAAPPLATA", "Corporación del Acueducto y Alcantarillado de Puerto Plata", "ORG"),
    ("CORAAMOCA",   "Corporación del Acueducto y Alcantarillado de Moca", "ORG"),
    ("CORAABO",     "Corporación del Acueducto y Alcantarillado de Boca Chica", "ORG"),
    ("CORAAROMANA", "Corporación del Acueducto y Alcantarillado de La Romana", "ORG"),
    ("CORAAVEGA",   "Corporación del Acueducto y Alcantarillado de La Vega", "ORG"),
    ("INDRHI",      "Instituto Nacional de Recursos Hidráulicos", "ORG"),
    ("SIE",         "Superintendencia de Electricidad", "ORG"),
    ("ETED",        "Empresa de Transmisión Eléctrica Dominicana", "ORG"),
    ("EGEHID",      "Empresa de Generación Hidroeléctrica Dominicana", "ORG"),
    ("EDESUR",      "Empresa Distribuidora de Electricidad del Sur", "ORG"),
    ("EDENORTE",    "Empresa Distribuidora de Electricidad del Norte", "ORG"),
    ("EDEESTE",     "Empresa Distribuidora de Electricidad del Este", "ORG"),
    ("CDEEE",       "Corporación Dominicana de Empresas Eléctricas Estatales", "ORG"),
    ("ADIE",        "Asociación Dominicana de la Industria Eléctrica", "ORG"),
    ("INDOMET",     "Instituto Dominicano de Meteorología", "ORG"),
    ("ONAMET",      "Oficina Nacional de Meteorología", "ORG"),

    # --- Transporte, tránsito y puertos ---
    ("INTRANT", "Instituto Nacional de Tránsito y Transporte Terrestre", "ORG"),
    ("OMSA",    "Oficina Metropolitana de Servicios de Autobuses", "ORG"),
    ("OPRET",   "Oficina para la Reorganización del Transporte", "ORG"),
    ("IDAC",    "Instituto Dominicano de Aviación Civil", "ORG"),
    ("JAC",     "Junta de Aviación Civil", "ORG"),
    ("APORDOM", "Autoridad Portuaria Dominicana", "ORG"),

    # --- Cuerpos especializados, emergencias y migración ---
    ("CESAC",    "Cuerpo Especializado en Seguridad Aeroportuaria", "ORG"),
    ("POLITUR",  "Dirección Central de Policía de Turismo", "ORG"),
    ("CESTUR",   "Dirección Central de Policía de Turismo", "ORG"),
    ("CESFRONT", "Cuerpo Especializado en Seguridad Fronteriza Terrestre", "ORG"),
    ("CECCOM",   "Cuerpo Especializado de Control de Combustibles y Comercio de Mercancías", "ORG"),
    ("DGM",      "Dirección General de Migración", "ORG"),
    ("COE",      "Centro de Operaciones de Emergencias", "ORG"),

    # --- Fuerzas del orden ---
    ("PN",   "Policía Nacional", "ORG"),
    ("FFAA", "Fuerzas Armadas", "ORG"),
    ("ERD",  "Ejército de República Dominicana", "ORG"),
    ("ARD",  "Armada de República Dominicana", "ORG"),
    ("FARD", "Fuerza Aérea de República Dominicana", "ORG"),

    # --- Regulación, tecnología, estadística y defensa del consumo/competencia ---
    ("INDOTEL",       "Instituto Dominicano de las Telecomunicaciones", "ORG"),
    ("OGTIC",         "Oficina Gubernamental de Tecnologías de la Información y Comunicación", "ORG"),
    ("OPTIC",         "Oficina Gubernamental de Tecnologías de la Información y Comunicación", "ORG"),
    ("ONAPI",         "Oficina Nacional de la Propiedad Industrial", "ORG"),
    ("ONE",           "Oficina Nacional de Estadística", "ORG"),
    ("INDOCAL",       "Instituto Dominicano para la Calidad", "ORG"),
    ("PROCONSUMIDOR", "Instituto Nacional de Protección de los Derechos del Consumidor", "ORG"),
    ("PROCOMPETENCIA", "Comisión Nacional de Defensa de la Competencia", "ORG"),

    # --- Programas sociales, fomento económico y agro ---
    ("SIUBEN",        "Sistema Único de Beneficiarios", "ORG"),
    ("SUPERATE",      "Programa Supérate", "ORG"),
    ("INESPRE",       "Instituto Nacional de Estabilización de Precios", "ORG"),
    ("IAD",           "Instituto Agrario Dominicano", "ORG"),
    ("BAGRICOLA",     "Banco Agrícola de la República Dominicana", "ORG"),
    ("PRODOMINICANA", "Centro de Exportación e Inversión de la República Dominicana", "ORG"),
    ("CEI-RD",        "Centro de Exportación e Inversión de la República Dominicana", "ORG"),
    ("CODOPESCA",     "Consejo Dominicano de Pesca y Acuicultura", "ORG"),
    ("JAD",           "Junta Agroempresarial Dominicana", "ORG"),
    ("FEDAGAN",       "Federación Nacional de Ganaderos", "ORG"),

    # --- Gobiernos locales y municipalidad ---
    ("ADN",    "Ayuntamiento del Distrito Nacional", "ORG"),
    ("ASDE",   "Ayuntamiento de Santo Domingo Este", "ORG"),
    ("ASDN",   "Ayuntamiento de Santo Domingo Norte", "ORG"),
    ("ASDO",   "Ayuntamiento de Santo Domingo Oeste", "ORG"),
    ("FEDOMU", "Federación Dominicana de Municipios", "ORG"),
    ("LMD",    "Liga Municipal Dominicana", "ORG"),

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
    ("CCPSD",      "Cámara de Comercio y Producción de Santo Domingo", "ORG"),
    ("CODIA",      "Colegio Dominicano de Ingenieros, Arquitectos y Agrimensores", "ORG"),
    ("CARD",       "Colegio de Abogados de la República Dominicana", "ORG"),

    # --- Medios de comunicación ---
    ("CDN",  "Cadena de Noticias", "ORG"),
    ("SIN",  "Servicios Informativos Nacionales", "ORG"),
    ("RNN",  "Red Nacional de Noticias", "ORG"),
    ("Z101", "Z101 Digital", "ORG"),

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
    ("Abinader",      "Luis Abinader", "PERSON"),
    ("Danilo",        "Danilo Medina", "PERSON"),
    ("Leonel",        "Leonel Fernández", "PERSON"),
    ("Hipólito",      "Hipólito Mejía", "PERSON"),
    ("Faride",        "Faride Raful", "PERSON"),
    ("Guido",         "Guido Gómez Mazara", "PERSON"),
    ("Yeni Berenice", "Yeni Berenice Reynoso", "PERSON"),
    ("Miriam Germán", "Miriam Germán Brito", "PERSON"),
]
# fmt: on
