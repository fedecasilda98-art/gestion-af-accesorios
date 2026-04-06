import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re
from fpdf import FPDF
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión AF Accesorios", layout="wide", initial_sidebar_state="collapsed")

# Archivos Base
ARCHIVO_ARTICULOS = "lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "movimientos_clientes.csv"
CARPETA_FOTOS = "fotos_productos"
WHATSAPP_NUM = "5493413512049"

# Detectar Modo Cliente
es_cliente = st.query_params.get("modo") == "cliente"

if not os.path.exists(CARPETA_FOTOS): 
    os.makedirs(CARPETA_FOTOS)

# --- CARGA DE DATOS ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            df.columns = df.columns.str.strip()
            for col in columnas:
                if col not in df.columns: 
                    df[col] = 0.0 if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo"]) else ""
            for col in df.columns:
                if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Flete", "Stock"]):
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
            return df[columnas]
        except: 
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

COLS_ARTICULOS = ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"]
COLS_CLIENTES = ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"]
COLS_MOVS = ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"]

df_stock = cargar_datos(ARCHIVO_ARTICULOS, COLS_ARTICULOS)
df_clientes = cargar_datos(ARCHIVO_CLIENTES, COLS_CLIENTES)
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, COLS_MOVS)

# Inicializar estados de sesión
if "carrito" not in st.session_state: st.session_state.carrito = []
if "remito_items" not in st.session_state: st.session_state.remito_items = []
if "orden_lista" not in st.session_state: st.session_state.orden_lista = None
if "confirmar_orden" not in st.session_state: st.session_state.confirmar_orden = False
if "confirmar_nc" not in st.session_state: st.session_state.confirmar_nc = False

# --- UTILIDADES DE FORMATO ---
def formatear_moneda(valor):
    try:
        v = round(float(valor), 2)
        return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "$ 0,00"

# --- CLASE PDF ---
class PDF(FPDF):
    def header(self):
        try: self.image('logo.jpg', 10, 8, 33)
        except: pass
        self.set_font("Helvetica", "B", 16)
        self.cell(40)
        self.cell(0, 10, "AF ACCESORIOS - ALUMINIO", ln=True)
        self.set_font("Helvetica", "", 10)
        self.cell(40)
        self.cell(0, 5, "Casilda, Santa Fe | WhatsApp: +54 9 341 351-2049", ln=True)
        self.ln(10)

