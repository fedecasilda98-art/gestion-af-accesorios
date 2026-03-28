import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re
from fpdf import FPDF
from io import BytesIO

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="AF Accesorios - Gestión", layout="wide", initial_sidebar_state="collapsed")

ARCHIVO_ARTICULOS = "lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "movimientos_clientes.csv"
CARPETA_FOTOS = "fotos_productos"
WHATSAPP_NUM = "5493413512049"

if not os.path.exists(CARPETA_FOTOS): os.makedirs(CARPETA_FOTOS)

# --- CARGA DE DATOS ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            df.columns = df.columns.str.strip()
            for col in columnas:
                if col not in df.columns: 
                    df[col] = 0.0 if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Stock"]) else ""
            return df[columnas]
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

COLS_ARTICULOS = ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"]
COLS_CLIENTES = ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"]
COLS_MOVS = ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"]

df_stock = cargar_datos(ARCHIVO_ARTICULOS, COLS_ARTICULOS)
df_clientes = cargar_datos(ARCHIVO_CLIENTES, COLS_CLIENTES)
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, COLS_MOVS)

# Estados de sesión para evitar reinicios bruscos
if "carrito" not in st.session_state: st.session_state.carrito = []
if "pdf_a_descargar" not in st.session_state: st.session_state.pdf_a_descargar = None

def formatear_moneda(valor):
    try: return f"$ {round(float(valor), 2):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "$ 0,00"

# --- CLASE PDF ---
class PDF(FPDF):
    def header(self):
        try: self.image('logo.jpg', 10, 8, 33)
        except: pass
        self.set_font("Helvetica", "B", 15); self.cell(40)
        self.cell(0, 10, "AF ACCESORIOS - ALUMINIO", ln=True)
        self.set_font("Helvetica", "", 10); self.cell(40)
        self.cell(0, 5, "Casilda, Santa Fe | WhatsApp: +54 9 341 351-2049", ln=True); self.ln(10)

def generar_pdf_final(cliente, carrito, total, titulo="COMPROBANTE"):
    try:
        pdf = PDF(); pdf.add_page()
        pdf.set_fill_color(240, 240, 240); pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, f" {titulo}", ln=True, fill=True, border=1); pdf.ln(3)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, f"CLIENTE: {cliente} | FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, border="B")
        pdf.ln(5)
        # Encabezados tabla
        pdf.set_font("Helvetica", "B", 10); pdf.set_fill_color(220, 220, 220)
        pdf.cell(110, 8, " Articulo", 1, 0, "L", True)
        pdf.cell(20, 8, "Cant", 1, 0, "C", True)
        pdf.cell(30, 8, "P.Unit", 1, 0, "R", True)
        pdf.cell(30, 8, "Subtotal", 1, 1, "R", True)
        # Items
        pdf.set_font("Helvetica", "", 10)
        for i in carrito:
            pdf.cell(110, 7, f" {i['Producto'][:50]}", 1)
            pdf.cell(20, 7, str(i['Cant']), 1, 0, "C")
            pdf.cell(30, 7, formatear_moneda(i['Precio U.']), 1, 0, "R")
            pdf.cell(30, 7, formatear_moneda(i['Subtotal']), 1, 1, "R")
        # Total
        pdf.ln(4); pdf.set_font("Helvetica", "B", 11)
        pdf.cell(160, 10, "TOTAL FINAL:", 0, 0, "R")
        pdf.cell(30, 10, formatear_moneda(total), 1, 1, "R")
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except Exception as e:
        st.error(f"Error PDF: {e}"); return None

# --- NAVEGACIÓN ---
tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Clientes", "📄 Presupuestador", "📋 Historial", "🏁 Cierre"])

with tabs[0]: # STOCK
    st.header("Inventario Actual")
    st.dataframe(df_stock, use_container_width=True, hide_index=True)

with tabs[1]: # LOTE
    st.header("Carga Masiva de Stock")
    df_lote = st.data_editor(pd.DataFrame(columns=["Accesorio", "Costo Base", "Cantidad"]), num_rows="dynamic", key="editor_lote")
    if st.button("Actualizar Stock"):
        for _, fila in df_lote.iterrows():
            if fila["Accesorio"] in df_stock["Accesorio"].values:
                idx = df_stock[df_stock["Accesorio"] == fila["Accesorio"]].index[0]
                df_stock.at[idx, "Stock"] += fila["Cantidad"]
                df_stock.at[idx, "Costo Base"] = fila["Costo Base"]
        df_stock.to_csv(ARCHIVO_ARTICULOS, index=False); st.success("Carga exitosa"); st.rerun()

