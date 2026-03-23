import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
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
    st.info("Asegurate de tener el archivo 'secretos.json' y haber compartido la planilla con el mail del bot.")
    st.stop()

# --- CARGA DE DATOS SEGURA Y CORRECCIÓN DE PEGADO ---
def cargar_df_seguro(hoja, columnas_base):
    try:
        data = hoja.get_all_records()
        df = pd.DataFrame(data)
    except:
        df = pd.DataFrame()

    if df.empty:
        return pd.DataFrame(columns=columnas_base)

    # Lógica por si los datos se pegaron todos en la primera columna (separados por coma)
    if len(df.columns) < 3 and df.shape[0] > 0:
        primera_col = df.columns[0]
        if "," in str(df.iloc[0, 0]):
            df_temp = df[primera_col].str.split(',', expand=True)
            for i, col in enumerate(columnas_base):
                if i < len(df_temp.columns):
                    df_temp.rename(columns={df_temp.columns[i]: col}, inplace=True)
            df = df_temp

    # Normalización de nombres de columnas
    df.columns = [str(c).strip() for c in df.columns]
    for c in columnas_base:
        if c not in df.columns:
            df[c] = ""
            
    # Conversión numérica
    for col in df.columns:
        if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Flete", "Stock", "%"]):
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
            
    return df[columnas_base]

def guardar(hoja, df):
    hoja.clear()
    hoja.update([df.columns.values.tolist()] + df.values.tolist())

# Definición de Columnas
COLS_ART = ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"]
COLS_CLI = ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"]
COLS_MOV = ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"]

df_stock = cargar_df_seguro(sh_stock, COLS_ART)
df_clientes = cargar_df_seguro(sh_clientes, COLS_CLI)
df_movs = cargar_df_seguro(sh_movs, COLS_MOV)

if "carrito" not in st.session_state: st.session_state.carrito = []
if "confirm_del" not in st.session_state: st.session_state.confirm_del = False

# --- UTILIDADES ---
def formatear_moneda(v):
    return f"$ {round(float(v), 2):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 10, "AF ACCESORIOS - COMPROBANTE", ln=True, align="C")
        self.set_font("Helvetica", "", 9)
        self.cell(0, 5, "Aluminio y Herrajes | Gestión Nube", ln=True, align="C")
        self.ln(10)

def generar_pdf_binario(cli, car, tot, df_c, tit):
    pdf = PDF(); pdf.add_page()
    info = df_c[df_c["Nombre"] == cli]
    tel = info["Tel"].values[0] if not info.empty else "-"
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 10, f"TIPO: {tit} | CLIENTE: {cli} | TEL: {tel}", ln=True, border="B")
    pdf.ln(5)
    for i in car:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(100, 8, f"{i['Producto']}")
        pdf.cell(20, 8, f"x{i['Cant']}", align="C")
        pdf.cell(0, 8, f"{formatear_moneda(i['Subtotal'])}", ln=True, align="R")
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 10, f"TOTAL: {formatear_moneda(tot)}", ln=True, align="R", border="T")
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ ---
t = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presu", "📋 Movs"])

with t[0]: # STOCK VISUAL
    st.header("Inventario Real (Google Sheets)")
    st.dataframe(df_stock, use_container_width=True, hide_index=True)

with t[1]: # CARGA POR LOTE
    st.header("Carga Masiva de Mercadería")
    df_l = pd.DataFrame(columns=["articulo", "cantidad", "costos", "flete"])
    ed_l = st.data_editor(df_l, num_rows="dynamic", use_container_width=True)
    if st.button("Procesar y Actualizar Nube"):
        for _, f in ed_l.iterrows():
            idx = df_stock[df_stock["Accesorio"] == f["articulo"]].index
            if not idx.empty:
                df_stock.at[idx[0], "Stock"] += float(f["cantidad"])
                df_stock.at[idx[0], "Costo Base"] = float(f["costos"])
                df_stock.at[idx[0], "Flete"] = float(f["flete"])
        guardar(sh_stock, df_stock); st.success("¡Stock actualizado!"); st.rerun()

with t[2]: # MAESTRO DE ARTÍCULOS
    st.header("Editor Maestro (Base de Datos)")
    df_ed = st.data_editor(df_stock, use_container_width=True, num_rows="dynamic")
    if st.button("Guardar Cambios en Maestro"):
        guardar(sh_stock, df_ed); st.success("Datos sincronizados con Google Sheets"); st.rerun()

