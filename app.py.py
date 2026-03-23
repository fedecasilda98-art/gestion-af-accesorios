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
    # IMPORTANTE: Asegurate que el archivo se llame secretos.json
    creds = Credentials.from_service_account_file("secretos.json", scopes=scope)
    client = gspread.authorize(creds)
    return client.open("Gestion_AF_Accesorios")

try:
    planilla = conectar_google()
    sh_stock = planilla.worksheet("articulos")
    sh_clientes = planilla.worksheet("clientes")
    sh_movs = planilla.worksheet("movimientos")
except Exception as e:
    st.error(f"Error de conexión con Google: {e}")
    st.info("Revisá que el archivo secretos.json esté en la carpeta y que compartiste la planilla con el mail del bot.")
    st.stop()

# --- CARGA DE DATOS DESDE NUBE ---
def cargar_df(hoja):
    data = hoja.get_all_records()
    df = pd.DataFrame(data)
    for col in df.columns:
        if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Flete", "Stock"]):
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
    return df

def guardar_df(hoja, df):
    # Limpiar hoja y subir nuevos datos (incluyendo encabezados)
    hoja.clear()
    hoja.update([df.columns.values.tolist()] + df.values.tolist())

# Carga inicial
df_stock = cargar_df(sh_stock)
df_clientes = cargar_df(sh_clientes)
df_movs = cargar_df(sh_movs)

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
es_cliente = st.query_params.get("modo") == "cliente"

if es_cliente:
    st.title("🛒 Catálogo Online AF")
    # (Lógica de catálogo simplificada para móvil)
    busqueda = st.text_input("Buscar accesorio...").upper()
    df_ver = df_stock[df_stock["Accesorio"].str.contains(busqueda, na=False)]
    for _, row in df_ver.iterrows():
        with st.container(border=True):
            st.subheader(row["Accesorio"])
            st.write(f"Precio: {formatear_moneda(row['Lista 2 (Efectivo)'])}")
            if st.button("Pedir por WhatsApp", key=row["Accesorio"]):
                st.markdown(f"[Enviar Mensaje](https://wa.me/5493413512049?text=Hola! Quiero {row['Accesorio']})")

