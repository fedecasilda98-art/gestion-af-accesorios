import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import os
from datetime import datetime
import re
from fpdf import FPDF

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión AF Accesorios", layout="wide", initial_sidebar_state="collapsed")

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def conectar_google():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file("secretos.json", scopes=scope)
    client = gspread.authorize(creds)
    return client.open("Gestion_AF_Accesorios")

try:
    planilla = conectar_google()
    sh_stock = planilla.worksheet("articulos")
    sh_clientes = planilla.worksheet("clientes")
    sh_movs = planilla.worksheet("movimientos")
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- CARGA DE DATOS SEGURA ---
def cargar_df_seguro(hoja, columnas_base):
    try:
        data = hoja.get_all_records()
        df = pd.DataFrame(data)
    except:
        df = pd.DataFrame()

    if df.empty or not all(c in df.columns for c in columnas_base):
        df = pd.DataFrame(columns=columnas_base)
        if "Accesorio" in columnas_base:
            fila_ej = {c: "" for c in columnas_base}
            fila_ej["Accesorio"] = "PRODUCTO DE PRUEBA"
            df = pd.concat([df, pd.DataFrame([fila_ej])], ignore_index=True)
        hoja.clear()
        hoja.update([df.columns.values.tolist()] + df.values.tolist())
    
    df.columns = [c.strip() for c in df.columns]
    for col in df.columns:
        if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Flete", "Stock"]):
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
    return df

def guardar_hoja(hoja, df):
    hoja.clear()
    hoja.update([df.columns.values.tolist()] + df.values.tolist())

# Definición de Columnas
COLS_ART = ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"]
COLS_CLI = ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"]
COLS_MOV = ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"]

df_stock = cargar_df_seguro(sh_stock, COLS_ART)
df_clientes = cargar_df_seguro(sh_clientes, COLS_CLI)
df_movs = cargar_df_seguro(sh_movs, COLS_MOV)

if "carrito" not in st.session_state:
    st.session_state.carrito = []

# --- UTILIDADES ---
def formatear_moneda(valor):
    v = round(float(valor), 2)
    return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "AF ACCESORIOS - ALUMINIO", ln=True, align="C")
        self.set_font("Helvetica", "", 10)
        self.cell(0, 5, "Gestión en la Nube | WhatsApp: +54 9 341 351-2049", ln=True, align="C")
        self.ln(10)

def generar_pdf_binario(cliente_nombre, carrito, total, df_clientes, titulo="PRESUPUESTO"):
    pdf = PDF() 
    pdf.add_page()
    info_cli = df_clientes[df_clientes["Nombre"] == cliente_nombre]
    tel = info_cli["Tel"].values[0] if not info_cli.empty else "-"
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, f" TIPO: {titulo}", ln=True, fill=True)
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(95, 7, f"CLIENTE: {cliente_nombre}", border="LT")
    pdf.cell(95, 7, f"FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}", border="RT", ln=True)
    pdf.cell(190, 7, f"TEL: {tel}", border="LRB", ln=True)
    pdf.ln(10)
    pdf.set_fill_color(200, 200, 200)
    pdf.cell(100, 10, " Artículo", border=1, fill=True)
    pdf.cell(20, 10, "Cant.", border=1, fill=True, align="C")
    pdf.cell(35, 10, "P. Unit", border=1, fill=True, align="R")
    pdf.cell(35, 10, "Subtotal", border=1, fill=True, align="R")
    pdf.ln(10)
    for item in carrito:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(100, 8, f" {item['Producto']}", border=1)
        pdf.cell(20, 8, str(item['Cant']), border=1, align="C")
        pdf.cell(35, 8, f"{formatear_moneda(item['Precio U.'])} ", border=1, align="R")
        pdf.cell(35, 8, f"{formatear_moneda(item['Subtotal'])} ", border=1, align="R")
        pdf.ln(8)
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(155, 10, "TOTAL:", border=0, align="R")
    pdf.cell(35, 10, f"{formatear_moneda(total)}", border=0, align="R")
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ ---
tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presu", "📋 Movs", "🏁 Cierre"])

with tabs[0]: # STOCK
    st.header("Inventario Real en la Nube")
    st.dataframe(df_stock, use_container_width=True, hide_index=True)

with tabs[1]: # LOTE
    st.header("🚚 Carga por Lote")
    st.write("Pegá aquí los datos para actualizar stock de forma masiva.")
    df_lote_base = pd.DataFrame(columns=["articulo", "rubro", "cantidad", "costos", "flete"])
    ed_lote = st.data_editor(df_lote_base, num_rows="dynamic", use_container_width=True)
    
    if st.button("Procesar Carga por Lote"):
        for _, fila in ed_lote.iterrows():
            idx = df_stock[df_stock["Accesorio"] == fila["articulo"]].index
            if not idx.empty:
                df_stock.at[idx[0], "Stock"] += float(fila["cantidad"])
                df_stock.at[idx[0], "Costo Base"] = float(fila["costos"])
                df_stock.at[idx[0], "Flete"] = float(fila["flete"])
        guardar_hoja(sh_stock, df_stock)
        st.success("¡Stock actualizado por lote!"); st.rerun()

with tabs[2]: # MAESTRO
    st.header("Editor Maestro")
    df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True, num_rows="dynamic")
    if st.button("Guardar Maestro"):
        guardar_hoja(sh_stock, df_ed); st.success("¡Guardado!"); st.rerun()

