import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re
from fpdf import FPDF

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión AF Accesorios", layout="wide")

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

# --- CARGA DE DATOS MEJORADA (Evita el error de 'Todo es Nombre') ---
def cargar_df_seguro(hoja, columnas_base):
    try:
        data = hoja.get_all_records()
        if not data:
            return pd.DataFrame(columns=columnas_base)
        df = pd.DataFrame(data)
    except:
        return pd.DataFrame(columns=columnas_base)

    # Limpieza profunda de columnas (quita espacios y mayúsculas/minúsculas)
    df.columns = [str(c).strip() for c in df.columns]
    
    # Si faltan columnas críticas, las creamos vacías para que no rompa
    for c in columnas_base:
        if c not in df.columns:
            df[c] = ""
            
    # Conversión de números
    for col in df.columns:
        if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Flete", "Stock"]):
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
    return df[columnas_base] # Retornamos solo las columnas que necesitamos en orden

def guardar(hoja, df):
    hoja.clear()
    hoja.update([df.columns.values.tolist()] + df.values.tolist())

# Estructuras de datos
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
        self.set_font("Helvetica", "B", 15); self.cell(0, 10, "AF ACCESORIOS - COMPROBANTE", ln=True, align="C")

def generar_pdf_binario(cli, car, tot, df_c, tit):
    pdf = PDF(); pdf.add_page()
    info = df_c[df_c["Nombre"] == cli]
    t = info["Tel"].values[0] if not info.empty else "-"
    pdf.set_font("Helvetica", "B", 10); pdf.cell(0, 10, f"{tit} | CLIENTE: {cli} | TEL: {t}", ln=True, border="B")
    pdf.ln(5)
    for i in car:
        pdf.cell(100, 8, f"{i['Producto']}"); pdf.cell(20, 8, f"x{i['Cant']}"); pdf.cell(0, 8, f"{formatear_moneda(i['Subtotal'])}", ln=True, align="R")
    pdf.ln(5); pdf.cell(0, 10, f"TOTAL: {formatear_moneda(tot)}", ln=True, align="R", border="T")
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ POR TABS ---
t = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presu", "📋 Movs", "🏁 Cierre"])

with t[0]:
    st.header("Inventario Actualizado")
    st.dataframe(df_stock, use_container_width=True, hide_index=True)

with t[1]:
    st.header("Carga Masiva (Lote)")
    df_l = pd.DataFrame(columns=["articulo", "cantidad", "costos", "flete"])
    ed_l = st.data_editor(df_l, num_rows="dynamic", use_container_width=True)
    if st.button("Procesar y Subir"):
        for _, f in ed_l.iterrows():
            idx = df_stock[df_stock["Accesorio"] == f["articulo"]].index
            if not idx.empty:
                df_stock.at[idx[0], "Stock"] += float(f["cantidad"])
                df_stock.at[idx[0], "Costo Base"] = float(f["costos"])
                df_stock.at[idx[0], "Flete"] = float(f["flete"])
        guardar(sh_stock, df_stock); st.success("¡Nube actualizada!"); st.rerun()

