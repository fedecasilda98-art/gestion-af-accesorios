import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re
from fpdf import FPDF
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión AF Accesorios", layout="wide", initial_sidebar_state="collapsed")

# Directorios y Archivos
if not os.path.exists("data"):
    os.makedirs("data")

ARCHIVO_ARTICULOS = "data/lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "data/clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "data/movimientos_clientes.csv"
CARPETA_FOTOS = "data/fotos_productos"
WHATSAPP_NUM = "5493413512049"

if not os.path.exists(CARPETA_FOTOS): 
    os.makedirs(CARPETA_FOTOS)

# --- CARGA DE DATOS ---
def cargar_datos(archivo, columns):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            df.columns = df.columns.str.strip()
            for col in columns:
                if col not in df.columns: 
                    df[col] = 0.0 if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo"]) else ""
            return df[columns]
        except: 
            return pd.DataFrame(columns=columns)
    return pd.DataFrame(columns=columns)

COLS_ARTICULOS = ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"]
COLS_CLIENTES = ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"]
COLS_MOVS = ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"]

df_stock = cargar_datos(ARCHIVO_ARTICULOS, COLS_ARTICULOS)
df_clientes = cargar_datos(ARCHIVO_CLIENTES, COLS_CLIENTES)
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, COLS_MOVS)

# Inicializar estados de sesión
if "carrito" not in st.session_state: st.session_state.carrito = []
if "remito_items" not in st.session_state: st.session_state.remito_items = []
if "confirmar_orden" not in st.session_state: st.session_state.confirmar_orden = False
if "confirmar_nc" not in st.session_state: st.session_state.confirmar_nc = False

# --- UTILIDADES ---
def formatear_moneda(valor):
    try:
        v = round(float(valor), 2)
        return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "$ 0,00"

class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "AF ACCESORIOS - ALUMINIO", ln=True, align="C")
        self.set_font("Helvetica", "", 10)
        self.cell(0, 5, "Casilda, Santa Fe | WhatsApp: +54 9 341 351-2049", ln=True, align="C")
        self.ln(10)