with t[3]: # CTA CTE COMPLETO
    st.header("Gestión de Clientes")
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("Seleccionar Cliente")
        if not df_clientes.empty:
            sel_cli = st.selectbox("Buscar:", ["Seleccionar..."] + df_clientes["Nombre"].tolist())
            if sel_cli != "Seleccionar...":
                idx_c = df_clientes[df_clientes["Nombre"] == sel_cli].index[0]
                st.metric("Saldo Actual", formatear_moneda(df_clientes.at[idx_c, "Saldo"]))
                
                with st.expander("⚙️ Modificar / Borrar Cliente"):
                    m_wa = st.text_input("WhatsApp:", df_clientes.at[idx_c, "Tel"])
                    m_loc = st.text_input("Localidad:", df_clientes.at[idx_c, "Localidad"])
                    if st.button("Actualizar Ficha"):
                        df_clientes.at[idx_c, "Tel"] = m_wa
                        df_clientes.at[idx_c, "Localidad"] = m_loc
                        guardar(sh_clientes, df_clientes); st.success("Actualizado!"); st.rerun()
                    
                    st.divider()
                    if st.button("🗑️ ELIMINAR CLIENTE"):
                        st.session_state.confirm_del = True
                    
                    if st.session_state.confirm_del:
                        st.warning(f"¿Segura que querés borrar a {sel_cli}?")
                        if st.button("SÍ, BORRAR DEFINITIVAMENTE"):
                            df_clientes = df_clientes.drop(idx_c)
                            guardar(sh_clientes, df_clientes)
                            st.session_state.confirm_del = False
                            st.rerun()

    with col_b:
        st.subheader("➕ Alta de Cliente")
        n_nom = st.text_input("Nombre Completo")
        n_tel = st.text_input("Teléfono/WA")
        if st.button("Crear Nuevo Cliente"):
            nuevo = pd.DataFrame([[n_nom, n_tel, "", "", 0.0]], columns=COLS_CLI)
            guardar(sh_clientes, pd.concat([df_clientes, nuevo], ignore_index=True)); st.rerun()

    if not df_clientes.empty and sel_cli != "Seleccionar...":
        st.divider()
        st.subheader(f"Historial de {sel_cli}")
        movs_c = df_movs[df_movs["Cliente"] == sel_cli].sort_index(ascending=False)
        for i, r in movs_c.iterrows():
            c_tag = "🔴" if r["Tipo"]=="VENTA" else "🟢" if r["Tipo"]=="PAGO" else "🔵"
            with st.expander(f"{c_tag} {r['Fecha']} - {r['Tipo']} - {formatear_moneda(r['Monto'])}"):
                st.write(f"Detalle: {r['Detalle']}")
                if r["Tipo"] in ["VENTA", "N. CRÉDITO"]:
                    items_rec = []
                    for it in str(r["Detalle"]).split(", "):
                        match = re.search(r"(\d+)x (.*) \(á \$ (.*)\)", it.replace(".", "").replace(",", "."))
                        if match:
                            q, p, pu = match.groups()
                            items_rec.append({"Producto": p, "Cant": int(q), "Subtotal": int(q)*float(pu)})
                    if items_rec:
                        p_data = generar_pdf_binario(sel_cli, items_rec, r["Monto"], df_clientes, r["Tipo"])
                        st.download_button(f"📄 Descargar {r['Tipo']} PDF", p_data, f"Doc_{i}.pdf")

        st.subheader("💵 Registrar Pago")
        pago = st.number_input("Entrada de efectivo $:", min_value=0.0)
        if st.button("Confirmar Cobro"):
            df_clientes.at[idx_c, "Saldo"] -= pago
            guardar(sh_clientes, df_clientes)
            n_m = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": sel_cli, "Tipo": "PAGO", "Monto": pago, "Metodo": "Efectivo", "Detalle": "Cobro registrado"}])
            guardar(sh_movs, pd.concat([df_movs, n_m])); st.rerun()

with t[4]: # PRESUPUESTADOR
    st.header("Operaciones de Venta")
    cli_p = st.selectbox("Cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
    c1, c2, c3 = st.columns([2,1,1])
    with c1: i_p = st.selectbox("Producto:", df_stock["Accesorio"].tolist())
    with c2: q_p = st.number_input("Cant:", min_value=1, value=1)
    with c3: l_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])

    if st.button("Añadir al Carrito"):
        p_unit = df_stock[df_stock["Accesorio"] == i_p][l_p].values[0]
        st.session_state.carrito.append({"Producto": i_p, "Cant": q_p, "Precio U.": p_unit, "Subtotal": p_unit*q_p})
        st.rerun()

    if st.session_state.carrito:
        df_car = pd.DataFrame(st.session_state.carrito)
        st.table(df_car)
        total_op = df_car["Subtotal"].sum()
        
        cv1, cv2, cv3 = st.columns(3)
        with cv1:
            if st.button(f"✅ VENTA ({formatear_moneda(total_op)})"):
                for it in st.session_state.carrito:
                    df_stock.loc[df_stock["Accesorio"] == it["Producto"], "Stock"] -= it["Cant"]
                guardar(sh_stock, df_stock)
                idx_v = df_clientes[df_clientes["Nombre"] == cli_p].index[0]
                df_clientes.at[idx_v, "Saldo"] += total_op
                guardar(sh_clientes, df_clientes)
                det_v = ", ".join([f"{x['Cant']}x {x['Producto']} (á {formatear_moneda(x['Precio U.'])})" for x in st.session_state.carrito])
                n_v = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": cli_p, "Tipo": "VENTA", "Monto": total_op, "Metodo": "-", "Detalle": det_v}])
                guardar(sh_movs, pd.concat([df_movs, n_v]))
                st.session_state.carrito = []; st.success("Venta Exitosa"); st.rerun()
        with cv2:
            if st.button("🔵 NOTA CRÉDITO"):
                for it in st.session_state.carrito:
                    df_stock.loc[df_stock["Accesorio"] == it["Producto"], "Stock"] += it["Cant"]
                guardar(sh_stock, df_stock)
                idx_v = df_clientes[df_clientes["Nombre"] == cli_p].index[0]
                df_clientes.at[idx_v, "Saldo"] -= total_op
                guardar(sh_clientes, df_clientes)
                det_n = ", ".join([f"{x['Cant']}x {x['Producto']} (á {formatear_moneda(x['Precio U.'])})" for x in st.session_state.carrito])
                n_n = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": cli_p, "Tipo": "N. CRÉDITO", "Monto": total_op, "Metodo": "-", "Detalle": det_n}])
                guardar(sh_movs, pd.concat([df_movs, n_n]))
                st.session_state.carrito = []; st.info("Nota de Crédito Procesada"); st.rerun()
        with cv3:
            if st.button("🗑️ Limpiar Carrito"):
                st.session_state.carrito = []; st.rerun()

with t[5]: # HISTORIAL
    st.header("Historial Global")
    st.dataframe(df_movs, use_container_width=True, hide_index=True)
