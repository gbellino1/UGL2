import streamlit as st
import datetime
import pandas as pd
import os
from playwright.sync_api import sync_playwright

# Configuración de la página
st.set_page_config(page_title="Buscador Licitaciones UGL", layout="wide")
st.title("🔎 Monitoreo de Licitaciones PAMI")
st.subheader("Neuromodulación y Alta Complejidad")

# --- Parámetros de búsqueda ---
palabras_clave = [
    'kit', 'neuro', 'neurocirugía', 'estimulador', 'batería',
    'electrodos', 'neuroestimulador', 'bomba', 'intratecal',
    'Prodigy','eterna','burst','incontinencia','espiculado','liberta',
    'DRG', 'proclaim','abbott','infinity','IOS','direccional','penta',
    'incontinencia','morfina','baclofeno','refill','espasticidad',
    'DBS','parkinson','oncologico','medular','recambio','sacro',
    'epidural','ganglio','corriente','cerebral','electrodo','profundo'
]

destinos = ["UGL IX Rosario", "UGL XIV Entre Ríos", "UGL XV Santa Fé", "UGL XXXIV Concordia"]

config_ugls = {
    "UGL II Corrientes": {"cod": "2", "ext": "docx"},
    "UGL IX Rosario": {"cod": "9", "ext": "pdf"},
    "UGL XIII Chaco": {"cod": "13", "ext": "docx"}, 
    "UGL XIV Entre Ríos": {"cod": "14", "ext": "doc"},
    "UGL XV Santa Fé": {"cod": "15", "ext": "doc"},
    "UGL XVIII Misiones": {"cod": "18", "ext": "pdf"},
    "UGL XXIII Formosa": {"cod": "23", "ext": "pdf"},
    "UGL XXXIV Concordia": {"cod": "34", "ext": "docx"} 
}

# Función crucial para la nube: Instala Chromium de forma nativa en el contenedor
@st.cache_resource
def preparar_entorno_playwright():
    st.write("Configurando dependencias del navegador en el servidor (esto ocurre solo una vez)...")
    os.system("playwright install chromium")

# --- Interfaz de Streamlit ---
if st.button('🚀 Iniciar Búsqueda en PAMI'):
    # Nos aseguramos de que el navegador esté instalado en el backend
    preparar_entorno_playwright()
    
    todos_los_resultados = []
    progreso = st.progress(0)
    
    hoy = datetime.datetime.now()
    hoy_dia = hoy.day
    mañana_dia = (hoy + datetime.timedelta(days=7)).day 

    # Contexto síncrono de Playwright
    with sync_playwright() as p:
        # Lanzamos el navegador con argumentos ligeros optimizados para servidores
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        page = browser.new_page()
        
        for i, destino in enumerate(destinos):
            st.write(f"Buscando en: **{destino}**...")
            progreso.progress((i + 1) / len(destinos))
            
            try:
                # Navegación base
                page.goto("https://prestadores.pami.org.ar/result.php?c=7-5&par=2", timeout=30000)
                
                # Selección de UGL mediante su etiqueta visible (reemplaza a Select de Selenium)
                page.select_option("#destino_compra", label=destino)
                
                # Selección de rango de fechas en el Datepicker
                for campo_id in ['fecha_post', 'fecha_ant']:
                    page.click(f"#{campo_id}")
                    page.wait_for_selector(".ui-datepicker-calendar", state="visible")
                    
                    dia = hoy_dia if campo_id == 'fecha_post' else mañana_dia
                    try:
                        # Hacemos click en el enlace del día correspondiente dentro del calendario
                        page.locator(f"//a[text()='{dia}']").first.click()
                    except:
                        st.warning(f"No se pudo seleccionar el día {dia} en {destino}.")
                
                # Ejecutar la consulta en el sitio
                page.click("#srchBtn")
                
                # Esperar a que la tabla de resultados se renderice en el DOM
                page.wait_for_selector('#resultados table', timeout=10000)
                
                # Capturamos todas las filas directamente
                filas = page.locator('#resultados table tr').all()
                
                for fila in filas:
                    columnas = fila.locator('td').all()
                    if len(columnas) >= 5:
                        detalle_texto = columnas[4].inner_text().lower().strip()
                        
                        # Filtrado inteligente por tus palabras clave
                        if any(palabra in detalle_texto for palabra in palabras_clave):
                            nro_completo = columnas[0].inner_text().strip()
                            nro_solo = nro_completo.split('/')[0]
                            
                            conf = config_ugls.get(destino, {"cod": "9", "ext": "pdf"})
                            cod_ugl = conf["cod"]
                            ext = conf["ext"]
                            
                            base_url = "https://institucional.pami.org.ar/compras/archivos"
                            link_v1 = f"{base_url}/CAB_{nro_solo}_2026_{cod_ugl}_1.{ext}"
                            link_v2 = f"{base_url}/CAB_{nro_solo}_2026_{cod_ugl}_2.{ext}"
                            
                            todos_los_resultados.append({
                                "Número": nro_completo,
                                "UGL": columnas[2].inner_text().strip(),
                                "Detalle": columnas[4].inner_text().strip(),
                                "Fecha": columnas[5].inner_text().strip(),
                                "Link Principal": link_v1,
                                "Link Alternativo": link_v2
                            })
                            
            except Exception as e:
                # Si una UGL no tiene registros o da timeout, continúa buscando en las demás
                continue
                
        # Cerramos de forma limpia la instancia del navegador
        browser.close()

    # --- Renderizado de Reportes ---
    progreso.progress(1.0)
    if todos_los_resultados:
        st.success(f"¡Se encontraron {len(todos_los_resultados)} coincidencias críticas!")
        df = pd.DataFrame(todos_los_resultados)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No se detectaron licitaciones abiertas para neuromodulación bajo estos parámetros.")
