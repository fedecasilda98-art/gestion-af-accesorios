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
            cols_num = ["Stock", "Saldo", "Monto", "Cantidad", "Subtotal", "Precio Unitario", "Costo Base", "Lista 1 (Cheques)", "Lista 2 (Efectivo)"]
            for col in cols_num:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

# --- GENERADORES DE PDF ---
def generar_pdf_documento(cliente_nom, df_carrito, total, tipo="PRESUPUESTO", nro_orden=None):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, txt="AF ACCESORIOS", ln=True, align="L")
    pdf.set_font("helvetica", "B", 12)
    titulo = f"{tipo} # {nro_orden}" if nro_orden else tipo
    pdf.cell(0, 10, txt=titulo, ln=True, align="R")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 8, txt=f"Cliente: {cliente_nom}", ln=True)
    pdf.cell(0, 8, txt=f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    pdf.ln(5)
    
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(90, 10, "Articulo", 1, 0, 'L', True)
    pdf.cell(20, 10, "Cant.", 1, 0, 'C', True)
    pdf.cell(35, 10, "P. Unit", 1, 0, 'C', True)
    pdf.cell(45, 10, "Subtotal", 1, 1, 'C', True)
    
    pdf.set_font("helvetica", "", 9)
    for _, row in df_carrito.iterrows():
        pdf.cell(90, 10, str(row["Artículo"])[:45], 1)
        pdf.cell(20, 10, str(int(row["Cantidad"])), 1, 0, 'C')
        pdf.cell(35, 10, f"$ {row['Precio Unitario']:,.2f}", 1, 0, 'R')
        pdf.cell(45, 10, f"$ {row['Subtotal']:,.2f}", 1, 1, 'R')
    
    pdf.ln(5)
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(145, 10, "TOTAL:", align="R")
    pdf.cell(45, 10, f"$ {total:,.2f}", 1, 1, 'R')
    
    ruta = f"{tipo}_{cliente_nom}.pdf"
    pdf.output(ruta)
    return ruta

def generar_pdf_catalogo(df):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, "CATALOGO - AF ACCESORIOS", ln=True, align="C")
    pdf.ln(10)

    items = df.to_dict("records")
    for i, item in enumerate(items):
        col = i % 2
        if col == 0 and i > 0: pdf.ln(5)
        x = 10 + (col * 100); y = pdf.get_y()
        if y > 230: pdf.add_page(); y = 20
        pdf.rect(x, y, 95, 55)
        
        nombre_foto = re.sub(r'[^a-zA-Z0-9\s]', '', str(item['Accesorio']))
        encontrada = False
        for ext in [".jpg", ".JPG", ".png", ".PNG", ".jpeg"]:
            fp = os.path.join(CARPETA_FOTOS, f"{nombre_foto}{ext}")
            if os.path.exists(fp):
                pdf.image(fp, x + 2, y + 2, 35, 35); encontrada = True; break
        
        if not encontrada:
            pdf.set_font("helvetica", "I", 7); pdf.set_xy(x+2, y+20); pdf.cell(35, 10, "Sin Foto", 0, 0, 'C')
        
        pdf.set_font("helvetica", "B", 10); pdf.set_xy(x+40, y+5); pdf.multi_cell(50, 5, str(item['Accesorio']))
        pdf.set_font("helvetica", "", 8); pdf.set_xy(x+40, y+15); pdf.multi_cell(50, 4, str(item.get('Descripcion', ''))[:80])
        pdf.set_font("helvetica", "B", 11); pdf.set_text_color(200, 0, 0); pdf.set_xy(x+40, y+45); pdf.cell(50, 5, f"$ {item['Lista 1 (Cheques)']:,.2f}")
        pdf.set_text_color(0, 0, 0)
        if col == 1: pdf.set_y(y + 60)
    
    ruta = "Catalogo_AF.pdf"
    pdf.output(ruta)
    return ruta

