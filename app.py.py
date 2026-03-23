import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re
from fpdf import FPDF
import io

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="AF Accesorios - Gestión Nube", layout="wide")

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

# --- FUNCIÓN DE LIMPIEZA DE DATOS PEGAJOSOS ---
def cargar_df_seguro(hoja, columnas_base):
    try:
        data = hoja.get_all_values()
        if not data:
            return pd.DataFrame(columns=columnas_base)
        
        # Si detectamos que todo está en una sola celda/columna
        if len(data[0]) == 1:
            # Intentamos reconstruir el DataFrame separando por comas
            lineas = [f[0] for f in data]
            # La primera línea suele ser el problema (RubroProveedor...)
            # Forzamos los encabezados correctos
            df = pd.read_csv(io.StringIO("\n".join(lineas)), names=columnas_base, skiprows=1)
        else:
            df = pd.DataFrame(data[1:], columns=data[0])
    except:
        df = pd.DataFrame(columns=columnas_base)

    # Limpieza de nombres de columnas
    df.columns = [str(c).strip() for c in df.columns]
    for c in columnas_base:
        if c not in df.columns: df[c] = ""
    
    # Conversión de números (precios y stock)
    for col in df.columns:
        if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Flete", "Stock", "%"]):
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
            
    return df[columnas_base]

def guardar(hoja, df):
    hoja.clear()
    hoja.update([df.columns.values.tolist()] + df.values.tolist())

# Estructuras oficiales
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

with tabs[0]: 
    st.header("Inventario de Herrajes")
    st.dataframe(df_stock, use_container_width=True, hide_index=True)

with tabs[2]: # MAESTRO DE ARTÍCULOS
    st.header("⚙️ Editor Maestro (Base de Datos)")
    st.info("Desde aquí podés corregir errores de tipeo o nombres de productos.")
    df_ed = st.data_editor(df_stock, use_container_width=True, num_rows="dynamic")
    if st.button("Sincronizar Cambios con la Nube"):
        guardar(sh_stock, df_ed); st.success("¡Google Sheets actualizado!"); st.rerun()

with tabs[3]: # CTA CTE COMPLETO
    st.header("Gestión de Clientes")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Selección y Edición")
        if not df_clientes.empty:
            sel_cli = st.selectbox("Elegir Cliente:", ["Seleccionar..."] + sorted(df_clientes["Nombre"].tolist()))
            if sel_cli != "Seleccionar...":
                idx = df_clientes[df_clientes["Nombre"] == sel_cli].index[0]
                st.metric("Saldo Pendiente", formatear_moneda(df_clientes.at[idx, "Saldo"]))
                
                with st.expander("📝 Editar Datos"):
                    e_wa = st.text_input("WhatsApp:", df_clientes.at[idx, "Tel"])
                    e_loc = st.text_input("Localidad:", df_clientes.at[idx, "Localidad"])
                    if st.button("Guardar Cambios Cliente"):
                        df_clientes.at[idx, "Tel"], df_clientes.at[idx, "Localidad"] = e_wa, e_loc
                        guardar(sh_clientes, df_clientes); st.rerun()
                
                with st.expander("🗑️ Eliminar Cliente"):
                    if st.button("Confirmar Borrado de " + sel_cli):
                        df_clientes = df_clientes.drop(idx)
                        guardar(sh_clientes, df_clientes); st.rerun()
    with c2:
        st.subheader("➕ Nuevo Cliente")
        n_nom = st.text_input("Nombre:")
        n_wa = st.text_input("Tel:")
        if st.button("Dar de Alta"):
            nueva = pd.DataFrame([[n_nom, n_wa, "", "", 0.0]], columns=COLS_CLI)
            guardar(sh_clientes, pd.concat([df_clientes, nueva], ignore_index=True)); st.rerun()

    if not df_clientes.empty and sel_cli != "Seleccionar...":
        st.divider()
        h = df_movs[df_movs["Cliente"] == sel_cli].sort_index(ascending=False)
        for i, r in h.iterrows():
            with st.expander(f"{r['Fecha']} - {r['Tipo']} - {formatear_moneda(r['Monto'])}"):
                st.write(f"Detalle: {r['Detalle']}")
                if r["Tipo"] in ["VENTA", "N. CRÉDITO"]:
                    items_rec = []
                    for it in str(r["Detalle"]).split(", "):
                        m = re.search(r"(\d+)x (.*) \(á \$ (.*)\)", it.replace(".", "").replace(",", "."))
                        if m: q, p, pu = m.groups(); items_rec.append({"Producto": p, "Cant": int(q), "Subtotal": int(q)*float(pu)})
                    if items_rec:
                        p_bin = generar_pdf(sel_cli, items_rec, r["Monto"], df_clientes, r["Tipo"])
                        st.download_button(f"📄 Descargar {r['Tipo']}", p_bin, f"Doc_{i}.pdf")

with tabs[4]: # VENTAS / PRESU
    st.header("Operaciones")
    cli_p = st.selectbox("Cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
    c_v1, c_v2, c_v3 = st.columns([2,1,1])
    with c_v1: i_p = st.selectbox("Artículo:", df_stock["Accesorio"].tolist())
    with c_v2: q_p = st.number_input("Cant:", min_value=1, value=1)
    with c_v3: l_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])

    if st.button("Añadir al Carrito"):
        p_u = df_stock[df_stock["Accesorio"] == i_p][l_p].values[0]
        st.session_state.carrito.append({"Producto": i_p, "Cant": q_p, "Precio U.": p_u, "Subtotal": p_u*q_p})
        st.rerun()

    if st.session_state.carrito:
        df_car = pd.DataFrame(st.session_state.carrito)
        st.table(df_car)
        total_v = df_car["Subtotal"].sum()
        if st.button(f"FINALIZAR VENTA ({formatear_moneda(total_v)})"):
            for it in st.session_state.carrito: df_stock.loc[df_stock["Accesorio"] == it["Producto"], "Stock"] -= it["Cant"]
            guardar(sh_stock, df_stock)
            idx_v = df_clientes[df_clientes["Nombre"] == cli_p].index[0]
            df_clientes.at[idx_v, "Saldo"] += total_v
            guardar(sh_clientes, df_clientes)
            det = ", ".join([f"{x['Cant']}x {x['Producto']} (á {formatear_moneda(x['Precio U.'])})" for x in st.session_state.carrito])
            guardar(sh_movs, pd.concat([df_movs, pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": cli_p, "Tipo": "VENTA", "Monto": total_v, "Metodo": "-", "Detalle": det}])]))
            st.session_state.carrito = []; st.success("¡Venta cargada!"); st.rerun()
