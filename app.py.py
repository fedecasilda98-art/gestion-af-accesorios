import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re
from fpdf import FPDF
from io import BytesIO

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="AF Accesorios - Gestión Integral", layout="wide", initial_sidebar_state="collapsed")

ARCHIVO_ARTICULOS = "lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "movimientos_clientes.csv"
CARPETA_FOTOS = "fotos_productos"
WHATSAPP_NUM = "5493413512049"

es_cliente = st.query_params.get("modo") == "cliente"
if not os.path.exists(CARPETA_FOTOS): os.makedirs(CARPETA_FOTOS)

# --- MOTOR DE DATOS ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            df.columns = df.columns.str.strip()
            for col in columnas:
                if col not in df.columns: 
                    df[col] = 0.0 if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Stock", "Flete"]) else ""
            return df[columnas]
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

COLS_ARTICULOS = ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"]
COLS_CLIENTES = ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"]
COLS_MOVS = ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"]

df_stock = cargar_datos(ARCHIVO_ARTICULOS, COLS_ARTICULOS)
df_clientes = cargar_datos(ARCHIVO_CLIENTES, COLS_CLIENTES)
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, COLS_MOVS)

# Estados
if "carrito" not in st.session_state: st.session_state.carrito = []
if "orden_lista" not in st.session_state: st.session_state.orden_lista = None
if "confirmar_accion" not in st.session_state: st.session_state.confirmar_accion = None

def formatear_moneda(valor):
    try: return f"$ {round(float(valor), 2):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "$ 0,00"

# --- PDF ENGINE ---
class PDF(FPDF):
    def header(self):
        try: self.image('logo.jpg', 10, 8, 33)
        except: pass
        self.set_font("Helvetica", "B", 16); self.cell(40)
        self.cell(0, 10, "AF ACCESORIOS - ALUMINIO", ln=True)
        self.set_font("Helvetica", "", 10); self.cell(40)
        self.cell(0, 5, "Casilda, Santa Fe | WhatsApp: +54 9 341 351-2049", ln=True); self.ln(10)

def generar_pdf_binario(cliente, carrito, total, df_cli, titulo="PRESUPUESTO"):
    try:
        pdf = PDF(); pdf.add_page()
        info = df_cli[df_cli["Nombre"] == cliente]
        pdf.set_fill_color(240, 240, 240); pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f" {titulo}", ln=True, fill=True, border=1); pdf.ln(2)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, f"CLIENTE: {cliente} | FECHA: {datetime.now().strftime('%d/%m/%Y')}", ln=True, border="B")
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 10); pdf.set_fill_color(200, 200, 200)
        pdf.cell(110, 10, " Articulo", 1, 0, "L", True)
        pdf.cell(20, 10, "Cant", 1, 0, "C", True)
        pdf.cell(30, 10, "P.Unit", 1, 0, "R", True)
        pdf.cell(30, 10, "Subtotal", 1, 1, "R", True)
        pdf.set_font("Helvetica", "", 10)
        for i in carrito:
            pdf.cell(110, 8, f" {i['Producto']}", 1)
            pdf.cell(20, 8, str(i['Cant']), 1, 0, "C")
            pdf.cell(30, 8, formatear_moneda(i['Precio U.']), 1, 0, "R")
            pdf.cell(30, 8, formatear_moneda(i['Subtotal']), 1, 1, "R")
        pdf.ln(5); pdf.set_font("Helvetica", "B", 12)
        pdf.cell(160, 10, "TOTAL:", 0, 0, "R")
        pdf.cell(30, 10, formatear_moneda(total), 1, 1, "R")
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except: return b""

# --- INTERFAZ ---
if es_cliente:
    st.title("🛒 Catálogo AF Accesorios")
    busc = st.text_input("Buscar...").upper()
    df_v = df_stock[df_stock["Accesorio"].str.contains(busc, na=False)]
    cols = st.columns(3)
    for idx, row in df_v.iterrows():
        with cols[idx % 3]:
            with st.container(border=True):
                st.subheader(row["Accesorio"])
                l = st.radio("Lista:", ["Cheques", "Efectivo"], key=f"l_{idx}")
                p = row["Lista 1 (Cheques)"] if l == "Cheques" else row["Lista 2 (Efectivo)"]
                st.write(f"**{formatear_moneda(p)}**")
                if st.button("Pedir", key=f"b_{idx}"):
                    st.markdown(f"[WhatsApp](https://wa.me/{WHATSAPP_NUM}?text=Pedido:{row['Accesorio']})")
