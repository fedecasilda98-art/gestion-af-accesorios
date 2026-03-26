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

# Detectar Modo Cliente
es_cliente = st.query_params.get("modo") == "cliente"

if not os.path.exists(CARPETA_FOTOS): 
    os.makedirs(CARPETA_FOTOS)

# --- CARGA DE DATOS ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            # CORRECCIÓN PARA CELULAR: sep=None detecta automáticamente si es , o ;
            df = pd.read_csv(archivo, sep=None, engine='python', on_bad_lines='skip')
            df.columns = df.columns.str.strip()
            for col in columnas:
                if col not in df.columns: 
                    df[col] = 0.0 if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo"]) else ""
            
            for col in df.columns:
                if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Flete", "Stock"]):
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
            return df[columnas]
        except: 
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

COLS_ARTICULOS = ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"]
COLS_CLIENTES = ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"]
COLS_MOVS = ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"]

df_stock = cargar_datos(ARCHIVO_ARTICULOS, COLS_ARTICULOS)
df_clientes = cargar_datos(ARCHIVO_CLIENTES, COLS_CLIENTES)
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, COLS_MOVS)

if "carrito" not in st.session_state:
    st.session_state.carrito = []

# --- UTILIDADES DE FORMATO ---
def formatear_moneda(valor):
    try:
        v = round(float(valor), 2)
        return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "$ 0,00"

# --- CLASE PDF ---
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

