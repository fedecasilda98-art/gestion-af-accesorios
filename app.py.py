import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re
from fpdf import FPDF
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión AF Accesorios", layout="wide", initial_sidebar_state="collapsed")

# --- BLOQUE DE DIAGNÓSTICO ---
st.sidebar.write("### 🔍 Estado de Archivos")
if os.path.exists("data"):
    st.sidebar.success("Carpeta 'data' encontrada")
    archivos_en_data = os.listdir("data")
    st.sidebar.write(f"Archivos: {archivos_en_data}")
else:
    st.sidebar.error("Carpeta 'data' NO EXISTE")

# Definición de rutas y constantes
ARCHIVO_ARTICULOS = "data/lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "data/clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "data/movimientos_clientes.csv"
CARPETA_FOTOS = "data/fotos_productos"
WHATSAPP_NUM = "5493413512049"

# Columnas globales para evitar NameError
COLS_ARTICULOS = ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"]
COLS_CLIENTES = ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"]
COLS_MOVS = ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"]

# Detectar Modo Cliente
es_cliente = st.query_params.get("modo") == "cliente"

if not os.path.exists(CARPETA_FOTOS):
    os.makedirs(CARPETA_FOTOS)

# --- CARGA DE DATOS ---
def cargar_datos(archivo, columns):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            df.columns = df.columns.str.strip()
            for col in columns:
                if col not in df.columns:
                    df[col] = 0.0 if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo"]) else ""
            for col in df.columns:
                if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Flete", "Stock"]):
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
            return df[columns]
        except:
            return pd.DataFrame(columns=columns)
    return pd.DataFrame(columns=columns)

# Cargar DataFrames
df_stock = cargar_datos(ARCHIVO_ARTICULOS, COLS_ARTICULOS)
df_clientes = cargar_datos(ARCHIVO_CLIENTES, COLS_CLIENTES)
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, COLS_MOVS)

# Inicializar estados de sesión
if "carrito" not in st.session_state: st.session_state.carrito = []
if "remito_items" not in st.session_state: st.session_state.remito_items = []
if "confirmar_orden" not in st.session_state: st.session_state.confirmar_orden = False
if "confirmar_nc" not in st.session_state: st.session_state.confirmar_nc = False

# --- UTILIDADES ---
def formatear_moneda(valor):
    try:
        v = round(float(valor), 2)
        return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "$ 0,00"

class PDF(FPDF):
    def header(self):
        try: self.image('logo.jpg', 10, 8, 33)
        except: pass
        self.set_font("Helvetica", "B", 16)
        self.cell(40)
        self.cell(0, 10, "AF ACCESORIOS - ALUMINIO", ln=True)
        self.set_font("Helvetica", "", 10)
        self.cell(40)
        self.cell(0, 5, "Casilda, Santa Fe | WhatsApp: +54 9 341 351-2049", ln=True)
        self.ln(10)