def generar_pdf_binario(cliente_nombre, carrito, total, df_clientes, titulo="PRESUPUESTO", fecha_fija=None):
    try:
        pdf = PDF() 
        pdf.add_page()
        info_cli = df_clientes[df_clientes["Nombre"] == cliente_nombre]
        tel = str(info_cli["Tel"].values[0]) if not info_cli.empty else "-"
        loc = str(info_cli["Localidad"].values[0]) if not info_cli.empty else "-"
        dir = str(info_cli["Direccion"].values[0]) if not info_cli.empty else "-"
        
        fecha_display = fecha_fija if fecha_fija else datetime.now().strftime('%d/%m/%Y %H:%M')

        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f" TIPO DE DOCUMENTO: {titulo}", ln=True, fill=True, border=1)
        pdf.ln(2)
        
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(95, 7, f" CLIENTE: {cliente_nombre}", border="LT")
        pdf.cell(95, 7, f" FECHA: {fecha_display}", border="RT", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(95, 7, f" TEL: {tel}", border="L")
        pdf.cell(95, 7, f" LOCALIDAD: {loc}", border="R", ln=True)
        pdf.cell(190, 7, f" DIRECCIÓN: {dir}", border="LRB", ln=True)
        pdf.ln(5)
        
        pdf.set_font("Helvetica", "B", 10); pdf.set_fill_color(200, 200, 200)
        pdf.cell(100, 10, " Articulo / Accesorio", border=1, fill=True)
        pdf.cell(20, 10, "Cant.", border=1, fill=True, align="C")
        pdf.cell(35, 10, "P. Unit", border=1, fill=True, align="R")
        pdf.cell(35, 10, "Subtotal", border=1, fill=True, align="R", ln=True)
        
        pdf.set_font("Helvetica", "", 10)
        for item in carrito:
            pdf.cell(100, 8, f" {item['Producto']}", border=1)
            pdf.cell(20, 8, str(item['Cant']), border=1, align="C")
            pdf.cell(35, 8, f"{formatear_moneda(item['Precio U.'])} ", border=1, align="R")
            pdf.cell(35, 8, f"{formatear_moneda(item['Subtotal'])} ", border=1, align="R", ln=True)
        
        pdf.ln(2); pdf.set_font("Helvetica", "B", 12)
        pdf.cell(155, 10, "TOTAL:", border=0, align="R")
        pdf.cell(35, 10, f"{formatear_moneda(total)}", border=1, align="R")
        
        res = pdf.output(dest='S')
        if isinstance(res, str):
            return res.encode('latin-1', 'replace')
        return bytes(res)
    except Exception as e:
        st.error(f"Error PDF: {str(e)}")
        return b""

# --- INTERFAZ ---
tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre", "📦 Remitos"])

with tabs[0]: # STOCK
    st.header("Inventario Actual")
    st.dataframe(df_stock, use_container_width=True, hide_index=True)

with tabs[1]: # LOTE
        st.header("🚚 Carga por Lote")
        st.info("Escribí los artículos nuevos abajo. Las Listas 1 y 2 se calculan solas.")
        columnas_lote = ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Descripcion"]
        df_lote_nuevo = pd.DataFrame(columns=columnas_lote)
        lote_editado = st.data_editor(df_lote_nuevo, num_rows="dynamic", use_container_width=True, key="lote_v_final_sincro")
        if st.button("🚀 PROCESAR E INCORPORAR AL STOCK", type="primary"):
            if lote_editado is not None and not lote_editado.empty:
                validos = lote_editado[lote_editado["Accesorio"].astype(str).str.strip() != ""].copy()
                if not validos.empty:
                    def limpiar_n(v):
                        try: return float(str(v).replace('$', '').replace(',', '.').strip())
                        except: return 0.0
                    procesados = []
                    for _, r in validos.iterrows():
                        cb = limpiar_n(r["Costo Base"])
                        fl = limpiar_n(r["Flete"])
                        ga = limpiar_n(r["% Ganancia"])
                        l1 = round((cb + fl) * (1 + ga/100), 2)
                        l2 = round(l1 * 0.90, 2)
                        procesados.append({
                            "Rubro": str(r["Rubro"]), "Proveedor": str(r["Proveedor"]),
                            "Accesorio": str(r["Accesorio"]), "Stock": limpiar_n(r["Stock"]),
                            "Costo Base": cb, "Flete": fl, "% Ganancia": ga,
                            "Lista 1 (Cheques)": l1, "Lista 2 (Efectivo)": l2,
                            "Descripcion": str(r["Descripcion"])
                        })
                    df_nuevos = pd.DataFrame(procesados)
                    df_f = pd.concat([df_stock, df_nuevos], ignore_index=True)
                    df_f.to_csv(ARCHIVO_ARTICULOS, index=False)
                    st.success(f"✅ Se agregaron {len(procesados)} artículos."); st.rerun()

with tabs[2]: # MAESTRO (Ejemplo de edición)
    st.header("⚙️ Maestro de Artículos")
    df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True, key="editor_maestro_final")
    if st.button("Guardar Cambios Maestro"):
        df_ed.to_csv(ARCHIVO_ARTICULOS, index=False)
        st.success("Base actualizada"); st.rerun()

