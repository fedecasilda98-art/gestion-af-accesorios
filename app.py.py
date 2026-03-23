import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re
from fpdf import FPDF

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión AF Accesorios", layout="wide")

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

# --- CARGA DE DATOS SEGURA Y REPARACIÓN ---
def cargar_df_seguro(hoja, columnas_base):
    try:
        data = hoja.get_all_records()
        df = pd.DataFrame(data)
    except:
        df = pd.DataFrame()

    if df.empty:
        return pd.DataFrame(columns=columnas_base)

    # Si se pegó todo en la columna A separado por comas
    if len(df.columns) < 3 and "," in str(df.iloc[0, 0]):
        col_sucia = df.columns[0]
        df_limpio = df[col_sucia].str.split(',', expand=True)
        for i, col in enumerate(columnas_base):
            if i < len(df_limpio.columns):
                df_limpio.rename(columns={df_limpio.columns[i]: col}, inplace=True)
        df = df_limpio

    # Normalización
    df.columns = [str(c).strip() for c in df.columns]
    for c in columnas_base:
        if c not in df.columns: df[c] = ""
    
    for col in df.columns:
        if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Flete", "Stock"]):
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
            
    return df[columnas_base]

def guardar(hoja, df):
    hoja.clear()
    hoja.update([df.columns.values.tolist()] + df.values.tolist())

# Estructuras
COLS_ART = ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"]
COLS_CLI = ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"]
COLS_MOV = ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"]

df_stock = cargar_df_seguro(sh_stock, COLS_ART)
df_clientes = cargar_df_seguro(sh_clientes, COLS_CLI)
df_movs = cargar_df_seguro(sh_movs, COLS_MOV)

if "carrito" not in st.session_state: st.session_state.carrito = []

# --- UTILIDADES ---
def formatear_moneda(v):
    return f"$ {round(float(v), 2):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 10, "AF ACCESORIOS - HERRAJES", ln=True, align="C")
        self.ln(10)

def generar_pdf_binario(cli, car, tot, df_c, tit):
    pdf = PDF(); pdf.add_page()
    info = df_c[df_c["Nombre"] == cli]
    tel = info["Tel"].values[0] if not info.empty else "-"
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 10, f"{tit} | CLIENTE: {cli} | TEL: {tel}", ln=True, border="B")
    pdf.ln(5)
    for i in car:
        pdf.cell(100, 8, f"{i['Producto']}"); pdf.cell(20, 8, f"x{i['Cant']}", align="C")
        pdf.cell(0, 8, f"{formatear_moneda(i['Subtotal'])}", ln=True, align="R")
    pdf.cell(0, 10, f"TOTAL: {formatear_moneda(tot)}", ln=True, align="R", border="T")
    return pdf.output(dest='S').encode('latin-1')

# --- TABS ---
t = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presu", "📋 Movs"])

with t[0]: # VISTA STOCK
    st.header("Inventario en Tiempo Real")
    st.dataframe(df_stock, use_container_width=True, hide_index=True)

with t[1]: # CARGA LOTE
    st.header("Carga Masiva (Lote)")
    df_l = pd.DataFrame(columns=["articulo", "cantidad", "costos", "flete"])
    ed_l = st.data_editor(df_l, num_rows="dynamic", use_container_width=True)
    if st.button("Procesar y Actualizar"):
        for _, f in ed_l.iterrows():
            idx = df_stock[df_stock["Accesorio"] == f["articulo"]].index
            if not idx.empty:
                df_stock.at[idx[0], "Stock"] += float(f["cantidad"])
                df_stock.at[idx[0], "Costo Base"] = float(f["costos"])
                df_stock.at[idx[0], "Flete"] = float(f["flete"])
        guardar(sh_stock, df_stock); st.success("Stock actualizado!"); st.rerun()

with t[2]: # MAESTRO
    st.header("Editor Maestro de Base de Datos")
    df_ed = st.data_editor(df_stock, use_container_width=True, num_rows="dynamic", hide_index=True)
    if st.button("Sincronizar Maestro con Google Sheets"):
        guardar(sh_stock, df_ed); st.success("¡Datos guardados!"); st.rerun()

