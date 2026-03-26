import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re
from fpdf import FPDF

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión AF Accesorios", layout="wide", initial_sidebar_state="collapsed")

# Archivos Base
ARCHIVO_ARTICULOS = "lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "movimientos_clientes.csv"
CARPETA_FOTOS = "fotos_productos"
WHATSAPP_NUM = "5493413512049"

if not os.path.exists(CARPETA_FOTOS):
    os.makedirs(CARPETA_FOTOS)

# --- CARGA DE DATOS ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo, sep=None, engine='python', on_bad_lines='skip')
            df.columns = df.columns.str.strip()
            for col in columnas:
                if col not in df.columns:
                    df[col] = 0.0 if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Flete", "Stock"]) else ""
            return df[columnas]
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

COLS_ARTICULOS = ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"]
COLS_CLIENTES = ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"]
COLS_MOVS = ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"]

df_stock = cargar_datos(ARCHIVO_ARTICULOS, COLS_ARTICULOS)
df_clientes = cargar_datos(ARCHIVO_CLIENTES, COLS_CLIENTES)
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, COLS_MOVS)

if "carrito" not in st.session_state: st.session_state.carrito = []
if "venta_confirmada" not in st.session_state: st.session_state.venta_confirmada = False

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
        self.set_font("Helvetica", "B", 15); self.cell(40)
        self.cell(0, 10, "AF ACCESORIOS - ALUMINIO", ln=True)
        self.set_font("Helvetica", "I", 9); self.cell(40)
        self.cell(0, 5, "Casilda, Santa Fe | WhatsApp: +54 9 341 351-2049", ln=True); self.ln(10)

def generar_pdf_universal(cliente_n, detalle_str, monto, titulo="ORDEN DE TRABAJO"):
    try:
        pdf = PDF(); pdf.add_page()
        pdf.set_fill_color(230, 230, 230); pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, f" {titulo}", ln=True, fill=True); pdf.ln(2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(95, 8, f"CLIENTE: {cliente_n}", border="LT")
        pdf.cell(95, 8, f"FECHA: {datetime.now().strftime('%d/%m/%Y')}", border="RT", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(190, 8, f"DETALLE:\n{detalle_str}", border="LR")
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(190, 10, f"TOTAL: {formatear_moneda(monto)}", border="LRB", align="R", ln=True)
        return pdf.output(dest='S').encode('latin-1')
    except: return None

# --- INTERFAZ ---
tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cuentas Corrientes", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre"])