def generar_pdf_binario(cliente_nombre, carrito, total, df_clientes, titulo="PRESUPUESTO", fecha_fija=None):
    try:
        pdf = PDF() 
        pdf.add_page()
        info_cli = df_clientes[df_clientes["Nombre"] == cliente_nombre]
        tel = str(info_cli["Tel"].values[0]) if not info_cli.empty else "-"
        loc = str(info_cli["Localidad"].values[0]) if not info_cli.empty else "-"
        dir = str(info_cli["Direccion"].values[0]) if not info_cli.empty else "-"
        
        fecha_doc = fecha_fija if fecha_fija else datetime.now().strftime('%d/%m/%Y %H:%M')

        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f" TIPO DE DOCUMENTO: {titulo}", ln=True, fill=True, border=1)
        pdf.ln(2)
        
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(95, 7, f" CLIENTE: {cliente_nombre}", border="LT")
        pdf.cell(95, 7, f" FECHA: {fecha_doc}", border="RT", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(95, 7, f" TEL: {tel}", border="L")
        pdf.cell(95, 7, f" LOCALIDAD: {loc}", border="R", ln=True)
        pdf.cell(190, 7, f" DIRECCIÓN: {dir}", border="LRB", ln=True)
        pdf.ln(5)
        
        pdf.set_font("Helvetica", "B", 10); pdf.set_fill_color(200, 200, 200)
        pdf.cell(130, 10, " Artículo / Accesorio", border=1, fill=True)
        pdf.cell(30, 10, "Cant.", border=1, fill=True, align="C")
        pdf.cell(30, 10, "Estado", border=1, fill=True, align="C", ln=True)
        
        pdf.set_font("Helvetica", "", 10)
        for item in carrito:
            pdf.cell(130, 8, f" {item['Producto']}", border=1)
            pdf.cell(30, 8, str(item['Cant']), border=1, align="C")
            pdf.cell(30, 8, "Entregado", border=1, align="C", ln=True)
        
        pdf.ln(15)
        pdf.cell(95, 8, "________________________", ln=False, align="C")
        pdf.cell(95, 8, "________________________", ln=True, align="C")
        pdf.cell(95, 8, "Firma Recibe", ln=False, align="C")
        pdf.cell(95, 8, "Control AF", ln=True, align="C")
        
        res = pdf.output(dest='S')
        return bytes(res) if isinstance(res, (bytearray, bytes)) else res.encode('latin-1', 'replace')
    except Exception as e:
        st.error(f"Error PDF: {str(e)}")
        return b""

# --- INTERFAZ ---
if es_cliente:
    st.title("🛒 Catálogo AF Accesorios")
    # ... (Sección de catálogo sin cambios)
else:
    tabs = st.tabs(["📊 Stock", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestador", "📦 Remitos", "📋 Órdenes", "🏁 Caja"])

    # --- TABLAS SIN CAMBIOS (RESUMIDAS PARA EL EJEMPLO) ---
    with tabs[0]: st.dataframe(df_stock, use_container_width=True, hide_index=True)
    with tabs[1]: 
        df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True)
        if st.button("Guardar Maestro"): df_ed.to_csv(ARCHIVO_ARTICULOS, index=False); st.rerun()
    
    with tabs[2]: # CTA CTE CON GESTIÓN DE CLIENTES
        st.header("👥 Gestión de Clientes y Saldos")
        # ... (Cta Cte sin cambios, se mantiene tu funcionalidad de alta/edición/pago)

    with tabs[3]: # PRESUPUESTADOR
        st.header("📄 Generador de Presupuestos")
        # ... (Presupuestador original sin cambios)

    with tabs[4]: # PESTAÑA NUEVA: REMITOS
        st.header("📦 Generar Remito de Entrega")
        st.info("Este remito se generará con fecha 01/04/2026.")
        
        cli_rem = st.selectbox("Cliente para el Remito:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"], key="cli_rem")
        
        r1, r2, r3 = st.columns([2, 1, 1])
        with r1: art_rem = st.selectbox("Buscar Artículo:", df_stock["Accesorio"].tolist(), key="art_rem")
        with r2: cant_rem = st.number_input("Cantidad:", min_value=1, value=1, key="cant_rem")
        with r3: 
            if st.button("➕ AGREGAR", use_container_width=True):
                st.session_state.remito_items.append({"Producto": art_rem, "Cant": cant_rem})
                st.rerun()

        if st.session_state.remito_items:
            st.subheader("Artículos en el Remito")
            for idx, r_item in enumerate(st.session_state.remito_items):
                c_art, c_del = st.columns([4, 1])
                c_art.write(f"**{r_item['Cant']}x** - {r_item['Producto']}")
                if c_del.button("❌", key=f"del_rem_{idx}"):
                    st.session_state.remito_items.pop(idx); st.rerun()
            
            st.divider()
            col_b1, col_b2 = st.columns(2)
            
            pdf_remito = generar_pdf_binario(cli_rem, st.session_state.remito_items, 0, df_clientes, "REMITO DE ENTREGA", "01/04/2026")
            
            if pdf_remito:
                col_b1.download_button("📥 DESCARGAR REMITO PDF", pdf_remito, f"Remito_{cli_rem}.pdf", "application/pdf", use_container_width=True)
            
            if col_b2.button("🗑️ LIMPIAR TODO", use_container_width=True):
                st.session_state.remito_items = []; st.rerun()

    with tabs[5]: st.dataframe(df_movs.sort_index(ascending=False), use_container_width=True, hide_index=True)
    with tabs[6]: # CIERRE
        st.metric("Valor Stock", formatear_moneda((df_stock['Stock'] * df_stock['Costo Base']).sum()))