with t[3]: # CTA CTE - DETALLE Y REIMPRESIÓN
    st.header("Cuentas Corrientes")
    if not df_clientes.empty:
        # 1. Elegir al cliente
        sel_cli = st.selectbox("Buscar Cliente:", ["Seleccionar..."] + df_clientes["Nombre"].tolist())
        
        if sel_cli != "Seleccionar...":
            idx_c = df_clientes[df_clientes["Nombre"] == sel_cli].index[0]
            
            # 2. Mostrar Saldo
            st.metric("Saldo Pendiente", formatear_moneda(df_clientes.at[idx_c, "Saldo"]))
            
            # 3. Mostrar Movimientos y Reimpresión
            st.subheader(f"Movimientos de {sel_cli}")
            h = df_movs[df_movs["Cliente"] == sel_cli].sort_index(ascending=False)
            
            if h.empty:
                st.info("Sin movimientos registrados.")
            else:
                for i, r in h.iterrows():
                    color = "🔴" if r["Tipo"]=="VENTA" else "🟢" if r["Tipo"]=="PAGO" else "🔵"
                    with st.expander(f"{color} {r['Fecha']} - {r['Tipo']} - {formatear_moneda(r['Monto'])}"):
                        st.write(f"**Detalle:** {r['Detalle']}")
                        if r["Tipo"] in ["VENTA", "N. CRÉDITO"]:
                            # Reconstrucción del carrito para PDF
                            items_rec = []
                            for it in str(r["Detalle"]).split(", "):
                                match = re.search(r"(\d+)x (.*) \(á \$ (.*)\)", it.replace(".", "").replace(",", "."))
                                if match:
                                    q, p, pu = match.groups()
                                    items_rec.append({"Producto": p, "Cant": int(q), "Subtotal": int(q)*float(pu)})
                            
                            if items_rec:
                                pdf_data = generar_pdf_binario(sel_cli, items_rec, r["Monto"], df_clientes, r["Tipo"])
                                st.download_button(f"📄 Descargar {r['Tipo']} (PDF)", pdf_data, f"{r['Tipo']}_{i}.pdf", "application/pdf")
            
            st.divider()
            st.subheader("Registrar Cobro")
            pago = st.number_input("Monto Recibido:", min_value=0.0)
            if st.button("Confirmar Pago"):
                df_clientes.at[idx_c, "Saldo"] -= pago
                guardar(sh_clientes, df_clientes)
                nuevo_m = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": sel_cli, "Tipo": "PAGO", "Monto": pago, "Metodo": "Efectivo", "Detalle": "Cobro en efectivo"}])
                guardar(sh_movs, pd.concat([df_movs, nuevo_m])); st.rerun()

with t[4]: # PRESUPUESTADOR COMPLETO
    st.header("Ventas y Presupuestos")
    cli_p = st.selectbox("Para el cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
    
    col1, col2, col3 = st.columns([2,1,1])
    with col1: item_p = st.selectbox("Producto:", df_stock["Accesorio"].tolist())
    with col2: cant_p = st.number_input("Cant:", min_value=1, value=1)
    with col3: lista_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
    
    if st.button("Añadir al Carrito"):
        precio_u = df_stock[df_stock["Accesorio"] == item_p][lista_p].values[0]
        st.session_state.carrito.append({"Producto": item_p, "Cant": cant_p, "Precio U.": precio_u, "Subtotal": precio_u * cant_p})
        st.rerun()
        
    if st.session_state.carrito:
        df_car = pd.DataFrame(st.session_state.carrito)
        st.table(df_car)
        total_v = df_car["Subtotal"].sum()
        st.subheader(f"Total: {formatear_moneda(total_v)}")
        
        c_v1, c_v2 = st.columns(2)
        with c_v1:
            if st.button("✅ REGISTRAR VENTA"):
                for it in st.session_state.carrito:
                    df_stock.loc[df_stock["Accesorio"] == it["Producto"], "Stock"] -= it["Cant"]
                guardar(sh_stock, df_stock)
                # Actualizar saldo cliente
                idx_c_v = df_clientes[df_clientes["Nombre"] == cli_p].index[0]
                df_clientes.at[idx_c_v, "Saldo"] += total_v
                guardar(sh_clientes, df_clientes)
                # Movimiento
                det_v = ", ".join([f"{x['Cant']}x {x['Producto']} (á {formatear_moneda(x['Precio U.'])})" for x in st.session_state.carrito])
                n_v = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": cli_p, "Tipo": "VENTA", "Monto": total_v, "Metodo": "-", "Detalle": det_v}])
                guardar(sh_movs, pd.concat([df_movs, n_v]))
                st.session_state.carrito = []; st.success("Venta Exitosa"); st.rerun()
        with c_v2:
            if st.button("🗑️ Vaciar Carrito"):
                st.session_state.carrito = []; st.rerun()

with t[5]:
    st.header("Historial Global")
    st.dataframe(df_movs, use_container_width=True, hide_index=True)

with t[6]:
    st.header("Estado del Negocio")
    st.metric("Capital en Stock (Costo)", formatear_moneda((df_stock['Stock'] * df_stock['Costo Base']).sum()))
    st.metric("Deuda Total a Cobrar", formatear_moneda(df_clientes['Saldo'].sum()))