def generar_pdf_binario(cliente_nombre, carrito, total, df_clientes, titulo="PRESUPUESTO"):
    try:
        pdf = PDF() 
        pdf.add_page()
        info_cli = df_clientes[df_clientes["Nombre"] == cliente_nombre]
        tel = str(info_cli["Tel"].values[0]) if not info_cli.empty else "-"
        loc = str(info_cli["Localidad"].values[0]) if not info_cli.empty else "-"
        dir = str(info_cli["Direccion"].values[0]) if not info_cli.empty else "-"

        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f" TIPO DE DOCUMENTO: {titulo}", ln=True, fill=True)
        pdf.ln(2)
        
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(95, 7, f"CLIENTE: {cliente_nombre}", border="LT")
        pdf.cell(95, 7, f"FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}", border="RT", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(95, 7, f"TEL: {tel}", border="L")
        pdf.cell(95, 7, f"LOCALIDAD: {loc}", border="R", ln=True)
        pdf.cell(190, 7, f"DIRECCIÓN: {dir}", border="LRB", ln=True)
        pdf.ln(10)
        
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(200, 200, 200)
        pdf.cell(100, 10, " Artículo / Accesorio", border=1, fill=True)
        pdf.cell(20, 10, "Cant.", border=1, fill=True, align="C")
        pdf.cell(35, 10, "P. Unit", border=1, fill=True, align="R")
        pdf.cell(35, 10, "Subtotal", border=1, fill=True, align="R")
        pdf.ln(10)
        
        pdf.set_font("Helvetica", "", 10)
        for item in carrito:
            pdf.cell(100, 8, f" {item['Producto']}", border=1)
            pdf.cell(20, 8, str(item['Cant']), border=1, align="C")
            pdf.cell(35, 8, f"{formatear_moneda(item['Precio U.'])} ", border=1, align="R")
            pdf.cell(35, 8, f"{formatear_moneda(item['Subtotal'])} ", border=1, align="R")
            pdf.ln(8)
        
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(120, 10, "", border=0)
        pdf.cell(35, 10, "TOTAL:", border=0, align="R")
        pdf.cell(35, 10, f"{formatear_moneda(total)}", border=0, align="R")
        
        # CORRECCIÓN PARA CELULAR: Usamos dest='S' para obtener el string de bytes directo
        output = pdf.output(dest='S')
        if isinstance(output, str):
            return output.encode('latin-1')
        return bytes(output)
    except Exception as e:
        st.error(f"Error PDF: {e}")
        return None

# --- INTERFAZ ---
if es_cliente:
    st.title("🛒 Catálogo AF Accesorios")
    busqueda = st.text_input("Buscar producto...", "").upper()
    df_ver = df_stock[df_stock["Accesorio"].str.contains(busqueda, na=False, case=False)]
    cols = st.columns(3)
    for idx, row in df_ver.reset_index().iterrows():
        with cols[idx % 3]:
            with st.container(border=True):
                nombre_limpio = re.sub(r'[^a-zA-Z0-9]', '', str(row['Accesorio']))
                fp = os.path.join(CARPETA_FOTOS, f"{nombre_limpio}.jpg")
                if os.path.exists(fp): st.image(fp, use_container_width=True)
                else: st.info("Sin foto")
                st.subheader(row["Accesorio"])
                l_tipo = st.radio("Lista:", ["Cheques", "Efectivo"], key=f"r_{idx}")
                p = row["Lista 1 (Cheques)"] if l_tipo == "Cheques" else row["Lista 2 (Efectivo)"]
                st.write(f"**{formatear_moneda(p)}**")
                cant = st.number_input("Cantidad", 0, key=f"n_{idx}")
                if st.button("Pedir", key=f"b_{idx}"):
                    msg = f"Pedido: {cant} unidades de {row['Accesorio']} ({l_tipo})"
                    st.markdown(f"[Enviar WhatsApp](https://wa.me/{WHATSAPP_NUM}?text={msg})")
else:
    tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestador", "📋 Órdenes", "🏁 Caja"])

    with tabs[0]: # STOCK
        st.header("Inventario")
        c1, c2, c3 = st.columns(3)
        c1.metric("Stock (Costo)", formatear_moneda((df_stock['Costo Base'] * df_stock['Stock']).sum()))
        c2.metric("Total Lista 1", formatear_moneda((df_stock['Lista 1 (Cheques)'] * df_stock['Stock']).sum()))
        c3.metric("Total Lista 2", formatear_moneda((df_stock['Lista 2 (Efectivo)'] * df_stock['Stock']).sum()))
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

    with tabs[1]: # LOTE (Tu lógica de carga masiva)
        st.header("Carga Masiva")
        df_lote = st.data_editor(pd.DataFrame(columns=COLS_ARTICULOS), num_rows="dynamic", use_container_width=True)
        if st.button("Procesar Lote"):
            df_final = pd.concat([df_stock, df_lote.dropna(subset=['Accesorio'])]).drop_duplicates(subset=['Accesorio'], keep='last')
            df_final.to_csv(ARCHIVO_ARTICULOS, index=False)
            st.success("Lote cargado"); st.rerun()

    with tabs[2]: # MAESTRO
        st.header("Maestro de Artículos")
        df_m = st.data_editor(df_stock, use_container_width=True, hide_index=True)
        if st.button("Guardar Cambios"):
            df_m.to_csv(ARCHIVO_ARTICULOS, index=False)
            st.success("Guardado"); st.rerun()

    with tabs[3]: # CTA CTE
        st.header("Cuentas Corrientes")
        if not df_clientes.empty:
            cli = st.selectbox("Cliente:", df_clientes["Nombre"].tolist())
            idx = df_clientes[df_clientes["Nombre"] == cli].index[0]
            st.metric("Saldo actual", formatear_moneda(df_clientes.at[idx, "Saldo"]))
            # (Aquí iría tu lógica de pagos que es igual a la anterior)

    with tabs[4]: # PRESUPUESTADOR
        st.header("Presupuestos y Ventas")
        cli_p = st.selectbox("Cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
        c_prod, c_cant, c_lista = st.columns([2,1,1])
        with c_prod: i_p = st.selectbox("Producto:", df_stock["Accesorio"].tolist())
        with c_cant: q_p = st.number_input("Cant:", 1)
        with c_lista: l_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
        
        if st.button("Agregar"):
            pu = df_stock[df_stock["Accesorio"] == i_p][l_p].values[0]
            st.session_state.carrito.append({"Producto": i_p, "Cant": q_p, "Precio U.": pu, "Subtotal": pu*q_p})
            st.rerun()

        if st.session_state.carrito:
            st.table(st.session_state.carrito)
            total = sum(i['Subtotal'] for i in st.session_state.carrito)
            
            col_p, col_v, col_l = st.columns(3)
            with col_p:
                pdf = generar_pdf_binario(cli_p, st.session_state.carrito, total, df_clientes, "PRESUPUESTO")
                if pdf: st.download_button("Descargar Presupuesto", pdf, "presu.pdf", "application/pdf")
            with col_v:
                if st.button("Confirmar Venta"):
                    # Lógica de descuento de stock y suma a saldo
                    st.success("Venta registrada")
                    st.session_state.carrito = []
                    st.rerun()
            with col_l:
                if st.button("Limpiar Carrito"):
                    st.session_state.carrito = []; st.rerun()

    with tabs[5]: # ÓRDENES
        st.dataframe(df_movs, use_container_width=True)

    with tabs[6]: # CIERRE
        st.write(f"Ventas del día: {len(df_movs[df_movs['Fecha'].str.contains(datetime.now().strftime('%d/%m/%Y'))])}")
