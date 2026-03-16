import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF
import re

# --- CONFIGURACIÓN DE RUTAS ---
st.set_page_config(page_title="AF Accesorios - Gestión", layout="wide")
ARCHIVO_ARTICULOS = "lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "movimientos_clientes.csv"
ARCHIVO_ORDENES_LOG = "log_ordenes.csv"
CARPETA_PRESUPUESTOS = "presupuestos_pdf"
CARPETA_ORDENES = "ordenes_trabajo"
CARPETA_FOTOS = "fotos_productos" 
LOGO_PATH = "logo.jpg" 

for carpeta in [CARPETA_PRESUPUESTOS, CARPETA_ORDENES, CARPETA_FOTOS]:
    if not os.path.exists(carpeta): os.makedirs(carpeta)

# --- ESTADO DE SESIÓN ---
if "carrito" not in st.session_state: 
    st.session_state.carrito = pd.DataFrame(columns=["Artículo", "Cantidad", "Precio Unitario", "Subtotal"])
if "form_id" not in st.session_state: 
    st.session_state.form_id = 0

# --- FUNCIONES DE DATOS ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            df.columns = df.columns.str.strip()
            if "Descripcion" not in df.columns and archivo == ARCHIVO_ARTICULOS:
                df["Descripcion"] = ""
            for col in ["Stock", "Saldo", "Monto", "Cantidad", "Subtotal", "Precio Unitario"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

def registrar_movimiento(cliente, tipo, monto, detalle, nro_orden=None):
    df_mov = cargar_datos(ARCHIVO_MOVIMIENTOS, ["Fecha", "Cliente", "Tipo", "Monto", "Detalle", "Nro_Orden"])
    nuevo = pd.DataFrame([[datetime.now().strftime("%d/%m/%Y %H:%M"), cliente, tipo, monto, detalle, nro_orden]], columns=df_mov.columns)
    guardar_datos(pd.concat([df_mov, nuevo], ignore_index=True), ARCHIVO_MOVIMIENTOS)

# --- GENERADORES DE PDF ---
def generar_pdf_documento(cliente_nom, df_carrito, total, tipo="PRESUPUESTO", nro_orden=None):
    pdf = FPDF()
    pdf.add_page()
    if os.path.exists(LOGO_PATH):
        try: pdf.image(LOGO_PATH, 10, 8, 33); pdf.ln(20)
        except: pdf.set_font("Arial", "B", 16); pdf.cell(100, 10, txt="AF ACCESORIOS"); pdf.ln(10)
    else:
        pdf.set_font("Arial", "B", 16); pdf.cell(100, 10, txt="AF ACCESORIOS"); pdf.ln(10)
    
    pdf.set_font("Arial", "B", 12)
    titulo = f"{tipo} # {nro_orden}" if nro_orden else tipo
    pdf.cell(0, 10, txt=titulo, ln=True, align="R")
    pdf.set_font("Arial", "B", 10); pdf.cell(0, 8, txt=f"Cliente: {cliente_nom}", ln=True)
    pdf.set_font("Arial", "", 9); pdf.cell(100, 8, txt=f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    pdf.ln(5)
    
    pdf.set_fill_color(240, 240, 240); pdf.set_font("Arial", "B", 9)
    pdf.cell(90, 10, "Articulo", 1, 0, 'L', True); pdf.cell(20, 10, "Cant.", 1, 0, 'C', True)
    pdf.cell(35, 10, "P. Unit", 1, 0, 'C', True); pdf.cell(45, 10, "Subtotal", 1, 1, 'C', True)
    
    pdf.set_font("Arial", "", 9)
    for _, row in df_carrito.iterrows():
        pdf.cell(90, 10, str(row["Artículo"])[:45], 1)
        pdf.cell(20, 10, str(int(row["Cantidad"])), 1, 0, 'C')
        pdf.cell(35, 10, f"$ {row['Precio Unitario']:,.2f}", 1, 0, 'R')
        pdf.cell(45, 10, f"$ {row['Subtotal']:,.2f}", 1, 1, 'R')
    
    pdf.ln(5); pdf.set_font("Arial", "B", 12)
    pdf.cell(145, 10, "TOTAL:", align="R"); pdf.cell(45, 10, f"$ {total:,.2f}", 1, 1, 'R')
    
    folder = CARPETA_PRESUPUESTOS if tipo=="PRESUPUESTO" else CARPETA_ORDENES
    nom_arch = f"{tipo}_{nro_orden if nro_orden else 'P'}_{cliente_nom}.pdf"
    ruta = os.path.join(folder, nom_arch)
    pdf.output(ruta)
    return ruta

def generar_pdf_catalogo(df):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    if os.path.exists(LOGO_PATH): pdf.image(LOGO_PATH, 10, 8, 30)
    pdf.set_font("Arial", "B", 16); pdf.cell(0, 10, "CATALOGO - AF ACCESORIOS", ln=True, align="C"); pdf.ln(20)

    items = df.to_dict("records")
    for i, item in enumerate(items):
        col = i % 2
        if col == 0 and i > 0: pdf.ln(5)
        x = 10 + (col * 100); y = pdf.get_y()
        if y > 230: pdf.add_page(); y = 40
        pdf.rect(x, y, 95, 55)
        nombre_foto = re.sub(r'[^a-zA-Z0-9\s]', '', str(item['Accesorio']))
        encontrada = False
        for ext in [".jpg", ".JPG", ".png", ".PNG", ".jpeg"]:
            fp = os.path.join(CARPETA_FOTOS, f"{nombre_foto}{ext}")
            if os.path.exists(fp):
                pdf.image(fp, x + 2, y + 2, 35, 35); encontrada = True; break
        if not encontrada:
            pdf.set_font("Arial", "I", 7); pdf.set_xy(x+2, y+20); pdf.cell(35, 10, "Sin Foto", 0, 0, 'C')
        pdf.set_font("Arial", "B", 10); pdf.set_xy(x+40, y+5); pdf.multi_cell(50, 5, str(item['Accesorio']))
        pdf.set_font("Arial", "", 8); pdf.set_xy(x+40, y+15); pdf.multi_cell(50, 4, str(item.get('Descripcion', ''))[:80])
        pdf.set_font("Arial", "B", 11); pdf.set_text_color(200, 0, 0); pdf.set_xy(x+40, y+45); pdf.cell(50, 5, f"$ {item['Lista 1 (Cheques)']:,.2f}")
        pdf.set_text_color(0, 0, 0)
        if col == 1: pdf.set_y(y + 60)
    
    ruta = "Catalogo_AF_Accesorios.pdf"
    pdf.output(ruta)
    return ruta

# --- CARGA ---
df_stock = cargar_datos(ARCHIVO_ARTICULOS, ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"])
df_clientes = cargar_datos(ARCHIVO_CLIENTES, ["Nombre", "Teléfono", "Localidad", "Saldo"])

# --- APP ---
tabs = st.tabs(["📊 Stock", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestos", "📖 Catálogo"])

with tabs[0]: st.dataframe(df_stock, use_container_width=True, hide_index=True)

with tabs[1]: # MAESTRO
    st.header("⚙️ Maestro de Artículos")
    with st.expander("➕ Nuevo"):
        with st.form("alta"):
            c1, c2, c3 = st.columns(3)
            rb = c1.text_input("Rubro"); pr = c2.text_input("Proveedor"); nm = c3.text_input("Accesorio")
            stk = c1.number_input("Stock", 0); cst = c2.number_input("Costo", 0.0); gan = c3.number_input("% Gan", 35.0)
            if st.form_submit_button("Guardar"):
                l1 = cst * (1 + (gan/100)); l2 = l1 * 0.9
                nuevo = pd.DataFrame([[rb.upper(), pr, nm.upper(), stk, cst, 0, gan, l1, l2, ""]], columns=df_stock.columns)
                guardar_datos(pd.concat([df_stock, nuevo], ignore_index=True), ARCHIVO_ARTICULOS); st.rerun()
    st.data_editor(df_stock, use_container_width=True, key="editor_m")

with tabs[2]: # CTA CTE
    st.header("👥 Clientes")
    sel_c = st.selectbox("Cliente:", ["Mostrador"] + sorted(df_clientes["Nombre"].tolist()))
    if sel_c != "Mostrador":
        idx = df_clientes[df_clientes["Nombre"]==sel_c].index[0]
        st.metric("Saldo", f"$ {df_clientes.at[idx, 'Saldo']:,.2f}")

with tabs[3]: # PRESUPUESTADOR
    st.header("📄 Presupuestos")
    cp = st.selectbox("Para:", ["Mostrador"] + sorted(df_clientes["Nombre"].tolist()))
    lp = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
    with st.form(key=f"f_{st.session_state.form_id}", clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        it = col1.selectbox("Art:", sorted(df_stock["Accesorio"].tolist()))
        ca = col2.number_input("Cant", 1)
        if st.form_submit_button("Añadir"):
            r = df_stock[df_stock["Accesorio"] == it].iloc[0]
            pu = r[lp]
            st.session_state.carrito = pd.concat([st.session_state.carrito, pd.DataFrame([[it, ca, pu, ca*pu]], columns=st.session_state.carrito.columns)], ignore_index=True)
            st.session_state.form_id += 1; st.rerun()
    
    if not st.session_state.carrito.empty:
        st.dataframe(st.session_state.carrito)
        tot = st.session_state.carrito["Subtotal"].sum()
        if st.button("Generar PDF"):
            path = generar_pdf_documento(cp, st.session_state.carrito, tot)
            with open(path, "rb") as f: st.download_button("Descargar", f, file_name=path)

with tabs[4]: # CATALOGO
    st.header("📖 Catálogo y Fotos")
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Subir Foto")
        art_foto = st.selectbox("¿A qué artículo pertenece?", sorted(df_stock["Accesorio"].tolist()))
        archivo_subido = st.file_uploader("Elegí la foto (JPG)", type=['jpg', 'jpeg', 'png'])
        if st.button("Guardar Foto"):
            if archivo_subido:
                nombre_limpio = re.sub(r'[^a-zA-Z0-9\s]', '', art_foto)
                ruta_foto = os.path.join(CARPETA_FOTOS, f"{nombre_limpio}.jpg")
                with open(ruta_foto, "wb") as f: f.write(archivo_subido.getbuffer())
                st.success(f"Foto de {art_foto} guardada!")
    
    with col_b:
        st.subheader("Generar Catálogo")
        if st.button("🚀 Crear Catálogo PDF"):
            path_cat = generar_pdf_catalogo(df_stock)
            with open(path_cat, "rb") as f: st.download_button("Descargar Catálogo", f, file_name="Catalogo_AF.pdf")