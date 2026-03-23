import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re
from fpdf import FPDF

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="AF Accesorios - Gestión", layout="wide")

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
    st.error(f"Error de conexión: {e}"); st.stop()

def cargar_df_seguro(hoja, columnas_base):
    try:
        data = hoja.get_all_records()
        df = pd.DataFrame(data)
    except:
        df = pd.DataFrame()
    if df.empty: return pd.DataFrame(columns=columnas_base)
    
    # Limpieza de columnas
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

COLS_ART = ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"]
COLS_CLI = ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"]
COLS_MOV = ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"]

df_stock = cargar_df_seguro(sh_stock, COLS_ART)
df_clientes = cargar_df_seguro(sh_clientes, COLS_CLI)
df_movs = cargar_df_seguro(sh_movs, COLS_MOV)

if "carrito" not in st.session_state: st.session_state.carrito = []

def formatear_moneda(v): return f"$ {round(float(v), 2):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 15); self.cell(0, 10, "AF ACCESORIOS", ln=True, align="C")

def generar_pdf(cli, car, tot, df_c, tit):
    pdf = PDF(); pdf.add_page(); info = df_c[df_c["Nombre"] == cli]
    t = info["Tel"].values[0] if not info.empty else "-"
    pdf.set_font("Helvetica", "B", 10); pdf.cell(0, 10, f"{tit} | CLIENTE: {cli} | TEL: {t}", ln=True, border="B")
    for i in car:
        pdf.cell(100, 8, f"{i['Producto']}"); pdf.cell(20, 8, f"x{i['Cant']}"); pdf.cell(0, 8, f"{formatear_moneda(i['Subtotal'])}", ln=True, align="R")
    pdf.cell(0, 10, f"TOTAL: {formatear_moneda(tot)}", ln=True, align="R", border="T")
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ ---
tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presu", "📋 Movs"])

with tabs[0]: st.header("Inventario"); st.dataframe(df_stock, use_container_width=True, hide_index=True)

with tabs[1]:
    st.header("Carga Masiva (Lote)")
    df_l = pd.DataFrame(columns=["articulo", "cantidad", "costos", "flete"])
    ed_l = st.data_editor(df_l, num_rows="dynamic", use_container_width=True)
    if st.button("Subir Lote"):
        for _, f in ed_l.iterrows():
            idx = df_stock[df_stock["Accesorio"] == f["articulo"]].index
            if not idx.empty:
                df_stock.at[idx[0], "Stock"] += float(f["cantidad"])
                df_stock.at[idx[0], "Costo Base"] = float(f["costos"])
                df_stock.at[idx[0], "Flete"] = float(f["flete"])
        guardar(sh_stock, df_stock); st.success("Stock actualizado"); st.rerun()

with tabs[2]:
    st.header("Maestro")
    df_ed = st.data_editor(df_stock, use_container_width=True, num_rows="dynamic")
    if st.button("Guardar Cambios Maestro"):
        guardar(sh_stock, df_ed); st.success("Sincronizado"); st.rerun()

