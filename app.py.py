import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re
from fpdf import FPDF

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="AF Accesorios - Gestión", layout="wide", initial_sidebar_state="collapsed")

# Archivos Base
ARCHIVO_ARTICULOS = "lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "movimientos_clientes.csv"
CARPETA_FOTOS = "fotos_productos"
WHATSAPP_NUM = "5493413512049"

es_cliente = st.query_params.get("modo") == "cliente"

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
            for col in df.columns:
                if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Flete", "Stock"]):
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
            return df[columnas]
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

COLS_ARTICULOS = ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"]
COLS_CLIENTES = ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"]
COLS_MOVS = ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"]

df_stock = cargar_datos(ARCHIVO_ARTICULOS, COLS_ARTICULOS)
df_clientes = cargar_datos(ARCHIVO_CLIENTES, COLS_CLIENTES)
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, COLS_MOVS)

if "carrito" not in st.session_state:
    st.session_state.carrito = []

def formatear_moneda(valor):
    try:
        v = round(float(valor), 2)
        return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "$ 0,00"

# --- LÓGICA DE PDF ---
class PDF(FPDF):
    def header(self):
        try: self.image('logo.jpg', 10, 8, 33)
        except: pass
        self.set_font("Helvetica", "B", 15); self.cell(40)
        self.cell(0, 10, "AF ACCESORIOS - ALUMINIO", ln=True)
        self.set_font("Helvetica", "I", 9); self.cell(40)
        self.cell(0, 5, "Casilda, Santa Fe | WhatsApp: +54 9 341 351-2049", ln=True); self.ln(10)

