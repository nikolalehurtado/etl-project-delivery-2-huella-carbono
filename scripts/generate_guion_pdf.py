"""
Genera el PDF con el Guion Completo de Sustentación para la Persona 2
(David Aponte — API y Calidad de Datos).

Uso:
    python scripts/generate_guion_pdf.py
"""

from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PDF = ROOT / "docs" / "guion_sustentacion_persona_2.pdf"


class NumberedCanvas(canvas.Canvas):
    """Agrega números de página y encabezados/pies en dos pasadas."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#555555"))

        # Encabezado (a partir de la página 2)
        if self._pageNumber > 1:
            self.drawString(
                54, 750, "Guion de Sustentación — Persona 2: API y Calidad de Datos | ETL UAO"
            )
            self.setStrokeColor(colors.HexColor("#D0D7DE"))
            self.setLineWidth(0.5)
            self.line(54, 744, 558, 744)

        # Pie de página (todas las páginas)
        text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(558, 36, text)
        self.drawString(54, 36, "Confidencial — Proyecto ETL Huella de Carbono (Segunda Entrega)")
        self.setStrokeColor(colors.HexColor("#D0D7DE"))
        self.setLineWidth(0.5)
        self.line(54, 46, 558, 46)

        self.restoreState()


def build_pdf():
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Estilos tipográficos
    primary_color = colors.HexColor("#0D47A1")  # Azul marino institucional
    dark_text = colors.HexColor("#1A1A1A")
    muted_text = colors.HexColor("#555555")

    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=primary_color,
        spaceAfter=6,
    )

    subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        textColor=muted_text,
        spaceAfter=14,
    )

    h1_style = ParagraphStyle(
        "Header1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=primary_color,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        "Header2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#1565C0"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=dark_text,
        spaceAfter=5,
    )

    script_say_style = ParagraphStyle(
        "ScriptSay",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8.8,
        leading=12.5,
        textColor=colors.HexColor("#0D3820"),
    )

    box_label_style = ParagraphStyle(
        "BoxLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0D47A1"),
        spaceAfter=3,
    )

    code_style = ParagraphStyle(
        "CodeInline",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#880E4F"),
    )

    story = []

    # ─────────────────────────────────────────────────────────────
    # PORTADA / ENCABEZADO
    # ─────────────────────────────────────────────────────────────
    story.append(Paragraph("GUION DE SUSTENTACIÓN — SEGUNDA ENTREGA ETL", title_style))
    story.append(
        Paragraph(
            "<b>Rol:</b> David Aponte (Persona 2 — API y Calidad de Datos)<br/>"
            "<b>Proyecto:</b> Huella de Carbono en Hogares Colombianos (ODS 12) · ECV 2025 + API IDEAM<br/>"
            "<b>Universidad Autónoma de Occidente</b> · Ingeniería de Datos e IA · Airflow 3.1.8 & GX 1.23.1",
            subtitle_style,
        )
    )
    story.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceAfter=10))

    # Caja de resumen inicial
    setup_box_data = [
        [
            Paragraph(
                "<b>PREPARACIÓN PREVIA ANTES DE PROYECTAR PANTALLA:</b><br/>"
                "• <b>Editor (VS Code):</b> Tener abiertas las pestañas: <code>README.md</code>, <code>docs/quality_rules.md</code>, <code>src/extract.py</code>, <code>src/validation.py</code>.<br/>"
                "• <b>Jupyter Notebooks:</b> Tener abiertos <code>notebooks/01_perfilamiento_ecv_primaria.ipynb</code> y <code>02_perfilamiento_api_ideam.ipynb</code> con las celdas ya corridas.<br/>"
                "• <b>Terminal:</b> Lista en la raíz del proyecto para ejecutar el comando de pruebas unitarias.<br/>"
                "• <b>Aclaración de API:</b> Se utilizó la <b>API Oficial del IDEAM (datos.gov.co)</b> y <u>NO</u> OpenWeatherMap (explicado en Sección 5).",
                body_style,
            )
        ]
    ]
    setup_table = Table(setup_box_data, colWidths=[504])
    setup_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0F4F8")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#B0BEC5")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(setup_table)
    story.append(Spacer(1, 8))

    # Helper para crear bloques de "Qué mostrar" y "Qué decir"
    def add_section_script(sec_num, sec_title, show_what, say_what, extra_tip=None):
        block = []
        block.append(Paragraph(f"Sección {sec_num} del README — {sec_title}", h1_style))

        # Qué mostrar (caja azul claro)
        show_content = [
            [
                Paragraph("<b>QUÉ MOSTRAR EN PANTALLA:</b>", box_label_style),
            ],
            [
                Paragraph(show_what, body_style),
            ],
        ]
        t_show = Table(show_content, colWidths=[504])
        t_show.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#E3F2FD")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#90CAF9")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        block.append(t_show)
        block.append(Spacer(1, 5))

        # Qué decir (caja verde muy claro)
        say_content = [
            [
                Paragraph(
                    "<b>QUÉ DECIR PASO A PASO (DISCURSO EXACTO):</b>",
                    ParagraphStyle(
                        "GreenLabel",
                        parent=box_label_style,
                        textColor=colors.HexColor("#1B5E20"),
                    ),
                ),
            ],
            [
                Paragraph(say_what, script_say_style),
            ],
        ]
        t_say = Table(say_content, colWidths=[504])
        t_say.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#E8F5E9")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#A5D6A7")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        block.append(t_say)

        if extra_tip:
            block.append(Spacer(1, 4))
            t_tip = Table(
                [[Paragraph(f"<b>Tip de defensa:</b> {extra_tip}", code_style)]], colWidths=[504]
            )
            t_tip.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF8E1")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#FFE082")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ])
            )
            block.append(t_tip)

        block.append(Spacer(1, 10))
        return KeepTogether(block)

    # ─────────────────────────────────────────────────────────────
    # 1. SECCIÓN 5: FUENTE PRIMARIA Y API
    # ─────────────────────────────────────────────────────────────
    story.append(
        add_section_script(
            sec_num="5",
            sec_title="Fuente Primaria y Fuente API (IDEAM vs OpenWeatherMap)",
            show_what="1. Abrir en VS Code <code>README.md</code> en la <b>Sección 5</b> (tabla de la API).<br/>"
            "2. Pasar a <code>src/extract.py</code> y resaltar la función <code>_query_params()</code> (línea 141) y <code>_fetch_page()</code> (línea 160).<br/>"
            "3. Opcional: mostrar un archivo generado en <code>data/work/&lt;run_id&gt;/raw/api_manifest.json</code>.",
            say_what='"En la sección 5 del README documenté la integración de la fuente primaria y la API climática. '
            'Para enriquecer la ECV 2025 y permitir responder los requisitos R6 y R7, integramos la temperatura oficial de Colombia.<br/><br/>'
            '<b>¿Por qué usamos la API del IDEAM en datos.gov.co y no OpenWeatherMap?</b><br/>'
            'Por tres motivos analíticos fundamentales: primero, OpenWeatherMap en versión gratuita no ofrece históricos del año 2025 por departamentos, '
            'sino pronósticos comerciales. Segundo, el IDEAM es la entidad oficial meteorológica de Colombia, garantizando respaldo técnico en estaciones terrestres. '
            'Y tercero, la API SODA nos permite hacer <b>agregación en el servidor</b> mediante `$select`, `$group` y `$where`, trayendo la suma, el conteo de lecturas, '
            'mínimo y máximo por estación. Esto evita colapsar la memoria descargando millones de registros horarios crudos.<br/><br/>'
            'En <code>src/extract.py</code> clasifiqué las excepciones en dos familias: <b>APITransientError</b> (errores 5xx, 429 y timeouts) '
            'que Airflow y nuestro cliente reintentan con retroceso exponencial; y <b>APIContractError</b> (errores 4xx o respuestas no conformes), '
            'que son deterministas y detienen la tarea de inmediato para no consumir reintentos en vano."',
            extra_tip="Si el evaluador pregunta por la llave privada, aclara que la API de datos.gov.co es abierta y permite X-App-Token opcional desde variables de entorno, sin exponer credenciales en Git.",
        )
    )

    # ─────────────────────────────────────────────────────────────
    # 2. SECCIÓN 8: HALLAZGOS DE PERFILAMIENTO
    # ─────────────────────────────────────────────────────────────
    story.append(
        add_section_script(
            sec_num="8",
            sec_title="Hallazgos de Perfilamiento Sistemático (Los 2 Notebooks)",
            show_what="1. Abrir en pantalla <code>notebooks/01_perfilamiento_ecv_primaria.ipynb</code>.<br/>"
            "2. Desplazarse a la celda de gasto de electricidad `P5018` (completitud 77%) y la de duplicados (212 filas eliminadas).<br/>"
            "3. Cambiar a <code>notebooks/02_perfilamiento_api_ideam.ipynb</code> y mostrar la celda de outliers de temperatura (rango [-15, 50] °C) y cobertura departamental.",
            say_what='"Para cumplir con la sección 8 del enunciado, no inventamos ningún umbral. Desarrollé dos notebooks reproducibles:<br/><br/>'
            '• En el <b>Notebook 01 (ECV Primaria)</b> identificamos que el grano de hogares tiene un 0.24% de duplicados históricos (212 de 88 mil filas), '
            'por lo cual fijamos la regla de unicidad en ≥ 99%. Validamos que el pago de energía `P5018` tiene una completitud observada del 77%; '
            'establecimos el umbral en ≥ 70%, porque si cae de ahí, la imputación dominaría los cálculos de huella eléctrica. '
            'También verificamos en el diccionario del DANE que el estrato está en `P8520S1A1` (Datos de la vivienda) y no en `P5010`, que son cuartos para dormir; sus códigos 0, 8 y 9 (11,6 % de los hogares) los reclasificamos a estrato 0.<br/><br/>'
            '• En el <b>Notebook 02 (API IDEAM)</b> confirmamos que la propia ficha técnica advierte de lecturas erróneas por fallas de sensores. '
            'Encontramos lecturas anómalas de -99°C. Por eso definimos que al menos el 99.5% de las lecturas debe estar dentro del rango físico plausible de Colombia '
            '(-15°C a 50°C). Asimismo, comprobamos que más de 20 departamentos tienen estaciones activas en 2025, garantizando suficiente significancia estadística para R6 y R7."',
            extra_tip="Menciona que ambos notebooks se pueden regenerar en cualquier momento ejecutando `python scripts/build_notebooks.py`.",
        )
    )

    # ─────────────────────────────────────────────────────────────
    # 3. SECCIÓN 9: RIESGOS Y REGLAS DE CALIDAD
    # ─────────────────────────────────────────────────────────────
    story.append(
        add_section_script(
            sec_num="9",
            sec_title="Riesgos y Reglas de Calidad (DQ01–DQ30)",
            show_what="1. Abrir en VS Code el documento <code>docs/quality_rules.md</code>.<br/>"
            "2. Mostrar la tabla de la <b>Compuerta 1</b> (DQ01-DQ11), <b>Compuerta 2</b> (DQ12-DQ18) y <b>Compuerta 3</b> (DQ19-DQ30).<br/>"
            "3. Señalar la columna 'Base del umbral' para evidenciar que no son arbitrarios.",
            say_what='"En la sección 9 formulé <b>30 reglas de calidad formales (DQ01 a DQ30)</b> distribuidas en tres compuertas analíticas:<br/>'
            '1. <b>Compuerta 1 (Raw ECV):</b> 11 reglas sobre contratos de esquema, llaves no nulas, completitud de pagos y códigos DIVIPOLA.<br/>'
            '2. <b>Compuerta 2 (Raw API):</b> 7 reglas sobre respuesta no vacía, consistencia temporal del año 2025, coordenadas colombianas y temperatura física.<br/>'
            '3. <b>Compuerta 3 (Preparados):</b> 12 reglas sobre unicidad de surrogates, no negatividad de emisiones y consistencia matemática de la huella total.<br/><br/>'
            'Cada regla cuenta con una severidad documentada: <b>Critical</b> detiene el flujo downstream de inmediato; '
            '<b>Warning</b> registra la desviación en auditoría pero permite la continuidad si está dentro de la tolerancia operativa; '
            'e <b>Info</b> se reserva para monitoreo."',
            extra_tip="Resalta que ninguna regla fue creada solo porque los datos de hoy la cumplen, cumpliendo la exigencia del enunciado.",
        )
    )

    # ─────────────────────────────────────────────────────────────
    # 4. SECCIONES 10 Y 11: IMPLEMENTACIÓN GX Y COMPUERTAS RAW
    # ─────────────────────────────────────────────────────────────
    story.append(
        add_section_script(
            sec_num="10 y 11",
            sec_title="Diseño con Great Expectations y Validación Raw",
            show_what="1. Abrir <code>src/validation.py</code> en la función <code>run_suite()</code> (línea 340) y <code>enforce_policy()</code> (línea 405).<br/>"
            "2. Abrir en el explorador de archivos la carpeta <code>gx/expectations/</code> para mostrar los 11 archivos JSON exportados.<br/>"
            "3. Abrir <code>dags/etl_huella_carbono_dag.py</code> y señalar las tareas <code>validate_primary_raw</code> y <code>validate_api_raw</code>.",
            say_what='"Para materializar estas reglas en código utilizamos <b>Great Expectations Core 1.23.1</b> en modo ephemeral:<br/><br/>'
            '• Creamos 11 Expectation Suites. Cada expectativa inyecta en su metadata el identificador de regla (`meta.rule_id`) y su severidad (`Critical` o `Warning`).<br/>'
            '• En <code>run_suite()</code> ejecutamos la validación en memoria sobre DataFrames de Pandas sin requerir bases de datos pesadas.<br/>'
            '• Al finalizar cada suite, el resultado se exporta a <code>gx/expectations/*.json</code> sin IDs volátiles para permitir control de versiones limpio en Git, '
            'y los veredictos detallados se archivan en <code>gx/validation_results/&lt;run_id&gt;/</code>.<br/><br/>'
            'En el DAG de Airflow, las tareas `validate_primary_raw` y `validate_api_raw` operan en paralelo sobre las dos ramas de extracción. '
            'Si cualquiera de ellas detecta un fallo Critical, lanza un <code>ValueError</code> y la transformación nunca recibe datos corruptos."',
            extra_tip="Aclara que las tareas intercambian solo rutas y metadatos compactos por XCom, nunca DataFrames gigantes.",
        )
    )

    # ─────────────────────────────────────────────────────────────
    # 5. SECCIÓN 14: VALIDACIÓN DE DATOS PREPARADOS
    # ─────────────────────────────────────────────────────────────
    story.append(
        add_section_script(
            sec_num="14",
            sec_title="Validación de Datos Preparados (Compuerta 3)",
            show_what="1. Abrir <code>src/validation.py</code> y bajar a la función <code>run_prepared_gate()</code> (línea 468).<br/>"
            "2. Mostrar la suite <code>_prepared_fact_huella()</code> resaltando las expectativas DQ22 y DQ23.<br/>"
            "3. En <code>dags/etl_huella_carbono_dag.py</code>, mostrar la línea: <code>prepared_gate >> loaded</code>.",
            say_what='"La sección 14 corresponde a la <b>Compuerta 3 (`validate_prepared`)</b>, que evalúa el lote transformado antes de permitir su inserción en MySQL:<br/><br/>'
            'Validamos las 6 tablas del modelo estrella: la tabla de hechos `fact_huella_carbono` y las 5 dimensiones (`dim_hogar`, `dim_ubicacion`, `dim_clima`, `dim_tarifas` y `dim_combustibles`).<br/>'
            'Aquí aplicamos dos de las reglas más críticas del negocio:<br/>'
            '• <b>DQ22:</b> Ningún cálculo de consumo o emisión puede ser negativo.<br/>'
            '• <b>DQ23:</b> Consistencia aditiva: `huella_total_anual_kg` debe ser estrictamente mayor o igual que sus partes individuales '
            '(`emisiones_energia_kg` y `emisiones_coccion_kg`).<br/><br/>'
            'Si se supera la compuerta, la tarea `load_dimensional_dw` de la Persona 3 toma el control; si falla, el Data Warehouse queda totalmente protegido contra datos inconsistentes."',
            extra_tip="Menciona que esta compuerta fue coordinada entre Persona 2 (reglas GX) y Persona 3 (esquema y grano dimensional).",
        )
    )

    # ─────────────────────────────────────────────────────────────
    # 6. DEMOSTRACIÓN EN VIVO (EL AS BAJO LA MANGA)
    # ─────────────────────────────────────────────────────────────
    demo_what = "1. Abrir la terminal integrada de VS Code en la raíz del proyecto.<br/>2. Ejecutar: <code>python -m unittest discover -s tests</code>."
    demo_say = (
        '"Para demostrar que el sistema de validación y la API funcionan de forma determinista y reproducible, '
        'implementé una suite de pruebas unitarias automatizadas con `unittest`.<br/><br/>'
        'Al ejecutar <code>python -m unittest discover -s tests</code> vemos cómo se ejecutan <b>14 pruebas en menos de 1 segundo</b>: '
        'se valida que los errores 500 generen reintentos transitorios, que los errores 400 corten deterministamente, '
        'que un código DIVIPOLA falso (como 999) sea atrapado como Critical por la regla DQ08, y que las 11 suites de Great Expectations '
        'ejecuten de punta a punta exitosamente."'
    )
    story.append(
        add_section_script(
            sec_num="Extra",
            sec_title="Demostración en Vivo: Pruebas Unitarias Automatizadas",
            show_what=demo_what,
            say_what=demo_say,
            extra_tip="Ejecutar este comando en vivo genera un impacto muy positivo en el jurado porque demuestra solidez de ingeniería de software.",
        )
    )

    # ─────────────────────────────────────────────────────────────
    # 7. BANCO DE RESPUESTAS A PREGUNTAS DIFÍCILES DEL JURADO
    # ─────────────────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("Banco de Preguntas Trampa del Evaluador y Cómo Responder", h1_style))
    story.append(
        Paragraph(
            "Ten estas respuestas preparadas por si el docente o jurado hace preguntas de diseño profundo:",
            body_style,
        )
    )
    story.append(Spacer(1, 6))

    qa_data = [
        [
            Paragraph("<b>Pregunta del Evaluador</b>", box_label_style),
            Paragraph("<b>Respuesta Sugerida (Directa y Técnica)</b>", box_label_style),
        ],
        [
            Paragraph("<i>¿Por qué no usaron una API de clima como OpenWeatherMap?</i>", body_style),
            Paragraph(
                "OpenWeatherMap en su capa gratuita solo entrega pronósticos actuales a 5 días y no históricos consolidados de 2025 para Colombia. "
                "Además, el IDEAM es la autoridad meteorológica oficial del país y su API SODA en datos.gov.co permite agregar en el servidor sin costo.",
                body_style,
            ),
        ],
        [
            Paragraph("<i>¿Por qué GX no reintenta cuando una regla falla?</i>", body_style),
            Paragraph(
                "Porque los fallos de calidad sobre un lote estático son deterministas. Si un CSV viene sin la columna P1_DEPARTAMENTO, reintentarlo 3 veces arrojará "
                "el mismo error. Solo se reintenta la red o la base de datos.",
                body_style,
            ),
        ],
        [
            Paragraph("<i>¿Qué diferencia hay entre Critical y Warning en su compuerta?</i>", body_style),
            Paragraph(
                "Critical lanza una excepción (`ValueError`) que bloquea las tareas downstream de Airflow. Warning se registra en el log y en el reporte JSON "
                "de GX, pero permite continuar porque el negocio tolera anomalías menores (como códigos de estrato fuera del diccionario).",
                body_style,
            ),
        ],
        [
            Paragraph("<i>¿Cómo manejan la reanudación si la API falla a mitad de camino?</i>", body_style),
            Paragraph(
                "La extracción se divide en ventanas continuas (`_windows`). Cada ventana descargada se serializa en JSON local. Si la tarea se interrumpe, "
                "al reintentar reutiliza las ventanas cacheadas y solo pide las faltantes.",
                body_style,
            ),
        ],
        [
            Paragraph("<i>¿Por qué usan modo ephemeral en Great Expectations?</i>", body_style),
            Paragraph(
                "Para evitar la sobrecarga y complejidad operativa de mantener un servidor GX Store externo. Ephemeral ejecuta directamente sobre DataFrames de Pandas "
                "en los workers de Airflow y exporta los contratos a JSON versionados en Git.",
                body_style,
            ),
        ],
    ]

    t_qa = Table(qa_data, colWidths=[180, 324])
    t_qa.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0E0E0")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDBDBD")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    story.append(t_qa)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF generado exitosamente en: {OUTPUT_PDF}")


if __name__ == "__main__":
    build_pdf()