with tabs[3]: # CTA CTE RECARGADO (Alta, Baja, Modificación)
    st.header("Gestión de Clientes")
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("🔍 Seleccionar Cliente")
        if not df_clientes.empty:
            sel = st.selectbox("Cliente:", ["Seleccionar..."] + sorted(df_clientes["Nombre"].tolist()))
            if sel != "Seleccionar...":
                idx = df_clientes[df_clientes["Nombre"] == sel].index[0]
                st.metric("Saldo Actual", formatear_moneda(df_clientes.at[idx, "Saldo"]))
                
                # --- MODIFICACIÓN ---
                with st.expander("📝 Editar Datos de " + sel):
                    e_tel = st.text_input("WhatsApp:", df_clientes.at[idx, "Tel"])
                    e_loc = st.text_input("Localidad:", df_clientes.at[idx, "Localidad"])
                    e_dir = st.text_input("Dirección:", df_clientes.at[idx, "Direccion"])
                    if st.button("Confirmar Edición"):
                        df_clientes.at[idx, "Tel"], df_clientes.at[idx, "Localidad"], df_clientes.at[idx, "Direccion"] = e_tel, e_loc, e_dir
                        guardar(sh_clientes, df_clientes); st.success("Datos actualizados"); st.rerun()
                
                # --- BAJA ---
                with st.expander("🗑️ Borrar Cliente"):
                    st.warning(f"¿Estás segura de eliminar a {sel}?")
                    if st.button("SÍ, ELIMINAR CLIENTE"):
                        df_clientes = df_clientes.drop(idx)
                        guardar(sh_clientes, df_clientes)
                        st.success("Cliente borrado"); st.rerun()

    with col_b:
        st.subheader("➕ Nuevo Cliente")
        n_nom = st.text_input("Nombre Completo:")
        n_wa = st.text_input("Tel/WhatsApp:")
        if st.button("Crear Ficha"):
            if n_nom:
                nueva_ficha = pd.DataFrame([[n_nom, n_wa, "", "", 0.0]], columns=COLS_CLI)
                guardar(sh_clientes, pd.concat([df_clientes, nueva_ficha], ignore_index=True))
                st.success("Creado!"); st.rerun()

    if not df_clientes.empty and sel != "Seleccionar...":
        st.divider()
        st.subheader(f"Movimientos de {sel}")
        h = df_movs[df_movs["Cliente"] == sel].sort_index(ascending=False)
        for i, r in h.iterrows():
            emoji = "🔴" if r["Tipo"]=="VENTA" else "🟢" if r["Tipo"]=="PAGO" else "🔵"
            with st.expander(f"{emoji} {r['Fecha']} - {r['Tipo']} - {formatear_moneda(r['Monto'])}"):
                st.write(f"Detalle: {r['Detalle']}")
                if r["Tipo"] in ["VENTA", "N. CRÉDITO"]:
                    items = []
                    for it in str(r["Detalle"]).split(", "):
                        m = re.search(r"(\d+)x (.*) \(á \$ (.*)\)", it.replace(".", "").replace(",", "."))
                        if m: q, p, pu = m.groups(); items.append({"Producto": p, "Cant": int(q), "Subtotal": int(q)*float(pu)})
                    if items:
                        pdf = generar_pdf(sel, items, r["Monto"], df_clientes, r["Tipo"])
                        st.download_button(f"📄 PDF {i}", pdf, f"Doc_{i}.pdf")

        st.subheader("💵 Cobro")
        monto_p = st.number_input("Entrada $:", min_value=0.0)
        if st.button("Registrar Pago"):
            df_clientes.at[idx, "Saldo"] -= monto_p
            guardar(sh_clientes, df_clientes)
            n_m = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": sel, "Tipo": "PAGO", "Monto": monto_p, "Metodo": "Efectivo", "Detalle": "Cobro"}])
            guardar(sh_movs, pd.concat([df_movs, n_m])); st.rerun()

with tabs[4]: # PRESU / VENTAS
    st.header("Operaciones")
    if not df_clientes.empty:
        cli_p = st.selectbox("Cliente:", df_clientes["Nombre"].tolist())
        c1, c2, c3 = st.columns([2,1,1])
        with c1: i_p = st.selectbox("Accesorio:", df_stock["Accesorio"].tolist())
        with c2: q_p = st.number_input("Cant:", min_value=1, value=1)
        with c3: l_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
        if st.button("Añadir"):
            pu = df_stock[df_stock["Accesorio"] == i_p][l_p].values[0]
            st.session_state.carrito.append({"Producto": i_p, "Cant": q_p, "Precio U.": pu, "Subtotal": pu*q_p})
            st.rerun()
        if st.session_state.carrito:
            st.table(pd.DataFrame(st.session_state.carrito))
            tot = sum(x['Subtotal'] for x in st.session_state.carrito)
            if st.button(f"FINALIZAR VENTA ({formatear_moneda(tot)})"):
                for it in st.session_state.carrito: df_stock.loc[df_stock["Accesorio"] == it["Producto"], "Stock"] -= it["Cant"]
                guardar(sh_stock, df_stock)
                idx_v = df_clientes[df_clientes["Nombre"] == cli_p].index[0]
                df_clientes.at[idx_v, "Saldo"] += tot
                guardar(sh_clientes, df_clientes)
                det = ", ".join([f"{x['Cant']}x {x['Producto']} (á {formatear_moneda(x['Precio U.'])})" for x in st.session_state.carrito])
                n_v = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": cli_p, "Tipo": "VENTA", "Monto": tot, "Metodo": "-", "Detalle": det}])
                guardar(sh_movs, pd.concat([df_movs, n_v]))
                st.session_state.carrito = []; st.success("Venta guardada"); st.rerun()