def generar_pdf_movimiento(cliente_row, mov_row, titulo="COMPROBANTE"):
    try:
        pdf = PDF(); pdf.add_page()
        pdf.set_fill_color(230, 230, 230); pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, f" {titulo}", ln=True, fill=True); pdf.ln(2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(95, 8, f"CLIENTE: {mov_row['Cliente']}", border="LT")
        pdf.cell(95, 8, f"FECHA: {mov_row['Fecha']}", border="RT", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(190, 8, f"DETALLE: {mov_row['Detalle']}", border="LR", ln=True)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(190, 10, f"TOTAL: {formatear_moneda(mov_row['Monto'])}", border="LRB", align="R", ln=True)
        output = pdf.output(dest='S')
        return output.encode('latin-1') if isinstance(output, str) else bytes(output)
    except: return None

def generar_presupuesto_bin(cliente_n, carrito, total, df_c, titulo="PRESUPUESTO"):
    try:
        pdf = PDF(); pdf.add_page()
        pdf.set_font("Helvetica", "B", 12); pdf.cell(0, 10, f" {titulo}", ln=True, fill=True)
        for it in carrito:
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(100, 8, f" {it['Producto']}", border=1)
            pdf.cell(20, 8, str(it['Cant']), border=1, align="C")
            pdf.cell(70, 8, f"{formatear_moneda(it['Subtotal'])}", border=1, align="R", ln=True)
        pdf.cell(190, 10, f"TOTAL: {formatear_moneda(total)}", align="R", ln=True)
        output = pdf.output(dest='S')
        return output.encode('latin-1') if isinstance(output, str) else bytes(output)
    except: return None

# --- INTERFAZ ---
if es_cliente:
    st.title("🛒 Catálogo AF Accesorios")
    # (Lógica de catálogo omitida por brevedad, se mantiene igual)
else:
    tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cuentas Corrientes", "📄 Presupuestador", "📋 Movimientos", "🏁 Cierre"])

    with tabs[3]:
        st.header("👥 Gestión de Cuentas Corrientes")
        with st.expander("➕ NUEVO CLIENTE"):
            with st.form("n_cli"):
                n_n = st.text_input("Nombre:")
                n_t = st.text_input("Tel:")
                n_l = st.text_input("Localidad:")
                n_d = st.text_input("Dirección:")
                n_s = st.number_input("Saldo Inicial:", value=0.0)
                if st.form_submit_button("Guardar Cliente"):
                    pd.concat([df_clientes, pd.DataFrame([{"Nombre":n_n,"Tel":n_t,"Localidad":n_l,"Direccion":n_d,"Saldo":n_s}])]).to_csv(ARCHIVO_CLIENTES, index=False); st.rerun()

        if not df_clientes.empty:
            c_sel = st.selectbox("Seleccionar Cliente:", df_clientes["Nombre"].tolist())
            idx = df_clientes[df_clientes["Nombre"] == c_sel].index[0]
            
            # BALANCE DE CUENTA
            st.info(f"### BALANCE ACTUAL: {formatear_moneda(df_clientes.at[idx, 'Saldo'])}")

            with st.expander("📝 MODIFICAR DATOS DE CLIENTE"):
                col_e1, col_e2 = st.columns(2)
                m_n = col_e1.text_input("Nombre:", df_clientes.at[idx, "Nombre"])
                m_t = col_e2.text_input("Tel:", df_clientes.at[idx, "Tel"])
                m_l = col_e1.text_input("Localidad:", df_clientes.at[idx, "Localidad"])
                m_d = col_e2.text_input("Dirección:", df_clientes.at[idx, "Direccion"])
                m_s = st.number_input("Editar Saldo Manualmente:", value=float(df_clientes.at[idx, "Saldo"]))
                if st.button("Guardar Cambios Totales"):
                    df_clientes.at[idx, "Nombre"], df_clientes.at[idx, "Tel"] = m_n, m_t
                    df_clientes.at[idx, "Localidad"], df_clientes.at[idx, "Direccion"], df_clientes.at[idx, "Saldo"] = m_l, m_d, m_s
                    df_clientes.to_csv(ARCHIVO_CLIENTES, index=False); st.success("Actualizado"); st.rerun()

            col_h, col_p = st.columns([2, 1])
            with col_h:
                st.subheader("Historial y Comprobantes")
                h = df_movs[df_movs["Cliente"] == c_sel].sort_index(ascending=False)
                for i, r in h.iterrows():
                    emo = "🔴" if r["Tipo"] == "VENTA" else "🟢" if r["Tipo"] == "PAGO" else "🔵"
                    with st.expander(f"{emo} {r['Fecha']} | {r['Tipo']} | {formatear_moneda(r['Monto'])}"):
                        st.write(f"Detalle: {r['Detalle']}")
                        # DESCARGA DESDE HISTORIAL
                        tit_pdf = "NOTA DE CRÉDITO" if r["Tipo"] == "PAGO" else "COMPROBANTE DE VENTA"
                        pdf_mov = generar_pdf_movimiento(df_clientes.iloc[idx], r, tit_pdf)
                        if pdf_mov: st.download_button(f"📥 Descargar {tit_pdf}", pdf_mov, f"{r['Tipo']}_{i}.pdf", key=f"dl_{i}")

            with col_p:
                st.subheader("Registrar Cobro")
                m_p = st.number_input("Monto Recibido:", min_value=0.0)
                if st.button("Confirmar Pago"):
                    df_clientes.at[idx, "Saldo"] -= m_p
                    pd.concat([df_movs, pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": c_sel, "Tipo": "PAGO", "Monto": m_p, "Metodo": "Efectivo", "Detalle": "Pago a cuenta"}])]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                    df_clientes.to_csv(ARCHIVO_CLIENTES, index=False); st.rerun()

    with tabs[4]:
        st.header("📄 Presupuestador")
        cli_p = st.selectbox("Cliente:", ["Consumidor Final"] + df_clientes["Nombre"].tolist())
        col_p1, col_p2, col_p3 = st.columns([3,1,1])
        with col_p1: p_sel = st.selectbox("Accesorio:", df_stock["Accesorio"].tolist())
        with col_p2: c_p = st.number_input("Cant:", 1)
        with col_p3: l_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
        
        if st.button("➕ AGREGAR"):
            pr = df_stock[df_stock["Accesorio"] == p_sel][l_p].values[0]
            st.session_state.carrito.append({"Producto": p_sel, "Cant": c_p, "Precio U.": pr, "Subtotal": pr*c_p}); st.rerun()

        if st.session_state.carrito:
            for i, it in enumerate(st.session_state.carrito):
                cx = st.columns([4, 1, 2, 2, 1])
                cx[0].write(it["Producto"]); cx[1].write(f"x{it['Cant']}")
                cx[2].write(formatear_moneda(it["Precio U."])); cx[3].write(formatear_moneda(it["Subtotal"]))
                if cx[4].button("🗑️", key=f"del_p_{i}"): st.session_state.carrito.pop(i); st.rerun()
            
            tot = sum(x["Subtotal"] for x in st.session_state.carrito)
            st.markdown(f"### Total: {formatear_moneda(tot)}")
            
            b1, b2, b3 = st.columns(3)
            with b1:
                pdf_p = generar_presupuesto_bin(cli_p, st.session_state.carrito, tot, df_clientes)
                if pdf_p: st.download_button("📥 IMPRIMIR PRESUPUESTO", pdf_p, "Presupuesto.pdf")
            with b2:
                if st.button("✅ CONFIRMAR ORDEN"):
                    for x in st.session_state.carrito: df_stock.loc[df_stock["Accesorio"] == x["Producto"], "Stock"] -= x["Cant"]
                    if cli_p != "Consumidor Final":
                        df_clientes.loc[df_clientes["Nombre"] == cli_p, "Saldo"] += tot
                    pd.concat([df_movs, pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": cli_p, "Tipo": "VENTA", "Monto": tot, "Metodo": "-", "Detalle": "Venta de accesorios"}])]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                    df_stock.to_csv(ARCHIVO_ARTICULOS, index=False); df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                    st.session_state.last_pdf = generar_presupuesto_bin(cli_p, st.session_state.carrito, tot, df_clientes, "ORDEN DE TRABAJO")
                    st.session_state.carrito = []; st.rerun()
            with b3: 
                if st.button("🧹 VACIAR"): st.session_state.carrito = []; st.rerun()
            if "last_pdf" in st.session_state: st.download_button("🖨️ IMPRIMIR ORDEN", st.session_state.last_pdf, "Orden.pdf")

    with tabs[5]: st.dataframe(df_movs.sort_index(ascending=False), use_container_width=True)
    with tabs[6]: st.metric("Saldo Global", formatear_moneda(df_clientes["Saldo"].sum()))