with t[3]: # CTA CTE COMPLETO (ALTA, BAJA, MODIFICACIÓN)
    st.header("Gestión de Clientes y Cuentas Corrientes")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Seleccionar Cliente")
        if not df_clientes.empty:
            sel = st.selectbox("Buscar:", ["Seleccionar..."] + sorted(df_clientes["Nombre"].tolist()))
            if sel != "Seleccionar...":
                idx_c = df_clientes[df_clientes["Nombre"] == sel].index[0]
                st.metric("Saldo Actual", formatear_moneda(df_clientes.at[idx_c, "Saldo"]))
                
                with st.expander("📝 Modificar / Eliminar Cliente"):
                    m_tel = st.text_input("WhatsApp:", df_clientes.at[idx_c, "Tel"])
                    m_loc = st.text_input("Localidad:", df_clientes.at[idx_c, "Localidad"])
                    if st.button("Guardar Cambios Contacto"):
                        df_clientes.at[idx_c, "Tel"], df_clientes.at[idx_c, "Localidad"] = m_tel, m_loc
                        guardar(sh_clientes, df_clientes); st.success("Actualizado"); st.rerun()
                    
                    st.divider()
                    if st.button("🗑️ ELIMINAR CLIENTE DEFINITIVAMENTE"):
                        st.session_state.confirmar_baja = True
                    
                    if st.session_state.get('confirmar_baja'):
                        st.warning(f"¿Estás segura de eliminar a {sel}?")
                        col_si, col_no = st.columns(2)
                        with col_si:
                            if st.button("SÍ, BORRAR"):
                                df_clientes = df_clientes.drop(idx_c)
                                guardar(sh_clientes, df_clientes)
                                st.session_state.confirmar_baja = False
                                st.rerun()
                        with col_no:
                            if st.button("CANCELAR"):
                                st.session_state.confirmar_baja = False
                                st.rerun()
    with c2:
        st.subheader("➕ Nuevo Cliente")
        n_n = st.text_input("Nombre:")
        n_t = st.text_input("Tel/WA:")
        if st.button("Crear Cliente"):
            nuevo_c = pd.DataFrame([[n_n, n_t, "", "", 0.0]], columns=COLS_CLI)
            guardar(sh_clientes, pd.concat([df_clientes, nuevo_c], ignore_index=True)); st.rerun()

    if not df_clientes.empty and sel != "Seleccionar...":
        st.divider()
        st.subheader(f"Movimientos y Reimpresión: {sel}")
        h_cli = df_movs[df_movs["Cliente"] == sel].sort_index(ascending=False)
        for i, r in h_cli.iterrows():
            tag = "🔴 VENTA" if r["Tipo"]=="VENTA" else "🟢 PAGO" if r["Tipo"]=="PAGO" else "🔵 N. CRÉDITO"
            with st.expander(f"{tag} - {r['Fecha']} - {formatear_moneda(r['Monto'])}"):
                st.write(f"Detalle: {r['Detalle']}")
                if r["Tipo"] in ["VENTA", "N. CRÉDITO"]:
                    items_rec = []
                    for it in str(r["Detalle"]).split(", "):
                        m = re.search(r"(\d+)x (.*) \(á \$ (.*)\)", it.replace(".", "").replace(",", "."))
                        if m: q, p, pu = m.groups(); items_rec.append({"Producto": p, "Cant": int(q), "Subtotal": int(q)*float(pu)})
                    if items_rec:
                        pdf_b = generar_pdf_binario(sel, items_rec, r["Monto"], df_clientes, r["Tipo"])
                        st.download_button(f"🖨️ PDF {i}", pdf_b, f"Doc_{i}.pdf")

        st.subheader("💵 Registrar Pago")
        pago_m = st.number_input("Monto Recibido $:", min_value=0.0)
        if st.button("Confirmar Cobro"):
            df_clientes.at[idx_c, "Saldo"] -= pago_m
            guardar(sh_clientes, df_clientes)
            n_p = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": sel, "Tipo": "PAGO", "Monto": pago_m, "Metodo": "Efectivo", "Detalle": "Pago de cliente"}])
            guardar(sh_movs, pd.concat([df_movs, n_p])); st.rerun()

with t[4]: # PRESU / VENTAS
    st.header("Generador de Ventas y Notas de Crédito")
    cli_p = st.selectbox("Cliente Operación:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
    c_v1, c_v2, c_v3 = st.columns([2,1,1])
    with c_v1: i_p = st.selectbox("Artículo:", df_stock["Accesorio"].tolist())
    with c_v2: q_p = st.number_input("Cant:", min_value=1, value=1, key="q_v")
    with c_v3: l_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])

    if st.button("Añadir Carrito"):
        pu = df_stock[df_stock["Accesorio"] == i_p][l_p].values[0]
        st.session_state.carrito.append({"Producto": i_p, "Cant": q_p, "Precio U.": pu, "Subtotal": pu*q_p})
        st.rerun()

    if st.session_state.carrito:
        df_car = pd.DataFrame(st.session_state.carrito)
        st.table(df_car)
        total_v = df_car["Subtotal"].sum()
        
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button(f"✅ VENTA ({formatear_moneda(total_v)})"):
                for it in st.session_state.carrito: df_stock.loc[df_stock["Accesorio"] == it["Producto"], "Stock"] -= it["Cant"]
                guardar(sh_stock, df_stock)
                idx_v = df_clientes[df_clientes["Nombre"] == cli_p].index[0]
                df_clientes.at[idx_v, "Saldo"] += total_v
                guardar(sh_clientes, df_clientes)
                det = ", ".join([f"{x['Cant']}x {x['Producto']} (á {formatear_moneda(x['Precio U.'])})" for x in st.session_state.carrito])
                guardar(sh_movs, pd.concat([df_movs, pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": cli_p, "Tipo": "VENTA", "Monto": total_v, "Metodo": "-", "Detalle": det}])]))
                st.session_state.carrito = []; st.success("Venta Exitosa"); st.rerun()
        with b2:
            if st.button("🔵 NOTA CRÉDITO"):
                for it in st.session_state.carrito: df_stock.loc[df_stock["Accesorio"] == it["Producto"], "Stock"] += it["Cant"]
                guardar(sh_stock, df_stock)
                idx_v = df_clientes[df_clientes["Nombre"] == cli_p].index[0]
                df_clientes.at[idx_v, "Saldo"] -= total_v
                guardar(sh_clientes, df_clientes)
                det = ", ".join([f"{x['Cant']}x {x['Producto']} (á {formatear_moneda(x['Precio U.'])})" for x in st.session_state.carrito])
                guardar(sh_movs, pd.concat([df_movs, pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": cli_p, "Tipo": "N. CRÉDITO", "Monto": total_v, "Metodo": "-", "Detalle": det}])]))
                st.session_state.carrito = []; st.info("Stock devuelto"); st.rerun()
        with b3:
            if st.button("🗑️ Vaciar"): st.session_state.carrito = []; st.rerun()

with t[5]: # HISTORIAL
    st.header("Historial de Movimientos Global")
    st.dataframe(df_movs, use_container_width=True, hide_index=True)
