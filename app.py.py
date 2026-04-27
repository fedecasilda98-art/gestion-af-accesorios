import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re
from fpdf import FPDF
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión AF Accesorios", layout="wide", initial_sidebar_state="collapsed")

# --- BLOQUE DE DIAGNÓSTICO ---
st.sidebar.write("### 🔍 Estado de Archivos")
if os.path.exists("data"):
    st.sidebar.success("Carpeta 'data' encontrada")
    archivos_en_data = os.listdir("data")
    st.sidebar.write(f"Archivos: {archivos_en_data}")
else:
    st.sidebar.error("Carpeta 'data' NO EXISTE")

ARCHIVO_ARTICULOS = "data/lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "data/clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "data/movimientos_clientes.csv"
ARCHIVO_REGISTRO_LOTES = "data/registro_lotes.csv"
CARPETA_FOTOS = "data/fotos_productos"
WHATSAPP_NUM = "5493413512049"

# Detectar Modo Cliente
es_cliente = st.query_params.get("modo") == "cliente"

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
            for col in df.columns:
                if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Flete", "Stock"]):
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
            return df[columns]
        except: 
            return pd.DataFrame(columns=columns)
    return pd.DataFrame(columns=columns)

COLS_ARTICULOS = ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"]
COLS_CLIENTES = ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"]
COLS_MOVS = ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"]
COLS_REGISTRO_LOTES = ["Fecha", "Articulos", "Costo Total Compra"]

df_stock = cargar_datos(ARCHIVO_ARTICULOS, COLS_ARTICULOS)
df_clientes = cargar_datos(ARCHIVO_CLIENTES, COLS_CLIENTES)
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, COLS_MOVS)
df_lotes_historial = cargar_datos(ARCHIVO_REGISTRO_LOTES, COLS_REGISTRO_LOTES)

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
        pdf.cell(100, 10, " Artículo / Accesorio", border=1, fill=True)
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
        if isinstance(res, (bytearray, bytes)):
            return bytes(res)
        else:
            return res.encode('latin-1', 'replace')
    except Exception as e:
        st.error(f"Error PDF: {str(e)}")
        return b""

# --- INTERFAZ ---
if es_cliente:
    st.title("🛒 Catálogo AF Accesorios")
    busqueda = st.text_input("Buscar producto...", "").upper()
    df_ver = df_stock[df_stock["Accesorio"].str.contains(busqueda, na=False)]
    cols = st.columns(3)
    for idx, row in df_ver.iterrows():
        with cols[idx % 3]:
            with st.container(border=True):
                nombre_foto = re.sub(r'[^a-zA-Z0-9\s]', '', str(row['Accesorio']))
                fp = os.path.join(CARPETA_FOTOS, f"{nombre_foto}.jpg")
                if os.path.exists(fp): st.image(fp, use_container_width=True)
                st.subheader(row["Accesorio"])
                l_tipo = st.radio("Condición:", ["Cheques", "Efectivo/Transf."], key=f"cr_{idx}")
                p = row["Lista 1 (Cheques)"] if l_tipo == "Cheques" else row["Lista 2 (Efectivo)"]
                st.write(f"**{formatear_moneda(p)}**")
                c = st.number_input("Cantidad", 0, key=f"cn_{idx}")
                if st.button("Pedir", key=f"cb_{idx}"):
                    msg = f"Hola! Pedido de {c}x {row['Accesorio']} ({l_tipo})."
                    st.markdown(f"[Confirmar en WhatsApp](https://wa.me/{WHATSAPP_NUM}?text={msg})")