with tabs[3]: # --- CUENTAS CORRIENTES ---
    st.header("👥 Gestión de Clientes")
    if not df_clientes.empty:
        c_sel = st.selectbox("Seleccionar Cliente:", df_clientes["Nombre"].tolist())
        idx = df_clientes[df_clientes["Nombre"] == c_sel].index[0]
        
        st.info(f"### BALANCE DE CUENTA: {formatear_moneda(df_clientes.at[idx, 'Saldo'])}")

        with st.expander("📝 MODIFICAR DATOS Y SALDO"):
            m_n = st.text_input("Nombre:", df_clientes.at[idx, "Nombre"])
            m_t = st.text_input("Tel:", df_clientes.at[idx, "Tel"])
            m_l = st.text_input("Localidad:", df_clientes.at[idx, "Localidad"])
            m_d = st.text_input("Dirección:", df_clientes.at[idx, "Direccion"])
            m_s = st.number_input("Saldo Actual:", value=float(df_clientes.at[idx, "Saldo"]))
            if st.button("Guardar Cambios"):
                df_clientes.at[idx, "Nombre"], df_clientes.at[idx, "Tel"] = m_n, m_t
                df_clientes.at[idx, "Localidad"], df_clientes.at[idx, "Direccion"], df_clientes.at[idx, "Saldo"] = m_l, m_d, m_s
                df_clientes.to_csv(ARCHIVO_CLIENTES, index=False); st.success("Datos actualizados"); st.rerun()

        col_h, col_p = st.columns([2, 1])
        with col_h:
            st.subheader("Historial")
            h = df_movs[df_movs["Cliente"] == c_sel].sort_index(ascending=False)
            for i, r in h.iterrows():
                emo = "🔴" if r["Tipo"] == "VENTA" else "🟢" if r["Tipo"] == "PAGO" else "🔵"
                with st.expander(f"{emo} {r['Fecha']} | {r['Tipo']} | {formatear_moneda(r['Monto'])}"):
                    st.write(f"Detalle: {r['Detalle']}")
                    # IMPRIMIR DESDE CUENTA CORRIENTE (ORDEN TAL CUAL)
                    pdf_hist = generar_pdf_universal(c_sel, r["Detalle"], r["Monto"], "ORDEN DE TRABAJO" if r["Tipo"]=="VENTA" else "COMPROBANTE DE PAGO")
                    st.download_button("🖨️ Re-Imprimir Orden", pdf_hist, f"Orden_{i}.pdf", key=f"btn_h_{i}")

        with col_p:
            st.subheader("Cobro")
            m_p = st.number_input("Monto:", min_value=0.0, key="pago_ins")
            if st.button("Confirmar Pago"):
                df_clientes.at[idx, "Saldo"] -= m_p
                pd.concat([df_movs, pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": c_sel, "Tipo": "PAGO", "Monto": m_p, "Metodo": "Efectivo", "Detalle": "Pago a cuenta"}])]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                df_clientes.to_csv(ARCHIVO_CLIENTES, index=False); st.rerun()

with tabs[4]: # --- PRESUPUESTADOR ---
    st.header("📄 Presupuestador")
    cli_p = st.selectbox("Cliente:", ["Consumidor Final"] + df_clientes["Nombre"].tolist(), key="cli_pres")
    
    if not st.session_state.venta_confirmada:
        c1, c2, c3 = st.columns([3,1,1])
        with c1: p_sel = st.selectbox("Accesorio:", df_stock["Accesorio"].tolist())
        with c2: cant = st.number_input("Cant:", 1)
        with c3: lista = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
        if st.button("➕ AGREGAR"):
            pr = df_stock[df_stock["Accesorio"] == p_sel][lista].values[0]
            st.session_state.carrito.append({"Producto": p_sel, "Cant": cant, "Precio U.": pr, "Subtotal": pr*cant}); st.rerun()

    if st.session_state.carrito:
        for i, it in enumerate(st.session_state.carrito):
            cx = st.columns([4, 1, 2, 2, 1])
            cx[0].write(it["Producto"]); cx[1].write(f"x{it['Cant']}")
            cx[2].write(formatear_moneda(it["Precio U."])); cx[3].write(formatear_moneda(it["Subtotal"]))
            if not st.session_state.venta_confirmada and cx[4].button("🗑️", key=f"del_{i}"):
                st.session_state.carrito.pop(i); st.rerun()
        
        tot = sum(x["Subtotal"] for x in st.session_state.carrito)
        det_p = "\n".join([f"- {x['Cant']}x {x['Producto']}" for x in st.session_state.carrito])
        st.markdown(f"### Total: {formatear_moneda(tot)}")

        b1, b2, b3 = st.columns(3)
        with b1:
            pdf_pre = generar_pdf_universal(cli_p, det_p, tot, "PRESUPUESTO")
            st.download_button("📥 IMPRIMIR PRESUPUESTO", pdf_pre, "Presupuesto.pdf")
        with b2:
            if not st.session_state.venta_confirmada:
                if st.button("✅ CONFIRMAR Y CREAR ORDEN"):
                    for x in st.session_state.carrito: df_stock.loc[df_stock["Accesorio"] == x["Producto"], "Stock"] -= x["Cant"]
                    if cli_p != "Consumidor Final": df_clientes.loc[df_clientes["Nombre"] == cli_p, "Saldo"] += tot
                    pd.concat([df_movs, pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": cli_p, "Tipo": "VENTA", "Monto": tot, "Metodo": "-", "Detalle": det_p}])]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                    df_stock.to_csv(ARCHIVO_ARTICULOS, index=False); df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                    st.session_state.venta_confirmada = True; st.rerun()
            else:
                pdf_ord = generar_pdf_universal(cli_p, det_p, tot, "ORDEN DE TRABAJO")
                st.download_button("🖨️ IMPRIMIR ORDEN DE TRABAJO", pdf_ord, "Orden.pdf", type="primary")
        with b3:
            if st.button("🧹 NUEVA VENTA / LIMPIAR"):
                st.session_state.carrito = []; st.session_state.venta_confirmada = False; st.rerun()

with tabs[5]: st.dataframe(df_movs.sort_index(ascending=False), use_container_width=True)
with tabs[6]: st.metric("Saldo Global en Calle", formatear_moneda(df_clientes["Saldo"].sum()))