with tabs[2]: # MAESTRO
    st.header("Maestro de Precios")
    df_m = st.data_editor(df_stock, use_container_width=True, hide_index=True, key="editor_maestro")
    if st.button("Guardar Cambios Maestro"):
        df_m.to_csv(ARCHIVO_ARTICULOS, index=False); st.success("Datos guardados"); st.rerun()

with tabs[3]: # CLIENTES
    st.header("Cuentas Corrientes")
    if not df_clientes.empty:
        c_sel = st.selectbox("Seleccionar Cliente:", df_clientes["Nombre"].tolist(), key="sel_cli_cte")
        idx_cli = df_clientes[df_clientes["Nombre"] == c_sel].index[0]
        st.metric("Saldo Actual", formatear_moneda(df_clientes.at[idx_cli, "Saldo"]))
        
        with st.expander("Acciones"):
            n_nombre = st.text_input("Nombre Nuevo Cliente")
            if st.button("Añadir Cliente"):
                nuevo = pd.DataFrame([[n_nombre, "", "", "", 0.0]], columns=COLS_CLIENTES)
                pd.concat([df_clientes, nuevo]).to_csv(ARCHIVO_CLIENTES, index=False); st.rerun()
            if st.button("Eliminar Seleccionado", type="primary"):
                df_clientes[df_clientes["Nombre"] != c_sel].to_csv(ARCHIVO_CLIENTES, index=False); st.rerun()

with tabs[4]: # PRESUPUESTADOR
    st.header("Presupuestador")
    col_c, col_a, col_q, col_l = st.columns([2, 2, 1, 1])
    with col_c: cli_p = st.selectbox("Cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["C. Final"], key="p_cli")
    with col_a: art_p = st.selectbox("Producto:", df_stock["Accesorio"].tolist(), key="p_art")
    with col_q: cant_p = st.number_input("Cant:", 1, key="p_q")
    with col_l: list_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"], key="p_l")
    
    if st.button("➕ AGREGAR"):
        precio = df_stock[df_stock["Accesorio"] == art_p][list_p].values[0]
        st.session_state.carrito.append({"Producto": art_p, "Cant": cant_p, "Precio U.": precio, "Subtotal": precio * cant_p})
        st.rerun()

    if st.session_state.carrito:
        st.subheader("Carrito")
        for i, it in enumerate(st.session_state.carrito):
            st.write(f"• {it['Cant']}x {it['Producto']} - {formatear_moneda(it['Subtotal'])}")
        
        total_v = sum(x["Subtotal"] for x in st.session_state.carrito)
        st.markdown(f"### TOTAL: {formatear_moneda(total_v)}")
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if st.button("🗑️ LIMPIAR"): st.session_state.carrito = []; st.session_state.pdf_a_descargar = None; st.rerun()
        with c2:
            if st.button("📥 PRE."):
                st.session_state.pdf_a_descargar = generar_pdf_final(cli_p, st.session_state.carrito, total_v, "PRESUPUESTO")
        with c3:
            if st.button("✅ ORDEN"):
                # Descontar stock y actualizar saldo
                for x in st.session_state.carrito:
                    df_stock.loc[df_stock["Accesorio"]==x["Producto"], "Stock"] -= x["Cant"]
                df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                if cli_p != "C. Final":
                    idx = df_clientes[df_clientes["Nombre"]==cli_p].index[0]
                    df_clientes.at[idx, "Saldo"] += total_v
                    df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                st.session_state.pdf_a_descargar = generar_pdf_final(cli_p, st.session_state.carrito, total_v, "ORDEN DE VENTA")
                st.session_state.carrito = [] # Limpiar tras confirmar
        
        if st.session_state.pdf_a_descargar:
            st.download_button("⬇️ DESCARGAR DOCUMENTO", st.session_state.pdf_a_descargar, f"Doc_{datetime.now().strftime('%H%M')}.pdf", "application/pdf")

with tabs[5]: # HISTORIAL
    st.header("Historial de Ventas")
    st.dataframe(df_movs, use_container_width=True)

with tabs[6]: # CIERRE
    st.header("Cierre de Caja")
    st.metric("Inversión en Stock (Costo)", formatear_moneda((df_stock["Stock"] * df_stock["Costo Base"]).sum()))
    st.metric("Total por Cobrar (Clientes)", formatear_moneda(df_clientes["Saldo"].sum()))