else:
    tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre de Caja", "📦 Remitos"])

    with tabs[0]: # STOCK
        st.header("Inventario Actual")
        if not df_stock.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Costo Stock", formatear_moneda((df_stock['Costo Base'] * df_stock['Stock']).sum()))
            c2.metric("Total Lista 1", formatear_moneda((df_stock['Lista 1 (Cheques)'] * df_stock['Stock']).sum()))
            c3.metric("Total Lista 2", formatear_moneda((df_stock['Lista 2 (Efectivo)'] * df_stock['Stock']).sum()))
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

    with tabs[1]: # LOTE
        st.header("🚚 Ingreso de Mercadería")
        tab_carga, tab_hist_ingresos = st.tabs(["📥 Cargar Lote", "📜 Historial de Ingresos"])

        with tab_carga:
            if "lote_temporal" not in st.session_state: 
                st.session_state.lote_temporal = []
            
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1, 1])
                opciones_stock = ["-- NUEVO ARTÍCULO --"] + df_stock["Accesorio"].tolist()
                prod_sel = c1.selectbox("Artículo:", opciones_stock, key="sel_prod_lote")
                cant_ingreso = c2.number_input("Cantidad:", min_value=0, value=0, key="cant_lote")
                costo_ingreso = c3.number_input("Costo Unitario $:", min_value=0.0, step=0.1, key="costo_lote")

                if prod_sel == "-- NUEVO ARTÍCULO --":
                    cn1, cn2, cn3 = st.columns(3)
                    nombre_nuevo = cn1.text_input("Nombre:", key="n_n_l")
                    rubro_nuevo = cn2.text_input("Rubro:", key="r_n_l")
                    prov_nuevo = cn3.text_input("Proveedor:", key="p_n_l")
                
                if st.button("➕ AGREGAR AL LISTADO", use_container_width=True):
                    nombre_final = nombre_nuevo if prod_sel == "-- NUEVO ARTÍCULO --" else prod_sel
                    if nombre_final and cant_ingreso > 0:
                        item_ex = df_stock[df_stock["Accesorio"] == nombre_final]
                        nuevo_i = {
                            "Rubro": rubro_nuevo if prod_sel == "-- NUEVO ARTÍCULO --" else item_ex["Rubro"].values[0],
                            "Proveedor": prov_nuevo if prod_sel == "-- NUEVO ARTÍCULO --" else item_ex["Proveedor"].values[0],
                            "Accesorio": nombre_final, "Stock": cant_ingreso, "Costo Base": costo_ingreso,
                            "Flete": item_ex["Flete"].values[0] if not item_ex.empty else 0.0,
                            "% Ganancia": item_ex["% Ganancia"].values[0] if not item_ex.empty else 40.0,
                            "Descripcion": item_ex["Descripcion"].values[0] if not item_ex.empty else ""
                        }
                        st.session_state.lote_temporal.append(nuevo_i)
                        st.rerun()

            if st.session_state.lote_temporal:
                df_temp = pd.DataFrame(st.session_state.lote_temporal)
                lote_final_edit = st.data_editor(df_temp, use_container_width=True, key="ed_lote_vis")
                
                col_acc1, col_acc2 = st.columns(2)
                if col_acc1.button("🗑️ LIMPIAR LISTA", use_container_width=True):
                    st.session_state.lote_temporal = []
                    st.rerun()
                    
                if col_acc2.button("🚀 CONFIRMAR E INGRESAR", type="primary", use_container_width=True):
                    detalle_hist = []
                    inv_total = 0
                    for _, r in lote_final_edit.iterrows():
                        n, stk, cb, fl, ga = r["Accesorio"], r["Stock"], r["Costo Base"], r["Flete"], r["% Ganancia"]
                        l1 = round((cb + fl) * (1 + ga/100), 2)
                        l2 = round(l1 * 0.90, 2)
                        inv_total += (stk * cb)
                        detalle_hist.append(f"{stk}x {n} (${cb})")
                        mask = df_stock["Accesorio"] == n
                        if mask.any():
                            df_stock.loc[mask, "Stock"] += stk
                            df_stock.loc[mask, ["Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)"]] = [cb, fl, ga, l1, l2]
                        else:
                            nf = pd.DataFrame([{"Rubro": r["Rubro"], "Proveedor": r["Proveedor"], "Accesorio": n, "Stock": stk, "Costo Base": cb, "Flete": fl, "% Ganancia": ga, "Lista 1 (Cheques)": l1, "Lista 2 (Efectivo)": l2, "Descripcion": r["Descripcion"]}])
                            df_stock = pd.concat([df_stock, nf], ignore_index=True)
                    df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                    n_h = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Articulos": " | ".join(detalle_hist), "Costo Total Compra": round(inv_total, 2)}])
                    pd.concat([df_lotes_historial, n_h], ignore_index=True).to_csv(ARCHIVO_REGISTRO_LOTES, index=False)
                    st.session_state.lote_temporal = []
                    st.success("✅ Stock e Historial actualizados.")
                    st.rerun()

        with tab_hist_ingresos:
            df_v_h = cargar_datos(ARCHIVO_REGISTRO_LOTES, COLS_REGISTRO_LOTES)
            if not df_v_h.empty:
                for idx, row in df_v_h.sort_index(ascending=False).iterrows():
                    with st.expander(f"📦 {row['Fecha']} | Inversión: {formatear_moneda(row['Costo Total Compra'])}"):
                        for it in str(row["Articulos"]).split(" | "): 
                            st.write(f"🔹 {it}")

    with tabs[2]: # MAESTRO
        st.header("⚙️ Maestro de Artículos")
        df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True, key="ed_maestro_full")
        if st.button("Guardar Cambios Maestro"):
            df_ed["Lista 1 (Cheques)"] = ((df_ed["Costo Base"] + df_ed["Flete"]) * (1 + df_ed["% Ganancia"] / 100)).round(2)
            df_ed["Lista 2 (Efectivo)"] = (df_ed["Lista 1 (Cheques)"] * 0.90).round(2)
            df_ed.to_csv(ARCHIVO_ARTICULOS, index=False)
            st.success("✅ Base actualizada")
            st.rerun()
        
        with st.expander("🗑️ ZONA DE PELIGRO - ELIMINAR"):
            art_borrar = st.selectbox("Seleccionar para borrar:", [""] + df_stock["Accesorio"].tolist(), key="del_item_sel")
            if art_borrar != "":
                st.error(f"¿Estás seguro de borrar {art_borrar}?")
                if st.button("SÍ, ELIMINAR DEFINITIVAMENTE"):
                    df_stock = df_stock[df_stock["Accesorio"] != art_borrar]
                    df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                    st.rerun()

    with tabs[7]: # REMITOS (Corrigiendo el SyntaxError de tu imagen)
        st.header("📦 Generar Remito de Entrega")
        # Aquí pegá tu lógica de remitos asegurándote de que la línea de st.number_input esté completa
        # Ejemplo de la línea corregida:
        # q_r = st.number_input("Cant:", min_value=1, value=1, key="cant_remito_f")