with tabs[3]: # CTA CTE
    st.header("Gestión de Cuentas Corrientes")
    if not df_clientes.empty:
        cli_sel = st.selectbox("Seleccionar Cliente:", df_clientes["Nombre"].tolist(), key="sel_cli_ctacte")
        idx_c = df_clientes[df_clientes["Nombre"] == cli_sel].index[0]
        st.metric("Saldo Pendiente", formatear_moneda(df_clientes.at[idx_c, "Saldo"]))
        
        monto_p = st.number_input("Monto a pagar $:", min_value=0.0, key="monto_pago_cli")
        if st.button("Registrar Pago"):
            df_clientes.at[idx_c, "Saldo"] -= monto_p
            df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
            n_mov = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": cli_sel, "Tipo": "PAGO", "Monto": monto_p, "Metodo": "Efectivo", "Detalle": "Pago parcial"}])
            pd.concat([df_movs, n_mov]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
            st.success("Pago guardado"); st.rerun()

with tabs[4]: # PRESUPUESTADOR
    st.header("📄 Presupuestador")
    cli_p = st.selectbox("Cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["C. Final"], key="cli_presu")
    p1, p2, p3 = st.columns([2, 1, 1])
    with p1: i_p = st.selectbox("Artículo:", df_stock["Accesorio"].tolist(), key="item_presu")
    with p2: q_p = st.number_input("Cant:", min_value=1, key="cant_presu")
    with p3: l_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"], key="lista_presu")
    
    if st.button("➕ AGREGAR"):
        p_u = df_stock[df_stock["Accesorio"] == i_p][l_p].values[0]
        st.session_state.carrito.append({"Producto": i_p, "Cant": q_p, "Precio U.": p_u, "Subtotal": p_u * q_p})
        st.rerun()

    if st.session_state.carrito:
        st.table(st.session_state.carrito)
        t_f = sum(item["Subtotal"] for item in st.session_state.carrito)
        st.write(f"### TOTAL: {formatear_moneda(t_f)}")
        
        colb1, colb2, colb3 = st.columns(3)
        with colb1:
            pdf_out = generar_pdf_binario(cli_p, st.session_state.carrito, t_f, df_clientes)
            st.download_button("📥 DESCARGAR PDF", pdf_out, f"Presu_{cli_p}.pdf", "application/pdf")
        with colb2:
            if st.button("✅ GENERAR ORDEN"):
                for item in st.session_state.carrito:
                    df_stock.loc[df_stock["Accesorio"] == item["Producto"], "Stock"] -= item["Cant"]
                if cli_p != "C. Final":
                    df_clientes.loc[df_clientes["Nombre"] == cli_p, "Saldo"] += t_f
                df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                n_v = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": cli_p, "Tipo": "VENTA", "Monto": t_f, "Metodo": l_p, "Detalle": "Venta asistida"}])
                pd.concat([df_movs, n_v]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                st.session_state.carrito = []; st.success("Orden cargada"); st.rerun()
        with colb3:
            if st.button("🗑️ LIMPIAR"):
                st.session_state.carrito = []; st.rerun()

with tabs[5]: # HISTORIAL
    st.header("📋 Historial Global")
    st.dataframe(df_movs.sort_index(ascending=False), use_container_width=True)

with tabs[6]: # CIERRE
        st.header("🏁 Cierre de Caja")
        c1, c2 = st.columns(2)
        v_s = round((df_stock['Stock'] * df_stock['Costo Base']).sum(), 2)
        c1.metric("Valor Stock", formatear_moneda(v_s))
        c2.metric("Deuda Clientes", formatear_moneda(df_clientes['Saldo'].sum()))

with tabs[7]: # REMITOS
    st.header("📦 Remitos")
    cr = st.selectbox("Cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["C. Final"], key="cli_remito_final")
    if st.button("Agregar item (Prueba)"):
        st.session_state.remito_items.append({"Producto": "Item Remito", "Cant": 1, "Precio U.": 0, "Subtotal": 0})
    if st.session_state.remito_items:
        pdf_rem = generar_pdf_binario(cr, st.session_state.remito_items, 0, df_clientes, "REMITO")
        st.download_button("Descargar Remito", pdf_rem, "remito.pdf")

st.divider()
with st.expander("🚀 CARGAR BASES DE DATOS AL VOLUMEN"):
    archivo_subido = st.file_uploader("Elegir archivo CSV", type="csv")
    destino = st.selectbox("¿Qué archivo estás subiendo?", [ARCHIVO_ARTICULOS, ARCHIVO_CLIENTES, ARCHIVO_MOVIMIENTOS])
    if st.button("Guardar en Railway"):
        if archivo_subido:
            with open(destino, "wb") as f: f.write(archivo_subido.getbuffer())