# --- CARGA ---
df_stock = cargar_datos(ARCHIVO_ARTICULOS, ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"])
df_clientes = cargar_datos(ARCHIVO_CLIENTES, ["Nombre", "Teléfono", "Localidad", "Saldo"])

# --- INTERFAZ STREAMLIT ---
tabs = st.tabs(["📊 Stock", "⚙️ Maestro", "👥 Clientes", "📄 Presupuestos", "📖 Catálogo"])

with tabs[0]: 
    st.subheader("Inventario Actual")
    st.dataframe(df_stock, use_container_width=True, hide_index=True)

with tabs[1]: # MAESTRO
    st.header("⚙️ Administración de Artículos")
    with st.expander("➕ Cargar Nuevo"):
        with st.form("alta"):
            c1, c2, c3 = st.columns(3)
            rb = c1.text_input("Rubro"); pr = c2.text_input("Proveedor"); nm = c3.text_input("Accesorio")
            stk = c1.number_input("Stock Inicial", 0); cst = c2.number_input("Costo Base", 0.0); gan = c3.number_input("% Ganancia", 35.0)
            if st.form_submit_button("Guardar Artículo"):
                l1 = cst * (1 + (gan/100)); l2 = l1 * 0.9
                nuevo = pd.DataFrame([[rb.upper(), pr, nm.upper(), stk, cst, 0, gan, l1, l2, ""]], columns=df_stock.columns)
                df_stock = pd.concat([df_stock, nuevo], ignore_index=True)
                guardar_datos(df_stock, ARCHIVO_ARTICULOS); st.rerun()
    st.info("Editá directamente en la tabla y dale a Guardar")
    df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True)
    if st.button("Guardar Cambios en Maestro"):
        guardar_datos(df_ed, ARCHIVO_ARTICULOS); st.success("¡Datos actualizados!"); st.rerun()

with tabs[2]: # CLIENTES
    st.header("👥 Base de Clientes")
    with st.expander("✨ Agregar Cliente"):
        with st.form("n_cli"):
            nc = st.text_input("Nombre"); tc = st.text_input("Tel"); lc = st.text_input("Localidad")
            if st.form_submit_button("Crear"):
                df_clientes = pd.concat([df_clientes, pd.DataFrame([[nc, tc, lc, 0.0]], columns=df_clientes.columns)], ignore_index=True)
                guardar_datos(df_clientes, ARCHIVO_CLIENTES); st.rerun()
    st.dataframe(df_clientes, use_container_width=True)

with tabs[3]: # PRESUPUESTOS
    st.header("📄 Generador de Presupuestos")
    c_p = st.selectbox("Cliente:", ["Mostrador"] + sorted(df_clientes["Nombre"].tolist()))
    l_p = st.selectbox("Lista de Precios:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
    
    with st.form(key=f"f_{st.session_state.form_id}", clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        it = col1.selectbox("Producto:", sorted(df_stock["Accesorio"].tolist()))
        ca = col2.number_input("Cantidad", 1, min_value=1)
        if st.form_submit_button("Añadir al Carrito"):
            r = df_stock[df_stock["Accesorio"] == it].iloc[0]
            pu = r[l_p]
            st.session_state.carrito = pd.concat([st.session_state.carrito, pd.DataFrame([[it, ca, pu, ca*pu]], columns=st.session_state.carrito.columns)], ignore_index=True)
            st.session_state.form_id += 1; st.rerun()
    
    if not st.session_state.carrito.empty:
        st.table(st.session_state.carrito)
        total = st.session_state.carrito["Subtotal"].sum()
        st.subheader(f"Total: $ {total:,.2f}")
        if st.button("Generar PDF Presupuesto"):
            pdf_path = generar_pdf_documento(c_p, st.session_state.carrito, total)
            with open(pdf_path, "rb") as f: st.download_button("📥 Descargar PDF", f, file_name=f"Presupuesto_{c_p}.pdf")
        if st.button("Limpiar Carrito"):
            st.session_state.carrito = pd.DataFrame(columns=st.session_state.carrito.columns); st.rerun()

with tabs[4]: # CATALOGO
    st.header("📖 Catálogo de AF Accesorios")
    c_izq, c_der = st.columns(2)
    
    with c_izq:
        st.subheader("📸 Subir Foto desde Celu/PC")
        art_sel = st.selectbox("Elegí el artículo:", sorted(df_stock["Accesorio"].tolist()))
        foto_subida = st.file_uploader("Saca una foto o elegí una", type=['jpg', 'jpeg', 'png'])
        if st.button("Guardar esta foto"):
            if foto_subida:
                nom_limpio = re.sub(r'[^a-zA-Z0-9\s]', '', art_sel)
                path_f = os.path.join(CARPETA_FOTOS, f"{nom_limpio}.jpg")
                with open(path_f, "wb") as f: f.write(foto_subida.getbuffer())
                st.success(f"Foto de {art_sel} guardada con éxito.")
            else: st.error("Primero subí un archivo.")
            
    with c_der:
        st.subheader("📄 Generar el PDF")
        if st.button("🚀 Crear Catálogo Completo"):
            cat_path = generar_pdf_catalogo(df_stock)
            with open(cat_path, "rb") as f: st.download_button("📥 Descargar Catálogo", f, file_name="Catalogo_AF_Accesorios.pdf")