else:
    t = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre"])

    with t[0]: # STOCK
        st.header("Inventario")
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

    with t[1]: # LOTE
        st.header("Carga por Lote")
        df_l = st.data_editor(pd.DataFrame(columns=["Rubro", "Proveedor", "Accesorio", "Costo Base", "Cantidad Nueva"]), num_rows="dynamic")
        if st.button("Procesar Lote"):
            for _, r in df_l.iterrows():
                if r["Accesorio"] in df_stock["Accesorio"].values:
                    idx = df_stock[df_stock["Accesorio"] == r["Accesorio"]].index[0]
                    df_stock.at[idx, "Stock"] += r["Cantidad Nueva"]
                    df_stock.at[idx, "Costo Base"] = r["Costo Base"]
            df_stock.to_csv(ARCHIVO_ARTICULOS, index=False); st.success("Stock Actualizado"); st.rerun()

    with t[2]: # MAESTRO
        st.header("Maestro")
        df_m = st.data_editor(df_stock, use_container_width=True, hide_index=True)
        if st.button("Guardar Maestro"): df_m.to_csv(ARCHIVO_ARTICULOS, index=False); st.rerun()

    with t[3]: # CTA CTE
        st.header("Clientes")
        if not df_clientes.empty:
            c_s = st.selectbox("Cliente:", df_clientes["Nombre"].tolist())
            idx_c = df_clientes[df_clientes["Nombre"] == c_s].index[0]
            st.metric("Saldo", formatear_moneda(df_clientes.at[idx_c, "Saldo"]))
            with st.expander("Nuevo/Eliminar"):
                n = st.text_input("Nuevo Nombre")
                if st.button("Crear"):
                    nc = pd.DataFrame([[n, "", "", "", 0.0]], columns=COLS_CLIENTES)
                    pd.concat([df_clientes, nc]).to_csv(ARCHIVO_CLIENTES, index=False); st.rerun()
                if st.button("Borrar Actual", type="primary"):
                    df_clientes[df_clientes["Nombre"] != c_s].to_csv(ARCHIVO_CLIENTES, index=False); st.rerun()

    with t[4]: # PRESUPUESTADOR
        st.header("Presupuestos")
        cp = st.selectbox("Cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
        c1, c2, c3 = st.columns([2,1,1])
        with c1: ap = st.selectbox("Art:", df_stock["Accesorio"].tolist())
        with c2: qp = st.number_input("Cant:", 1)
        with c3: lp = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
        if st.button("➕ AGREGAR"):
            pu = round(df_stock[df_stock["Accesorio"]==ap][lp].values[0], 2)
            st.session_state.carrito.append({"Producto": ap, "Cant": qp, "Precio U.": pu, "Subtotal": pu*qp}); st.rerun()
        
        if st.session_state.carrito:
            for i, it in enumerate(st.session_state.carrito):
                st.write(f"{it['Cant']}x {it['Producto']} ({formatear_moneda(it['Subtotal'])})")
            tot = sum(x["Subtotal"] for x in st.session_state.carrito)
            st.write(f"### TOTAL: {formatear_moneda(tot)}")
            b_p, b_o, b_n, b_l = st.columns(4)
            with b_p:
                pdf = generar_pdf_binario(cp, st.session_state.carrito, tot, df_clientes, "PRESUPUESTO")
                if pdf: st.download_button("📥 BAJAR PRE.", pdf, f"Pre_{cp}.pdf", "application/pdf")
            with b_o: 
                if st.button("✅ ORDEN"): st.session_state.confirmar_accion = "ORDEN"
            with b_n:
                if st.button("🔵 N.C."): st.session_state.confirmar_accion = "NC"
            with b_l:
                if st.button("🗑️ LIMPIAR"): st.session_state.carrito = []; st.rerun()

            if st.session_state.confirmar_accion:
                acc = st.session_state.confirmar_accion
                st.warning(f"¿Confirmar {acc}?"); si, no = st.columns(2)
                if si.button("SÍ"):
                    sig = -1 if acc == "ORDEN" else 1
                    for x in st.session_state.carrito:
                        df_stock.loc[df_stock["Accesorio"]==x["Producto"], "Stock"] += (x["Cant"]*sig)
                    df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                    if cp != "Consumidor Final":
                        idx = df_clientes[df_clientes["Nombre"]==cp].index[0]
                        df_clientes.at[idx, "Saldo"] += (tot * sig * -1)
                        df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                        nm = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m %H:%M"), "Cliente": cp, "Tipo": acc, "Monto": tot, "Metodo": "-", "Detalle": "Venta"}])
                        pd.concat([df_movs, nm]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                    st.session_state.orden_lista = generar_pdf_binario(cp, st.session_state.carrito, tot, df_clientes, acc)
                    st.session_state.confirmar_accion = None; st.rerun()
            if st.session_state.orden_lista:
                st.download_button("⬇️ BAJAR FINAL", st.session_state.orden_lista, "Comprobante.pdf", "application/pdf")

    with t[5]: # ORDENES
        st.header("Historial")
        st.dataframe(df_movs.sort_index(ascending=False), use_container_width=True)

    with t[6]: # CIERRE
        st.header("Cierre de Caja")
        m1, m2 = st.columns(2)
        m1.metric("Valor Stock (Costo)", formatear_moneda((df_stock["Stock"]*df_stock["Costo Base"]).sum()))
        m2.metric("Total en la Calle", formatear_moneda(df_clientes["Saldo"].sum()))