def generar_pdf_binario(cliente_nombre, carrito, total, df_clientes, titulo="PRESUPUESTO", fecha_fija=None):
    try:
        pdf = PDF()
        pdf.add_page()
        info_cli = df_clientes[df_clientes["Nombre"] == cliente_nombre]
        tel = str(info_cli["Tel"].values[0]) if not info_cli.empty else "-"
        loc = str(info_cli["Localidad"].values[0]) if not info_cli.empty else "-"
        dire = str(info_cli["Direccion"].values[0]) if not info_cli.empty else "-"
        
        fecha_display = fecha_fija if fecha_fija else datetime.now().strftime('%d/%m/%Y %H:%M')

        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f" TIPO DE DOCUMENTO: {titulo}", ln=True, fill=True, border=1)
        pdf.ln(2)
        
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(95, 7, f" CLIENTE: {cliente_nombre}", border="LT")
        pdf.cell(95, 7, f" FECHA: {fecha_display}", border="RT", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(95, 7, f" TEL: {tel}", border="L")
        pdf.cell(95, 7, f" LOCALIDAD: {loc}", border="R", ln=True)
        pdf.cell(190, 7, f" DIRECCIÓN: {dire}", border="LRB", ln=True)
        pdf.ln(5)
        
        pdf.set_font("Helvetica", "B", 10); pdf.set_fill_color(200, 200, 200)
        pdf.cell(100, 10, " Artículo / Accesorio", border=1, fill=True)
        pdf.cell(20, 10, "Cant.", border=1, fill=True, align="C")
        pdf.cell(35, 10, "P. Unit", border=1, fill=True, align="R")
        pdf.cell(35, 10, "Subtotal", border=1, fill=True, align="R", ln=True)
        
        pdf.set_font("Helvetica", "", 10)
        for item in carrito:
            pdf.cell(100, 8, f" {item['Producto']}", border=1)
            pdf.cell(20, 8, str(item['Cant']), border=1, align="C")
            pdf.cell(35, 8, f"{formatear_moneda(item['Precio U.'])} ", border=1, align="R")
            pdf.cell(35, 8, f"{formatear_moneda(item['Subtotal'])} ", border=1, align="R", ln=True)
        
        pdf.ln(2); pdf.set_font("Helvetica", "B", 12)
        pdf.cell(155, 10, "TOTAL:", border=0, align="R")
        pdf.cell(35, 10, f"{formatear_moneda(total)}", border=1, align="R")
        
        return bytes(pdf.output(dest='S'))
    except Exception as e:
        st.error(f"Error PDF: {str(e)}")
        return b""

# --- INTERFAZ ---
if es_cliente:
    st.title("🛒 Catálogo AF Accesorios")
    busqueda = st.text_input("Buscar producto...", "").upper()
    df_ver = df_stock[df_stock["Accesorio"].str.contains(busqueda, na=False)]
    cols = st.columns(3)
    for idx, row in df_ver.iterrows():
        with cols[idx % 3]:
            with st.container(border=True):
                nombre_foto = re.sub(r'[^a-zA-Z0-9\s]', '', str(row['Accesorio']))
                fp = os.path.join(CARPETA_FOTOS, f"{nombre_foto}.jpg")
                if os.path.exists(fp): st.image(fp, use_container_width=True)
                st.subheader(row["Accesorio"])
                l_tipo = st.radio("Condición:", ["Cheques", "Efectivo/Transf."], key=f"cr_{idx}")
                p = row["Lista 1 (Cheques)"] if l_tipo == "Cheques" else row["Lista 2 (Efectivo)"]
                st.write(f"**{formatear_moneda(p)}**")
                c = st.number_input("Cantidad", 0, key=f"cn_{idx}")
                if st.button("Pedir", key=f"cb_{idx}"):
                    msg = f"Hola! Pedido de {c}x {row['Accesorio']} ({l_tipo})."
                    st.markdown(f"[Confirmar en WhatsApp](https://wa.me/{WHATSAPP_NUM}?text={msg})")
else:
    tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre", "📦 Remitos"])

    with tabs[0]: # STOCK
        st.header("Inventario Actual")
        if not df_stock.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Costo Stock", formatear_moneda((df_stock['Costo Base'] * df_stock['Stock']).sum()))
            c2.metric("Total Lista 1", formatear_moneda((df_stock['Lista 1 (Cheques)'] * df_stock['Stock']).sum()))
            c3.metric("Total Lista 2", formatear_moneda((df_stock['Lista 2 (Efectivo)'] * df_stock['Stock']).sum()))
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

    with tabs[1]: # LOTE
        st.header("🚚 Carga por Lote")
        df_lote_nuevo = pd.DataFrame(columns=["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Descripcion"])
        lote_editado = st.data_editor(df_lote_nuevo, num_rows="dynamic", use_container_width=True, key="lote_editor")
        if st.button("🚀 PROCESAR E INCORPORAR"):
            if lote_editado is not None and not lote_editado.empty:
                validos = lote_editado[lote_editado["Accesorio"].astype(str).str.strip() != ""].copy()
                procesados = []
                for _, r in validos.iterrows():
                    cb = float(r["Costo Base"]) if r["Costo Base"] else 0.0
                    fl = float(r["Flete"]) if r["Flete"] else 0.0
                    ga = float(r["% Ganancia"]) if r["% Ganancia"] else 0.0
                    l1 = round((cb + fl) * (1 + ga/100), 2)
                    procesados.append({
                        "Rubro": r["Rubro"], "Proveedor": r["Proveedor"], "Accesorio": r["Accesorio"],
                        "Stock": r["Stock"], "Costo Base": cb, "Flete": fl, "% Ganancia": ga,
                        "Lista 1 (Cheques)": l1, "Lista 2 (Efectivo)": round(l1 * 0.9, 2), "Descripcion": r["Descripcion"]
                    })
                df_f = pd.concat([df_stock, pd.DataFrame(procesados)], ignore_index=True)
                df_f.to_csv(ARCHIVO_ARTICULOS, index=False)
                st.success("Artículos agregados"); st.rerun()

    with tabs[2]: # MAESTRO
        st.header("⚙️ Maestro de Artículos")
        df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True, key="ed_maestro")
        if st.button("Guardar Cambios Maestro"):
            df_ed["Lista 1 (Cheques)"] = ((df_ed["Costo Base"] + df_ed["Flete"]) * (1 + df_ed["% Ganancia"] / 100)).round(2)
            df_ed["Lista 2 (Efectivo)"] = (df_ed["Lista 1 (Cheques)"] * 0.9).round(2)
            df_ed.to_csv(ARCHIVO_ARTICULOS, index=False)
            st.success("Base actualizada"); st.rerun()

    with tabs[3]: # CTA CTE
        st.header("👥 Gestión de Cuentas Corrientes")
        if not df_clientes.empty:
            cli_sel = st.selectbox("🔍 Seleccionar Cliente:", df_clientes["Nombre"].tolist())
            idx_c = df_clientes[df_clientes["Nombre"] == cli_sel].index[0]
            st.metric("Saldo Pendiente", formatear_moneda(df_clientes.at[idx_c, "Saldo"]))
            
            monto_p = st.number_input("Registrar Pago $:", min_value=0.0)
            if st.button("Confirmar Pago"):
                df_clientes.at[idx_c, "Saldo"] = round(df_clientes.at[idx_c, "Saldo"] - monto_p, 2)
                df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                n_mov = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": cli_sel, "Tipo": "PAGO", "Monto": monto_p, "Metodo": "Efectivo", "Detalle": "Pago recibido"}])
                pd.concat([df_movs, n_mov]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                st.success("Pago registrado"); st.rerun()

    with tabs[4]: # PRESUPUESTADOR
        st.header("📄 Generador de Presupuestos")
        cli_p = st.selectbox("Cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
        c1, c2, c3 = st.columns([2,1,1])
        with c1: i_p = st.selectbox("Artículo:", df_stock["Accesorio"].tolist())
        with c2: q_p = st.number_input("Cant:", min_value=1, value=1)
        with c3: l_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
        
        if st.button("➕ AGREGAR"):
            p_u = df_stock[df_stock["Accesorio"] == i_p][l_p].values[0]
            st.session_state.carrito.append({"Producto": i_p, "Cant": q_p, "Precio U.": p_u, "Subtotal": round(p_u * q_p, 2)})
            st.rerun()

        if st.session_state.carrito:
            st.table(st.session_state.carrito)
            total = round(sum(i["Subtotal"] for i in st.session_state.carrito), 2)
            st.subheader(f"TOTAL: {formatear_moneda(total)}")
            
            if st.button("✅ GENERAR ORDEN"):
                st.session_state.confirmar_orden = True
            
            if st.session_state.confirmar_orden:
                if st.button("SÍ, CONFIRMAR"):
                    # Lógica de resta de stock y saldo
                    for item in st.session_state.carrito:
                        df_stock.loc[df_stock["Accesorio"] == item["Producto"], "Stock"] -= item["Cant"]
                    if cli_p != "Consumidor Final":
                        df_clientes.loc[df_clientes["Nombre"] == cli_p, "Saldo"] += total
                        df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                    df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                    st.session_state.carrito = []
                    st.session_state.confirmar_orden = False
                    st.success("Orden procesada"); st.rerun()

    with tabs[5]: # ÓRDENES (HISTORIAL)
        st.header("📋 Historial de Operaciones")
        st.dataframe(df_movs.sort_index(ascending=False), use_container_width=True)

    with tabs[6]: # CIERRE
        st.header("🏁 Cierre")
        st.write("Resumen ejecutivo del negocio.")

    with tabs[7]: # REMITOS
        st.header("📦 Remitos")
        # Estructura similar al presupuestador para remitos...

st.divider()
with st.expander("🚀 CARGA MASIVA"):
    archivo_subido = st.file_uploader("Elegir CSV", type="csv")
    destino = st.selectbox("Destino", [ARCHIVO_ARTICULOS, ARCHIVO_CLIENTES, ARCHIVO_MOVIMIENTOS])
    if st.button("Subir"):
        if archivo_subido:
            with open(destino, "wb") as f: f.write(archivo_subido.getbuffer())
            st.success("Guardado"); st.rerun()