else:
    tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presu", "📋 Movs", "🏁 Cierre"])

    with tabs[0]: # STOCK
        st.header("Inventario en la Nube")
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

    with tabs[2]: # MAESTRO
        st.header("Editor Maestro")
        df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True)
        if st.button("Guardar Cambios en la Nube"):
            guardar_df(sh_stock, df_ed)
            st.success("¡Google Sheets actualizado!"); st.rerun()

    with tabs[3]: # CTA CTE - CON REIMPRESIÓN
        st.header("Cuentas Corrientes")
        if not df_clientes.empty:
            cli_sel = st.selectbox("Seleccionar Cliente:", df_clientes["Nombre"].tolist())
            idx_c = df_clientes[df_clientes["Nombre"] == cli_sel].index[0]
            st.metric("Saldo", formatear_moneda(df_clientes.at[idx_c, "Saldo"]))
            
            hist = df_movs[df_movs["Cliente"] == cli_sel].sort_index(ascending=False)
            for i, row in hist.iterrows():
                tipo_col = "🔴" if row["Tipo"] == "VENTA" else "🟢" if row["Tipo"] == "PAGO" else "🔵"
                with st.expander(f"{tipo_col} {row['Fecha']} | {row['Tipo']} | {formatear_moneda(row['Monto'])}"):
                    st.write(f"Detalle: {row['Detalle']}")
                    if row["Tipo"] in ["VENTA", "N. CRÉDITO"]:
                        # Lógica de reimpresión (extracción por regex)
                        temp_car = []
                        items = str(row["Detalle"]).split(", ")
                        for it in items:
                            m = re.search(r"(\d+)x (.*) \(á \$ (.*)\)", it.replace(".", "").replace(",", "."))
                            if m:
                                q, p, pu = m.groups()
                                temp_car.append({"Producto": p, "Cant": int(q), "Precio U.": float(pu), "Subtotal": int(q)*float(pu)})
                        if temp_car:
                            pdf_r = generar_pdf_binario(cli_sel, temp_car, row["Monto"], df_clientes, row["Tipo"])
                            st.download_button(f"🖨️ Reimprimir {i}", pdf_r, f"Comprobante_{i}.pdf", "application/pdf")

            monto_p = st.number_input("Registrar Pago $:", min_value=0.0, step=0.01)
            if st.button("Confirmar Pago"):
                df_clientes.at[idx_c, "Saldo"] = round(df_clientes.at[idx_c, "Saldo"] - monto_p, 2)
                guardar_df(sh_clientes, df_clientes)
                nuevo_m = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": cli_sel, "Tipo": "PAGO", "Monto": monto_p, "Metodo": "Efectivo", "Detalle": "Pago manual"}])
                df_m_total = pd.concat([df_movs, nuevo_m])
                guardar_df(sh_movs, df_m_total)
                st.success("Pago guardado en la nube"); st.rerun()

    with tabs[4]: # PRESUPUESTADOR - CON NOTAS DE CRÉDITO
        st.header("Presupuestos y Notas de Crédito")
        cli_p = st.selectbox("Cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
        i_p = st.selectbox("Artículo:", df_stock["Accesorio"].tolist())
        q_p = st.number_input("Cant:", min_value=1, value=1)
        l_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])

        if st.button("Añadir"):
            p_u = round(df_stock[df_stock["Accesorio"] == i_p][l_p].values[0], 2)
            st.session_state.carrito.append({"Producto": i_p, "Cant": q_p, "Precio U.": p_u, "Subtotal": round(p_u * q_p, 2)})
            st.rerun()

        if st.session_state.carrito:
            df_c = pd.DataFrame(st.session_state.carrito)
            st.table(df_c)
            total_f = round(df_c["Subtotal"].sum(), 2)
            
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("✅ VENTA (Orden)"):
                    for item in st.session_state.carrito:
                        df_stock.loc[df_stock["Accesorio"] == item["Producto"], "Stock"] -= item["Cant"]
                    guardar_df(sh_stock, df_stock)
                    idx_cp = df_clientes[df_clientes["Nombre"] == cli_p].index[0]
                    df_clientes.at[idx_cp, "Saldo"] = round(df_clientes.at[idx_cp, "Saldo"] + total_f, 2)
                    guardar_df(sh_clientes, df_clientes)
                    det = ", ".join([f"{i['Cant']}x {i['Producto']} (á {formatear_moneda(i['Precio U.'])})" for i in st.session_state.carrito])
                    nuevo_v = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": cli_p, "Tipo": "VENTA", "Monto": total_f, "Metodo": "-", "Detalle": det}])
                    guardar_df(sh_movs, pd.concat([df_movs, nuevo_v]))
                    st.success("Venta procesada"); st.session_state.carrito = []; st.rerun()
            
            with c2:
                if st.button("🔵 NOTA CRÉDITO"):
                    for item in st.session_state.carrito:
                        df_stock.loc[df_stock["Accesorio"] == item["Producto"], "Stock"] += item["Cant"]
                    guardar_df(sh_stock, df_stock)
                    idx_cp = df_clientes[df_clientes["Nombre"] == cli_p].index[0]
                    df_clientes.at[idx_cp, "Saldo"] = round(df_clientes.at[idx_cp, "Saldo"] - total_f, 2)
                    guardar_df(sh_clientes, df_clientes)
                    det = ", ".join([f"{i['Cant']}x {i['Producto']} (á {formatear_moneda(i['Precio U.'])})" for i in st.session_state.carrito])
                    nuevo_nc = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": cli_p, "Tipo": "N. CRÉDITO", "Monto": total_f, "Metodo": "-", "Detalle": det}])
                    guardar_df(sh_movs, pd.concat([df_movs, nuevo_nc]))
                    st.success("Nota de Crédito procesada"); st.session_state.carrito = []; st.rerun()
            
            with c3:
                if st.button("🗑️ Limpiar"):
                    st.session_state.carrito = []; st.rerun()

    with tabs[6]: # CIERRE
        st.header("Cierre de Caja Global")
        st.metric("Valor Stock", formatear_moneda((df_stock['Stock'] * df_stock['Costo Base']).sum()))
        st.metric("Total Deuda Clientes", formatear_moneda(df_clientes['Saldo'].sum()))