with tabs[3]: # CTA CTE
    st.header("Cuentas Corrientes")
    if not df_clientes.empty:
        cli_sel = st.selectbox("Seleccionar Cliente:", df_clientes["Nombre"].tolist())
        idx_c = df_clientes[df_clientes["Nombre"] == cli_sel].index[0]
        st.metric("Saldo", formatear_moneda(df_clientes.at[idx_c, "Saldo"]))
        
        hist = df_movs[df_movs["Cliente"] == cli_sel].sort_index(ascending=False)
        for i, row in hist.iterrows():
            with st.expander(f"{row['Fecha']} | {row['Tipo']} | {formatear_moneda(row['Monto'])}"):
                st.write(f"Detalle: {row['Detalle']}")
                if row["Tipo"] in ["VENTA", "N. CRÉDITO"]:
                    temp_car = []
                    for it in str(row["Detalle"]).split(", "):
                        m = re.search(r"(\d+)x (.*) \(á \$ (.*)\)", it.replace(".", "").replace(",", "."))
                        if m: q, p, pu = m.groups(); temp_car.append({"Producto": p, "Cant": int(q), "Precio U.": float(pu), "Subtotal": int(q)*float(pu)})
                    if temp_car:
                        pdf_r = generar_pdf_binario(cli_sel, temp_car, row["Monto"], df_clientes, row["Tipo"])
                        st.download_button(f"🖨️ Reimprimir {i}", pdf_r, f"Compro_{i}.pdf", "application/pdf")
        
        m_p = st.number_input("Pago $:", min_value=0.0)
        if st.button("Pagar"):
            df_clientes.at[idx_c, "Saldo"] = round(df_clientes.at[idx_c, "Saldo"] - m_p, 2)
            guardar_hoja(sh_clientes, df_clientes)
            n_m = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": cli_sel, "Tipo": "PAGO", "Monto": m_p, "Metodo": "Efectivo", "Detalle": "Pago"}])
            guardar_hoja(sh_movs, pd.concat([df_movs, n_m])); st.rerun()

with tabs[4]: # PRESUPUESTADOR
    st.header("Presupuestador / Venta / Notas de Crédito")
    cli_p = st.selectbox("Cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: i_p = st.selectbox("Artículo:", df_stock["Accesorio"].tolist())
    with c2: q_p = st.number_input("Cant:", min_value=1, value=1)
    with c3: l_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])

    if st.button("Añadir"):
        p_u = round(df_stock[df_stock["Accesorio"] == i_p][l_p].values[0], 2)
        st.session_state.carrito.append({"Producto": i_p, "Cant": q_p, "Precio U.": p_u, "Subtotal": round(p_u * q_p, 2)})
        st.rerun()

    if st.session_state.carrito:
        df_c = pd.DataFrame(st.session_state.carrito)
        st.table(df_c)
        total_f = round(df_c["Subtotal"].sum(), 2)
        
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("✅ VENTA"):
                for item in st.session_state.carrito: df_stock.loc[df_stock["Accesorio"] == item["Producto"], "Stock"] -= item["Cant"]
                guardar_hoja(sh_stock, df_stock)
                idx_cp = df_clientes[df_clientes["Nombre"] == cli_p].index[0]
                df_clientes.at[idx_cp, "Saldo"] = round(df_clientes.at[idx_cp, "Saldo"] + total_f, 2)
                guardar_hoja(sh_clientes, df_clientes)
                det = ", ".join([f"{i['Cant']}x {i['Producto']} (á {formatear_moneda(i['Precio U.'])})" for i in st.session_state.carrito])
                guardar_hoja(sh_movs, pd.concat([df_movs, pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": cli_p, "Tipo": "VENTA", "Monto": total_f, "Metodo": "-", "Detalle": det}])]))
                st.session_state.carrito = []; st.rerun()
        with b2:
            if st.button("🔵 NOTA CRÉDITO"):
                for item in st.session_state.carrito: df_stock.loc[df_stock["Accesorio"] == item["Producto"], "Stock"] += item["Cant"]
                guardar_hoja(sh_stock, df_stock)
                idx_cp = df_clientes[df_clientes["Nombre"] == cli_p].index[0]
                df_clientes.at[idx_cp, "Saldo"] = round(df_clientes.at[idx_cp, "Saldo"] - total_f, 2)
                guardar_hoja(sh_clientes, df_clientes)
                det = ", ".join([f"{i['Cant']}x {i['Producto']} (á {formatear_moneda(i['Precio U.'])})" for i in st.session_state.carrito])
                guardar_hoja(sh_movs, pd.concat([df_movs, pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": cli_p, "Tipo": "N. CRÉDITO", "Monto": total_f, "Metodo": "-", "Detalle": det}])]))
                st.session_state.carrito = []; st.rerun()
        with b3:
            if st.button("🗑️ Limpiar"): st.session_state.carrito = []; st.rerun()

with tabs[5]: # MOVS
    st.header("Historial Global")
    st.dataframe(df_movs, use_container_width=True, hide_index=True)

with tabs[6]: # CIERRE
    st.header("Cierre")
    st.metric("Valor Stock", formatear_moneda((df_stock['Stock'] * df_stock['Costo Base']).sum()))
    st.metric("Deuda Clientes", formatear_moneda(df_clientes['Saldo'].sum()))
