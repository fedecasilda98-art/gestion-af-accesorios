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
            # CORRECCIÓN 1: sep=None detecta automáticamente si usaste coma o punto y coma
            df = pd.read_csv(archivo, sep=None, engine='python', on_bad_lines='skip')
            df.columns = df.columns.str.strip()
            for col in columnas:
                if col not in df.columns:
                    if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Flete", "Stock", "% Ganancia"]):
                        df[col] = 0.0
                    else:
                        df[col] = ""
            for col in df.columns:
                if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Flete", "Stock", "% Ganancia"]):
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
            return df[columnas]
        except Exception as e:
            st.error(f"Error en {archivo}: {e}")
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

def formatear_moneda(valor):
    try:
        v = round(float(valor), 2)
        return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "$ 0,00"

class PDF(FPDF):
    def header(self):
        try: self.image('logo.jpg', 10, 8, 33)
        except: pass
        self.set_font("Helvetica", "B", 15); self.cell(40)
        self.cell(0, 10, "AF ACCESORIOS - ALUMINIO", ln=True)
        self.set_font("Helvetica", "I", 9); self.cell(40)
        self.cell(0, 5, "Casilda, Santa Fe | WhatsApp: +54 9 341 351-2049", ln=True); self.ln(10)
    def footer(self):
        self.set_y(-15); self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")

def generar_pdf_binario(cliente_nombre, carrito, total, df_clientes, titulo="PRESUPUESTO"):
    try:
        pdf = PDF(); pdf.add_page()
        info_cli = df_clientes[df_clientes["Nombre"] == cliente_nombre]
        tel = str(info_cli["Tel"].values[0]) if not info_cli.empty else "-"
        loc = str(info_cli["Localidad"].values[0]) if not info_cli.empty else "-"
        dir = str(info_cli["Direccion"].values[0]) if not info_cli.empty else "-"
        pdf.set_fill_color(230, 230, 230); pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, f" {titulo}", ln=True, fill=True); pdf.ln(2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(95, 8, f"CLIENTE: {cliente_nombre}", border="LT")
        pdf.cell(95, 8, f"FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}", border="RT", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(95, 8, f"TEL: {tel}", border="L")
        pdf.cell(95, 8, f"LOCALIDAD: {loc}", border="R", ln=True)
        pdf.cell(190, 8, f"DIRECCIÓN: {dir}", border="LRB", ln=True); pdf.ln(8)
        pdf.set_font("Helvetica", "B", 10); pdf.set_fill_color(200, 200, 200)
        pdf.cell(100, 10, " Artículo", border=1, fill=True); pdf.cell(20, 10, "Cant.", border=1, fill=True, align="C")
        pdf.cell(35, 10, "P. Unit", border=1, fill=True, align="R"); pdf.cell(35, 10, "Subtotal", border=1, fill=True, align="R"); pdf.ln(10)
        pdf.set_font("Helvetica", "", 10)
        for item in carrito:
            pdf.cell(100, 8, f" {item['Producto']}", border=1); pdf.cell(20, 8, str(item['Cant']), border=1, align="C")
            pdf.cell(35, 8, f"{formatear_moneda(item['Precio U.'])} ", border=1, align="R")
            pdf.cell(35, 8, f"{formatear_moneda(item['Subtotal'])} ", border=1, align="R"); pdf.ln(8)
        pdf.ln(5); pdf.set_font("Helvetica", "B", 12); pdf.cell(120, 10, "", border=0)
        pdf.cell(35, 10, "TOTAL:", border=0, align="R"); pdf.cell(35, 10, f"{formatear_moneda(total)}", border=0, align="R")
        # CORRECCIÓN 2: dest='S' devuelve el string de bytes para que el celu lo descargue bien
        output = pdf.output(dest='S')
        return output.encode('latin-1') if isinstance(output, str) else bytes(output)
    except Exception as e: st.error(f"Error PDF: {e}"); return None

# --- INTERFAZ ---
if es_cliente:
    st.title("🛒 Catálogo AF Accesorios")
    busqueda = st.text_input("🔍 Buscar accesorio...", "").upper()
    df_ver = df_stock[df_stock["Accesorio"].str.contains(busqueda, na=False, case=False)]
    col_v = st.columns(3)
    for idx, row in df_ver.reset_index().iterrows():
        with col_v[idx % 3]:
            with st.container(border=True):
                n_f = re.sub(r'[^a-zA-Z0-9]', '', str(row['Accesorio']))
                fp = os.path.join(CARPETA_FOTOS, f"{n_f}.jpg")
                if os.path.exists(fp): st.image(fp, use_container_width=True)
                else: st.info("📷 Sin imagen")
                st.subheader(row["Accesorio"])
                l_t = st.radio("Condición:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"], key=f"lv_{idx}")
                p_v = row[l_t]
                st.write(f"### {formatear_moneda(p_v)}")
                c_v = st.number_input("Cantidad:", 0, key=f"nv_{idx}")
                if st.button("Pedir por WhatsApp", key=f"bv_{idx}"):
                    msg = f"Hola AF Accesorios! Quiero pedir {c_v} de {row['Accesorio']} ({l_t})"
                    st.markdown(f'<a href="https://wa.me/{WHATSAPP_NUM}?text={msg}" target="_blank">📲 Enviar Pedido</a>', unsafe_allow_html=True)
else:
    tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cuentas Corrientes", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre"])

    with tabs[0]: # STOCK COMPLETO
        st.header("📊 Inventario Actual")
        if not df_stock.empty:
            m1, m2, m3 = st.columns(3)
            m1.metric("Capital (Costo)", formatear_moneda((df_stock['Costo Base'] * df_stock['Stock']).sum()))
            m2.metric("Total Lista 1", formatear_moneda((df_stock['Lista 1 (Cheques)'] * df_stock['Stock']).sum()))
            m3.metric("Total Lista 2", formatear_moneda((df_stock['Lista 2 (Efectivo)'] * df_stock['Stock']).sum()))
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

    with tabs[1]: # CARGA LOTE COMPLETA
        st.header("🚚 Carga por Lote")
        df_lote = st.data_editor(pd.DataFrame(columns=COLS_ARTICULOS), num_rows="dynamic", key="ed_lote")
        if st.button("📥 Integrar Lote"):
            pd.concat([df_stock, df_lote.dropna(subset=["Accesorio"])]).drop_duplicates(subset=["Accesorio"], keep="last").to_csv(ARCHIVO_ARTICULOS, index=False)
            st.success("Base actualizada"); st.rerun()

    with tabs[2]: # MAESTRO COMPLETO
        st.header("⚙️ Gestión del Maestro")
        df_m = st.data_editor(df_stock, use_container_width=True, hide_index=True, key="ed_maestro")
        if st.button("💾 Guardar Cambios"):
            df_m.to_csv(ARCHIVO_ARTICULOS, index=False); st.success("Guardado"); st.rerun()

    with tabs[3]: # CTA CTE CON NUEVAS FUNCIONES
        st.header("👥 Gestión de Clientes")
        with st.expander("➕ NUEVO CLIENTE"):
            with st.form("f_nuevo"):
                n_n = st.text_input("Nombre / Razón Social:")
                n_t = st.text_input("Tel:")
                n_l = st.text_input("Localidad:")
                n_d = st.text_input("Dirección:")
                n_s = st.number_input("Saldo Inicial:", value=0.0)
                if st.form_submit_button("Crear Cliente"):
                    nuevo = pd.DataFrame([{"Nombre": n_n, "Tel": n_t, "Localidad": n_l, "Direccion": n_d, "Saldo": n_s}])
                    pd.concat([df_clientes, nuevo]).to_csv(ARCHIVO_CLIENTES, index=False); st.success("Creado"); st.rerun()

        if not df_clientes.empty:
            c_sel = st.selectbox("Seleccionar Cliente:", df_clientes["Nombre"].tolist())
            idx = df_clientes[df_clientes["Nombre"] == c_sel].index[0]
            
            with st.expander("📝 MODIFICAR / ELIMINAR"):
                m_n = st.text_input("Nombre:", df_clientes.at[idx, "Nombre"])
                m_t = st.text_input("Tel:", df_clientes.at[idx, "Tel"])
                if st.button("Actualizar Datos"):
                    df_clientes.at[idx, "Nombre"], df_clientes.at[idx, "Tel"] = m_n, m_t
                    df_clientes.to_csv(ARCHIVO_CLIENTES, index=False); st.success("Actualizado"); st.rerun()
                if st.button("🗑️ ELIMINAR CLIENTE"):
                    st.error(f"¿Seguro que querés eliminar a {c_sel}?"); 
                    if st.button("SÍ, ELIMINAR"):
                        df_clientes.drop(idx).to_csv(ARCHIVO_CLIENTES, index=False); st.rerun()

            st.divider()
            col_h, col_p = st.columns([2, 1])
            with col_h:
                st.subheader("Historial")
                h = df_movs[df_movs["Cliente"] == c_sel].sort_index(ascending=False)
                for i, r in h.iterrows():
                    with st.expander(f"{r['Fecha']} | {r['Tipo']} | {formatear_moneda(r['Monto'])}"):
                        st.write(f"Detalle: {r['Detalle']}")
            with col_p:
                st.subheader("Registrar Cobro")
                m_p = st.number_input("Monto:", min_value=0.0)
                if st.button("Confirmar Pago"):
                    df_clientes.at[idx, "Saldo"] -= m_p
                    pd.concat([df_movs, pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": c_sel, "Tipo": "PAGO", "Monto": m_p, "Metodo": "Efectivo", "Detalle": "Cobro registrado"}])]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                    df_clientes.to_csv(ARCHIVO_CLIENTES, index=False); st.success("Pago guardado"); st.rerun()

    with tabs[4]: # PRESUPUESTADOR COMPLETO
        st.header("📄 Presupuestador")
        cli_p = st.selectbox("Cliente:", ["Consumidor Final"] + df_clientes["Nombre"].tolist())
        prod_p = st.selectbox("Accesorio:", df_stock["Accesorio"].tolist())
        cant_p = st.number_input("Cant:", 1)
        list_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
        if st.button("➕ Agregar"):
            pu = df_stock[df_stock["Accesorio"] == prod_p][list_p].values[0]
            st.session_state.carrito.append({"Producto": prod_p, "Cant": cant_p, "Precio U.": pu, "Subtotal": pu*cant_p}); st.rerun()
        if st.session_state.carrito:
            st.table(st.session_state.carrito); t = sum(i['Subtotal'] for i in st.session_state.carrito)
            if st.button("🚀 CONFIRMAR VENTA"):
                for i in st.session_state.carrito: df_stock.loc[df_stock["Accesorio"] == i["Producto"], "Stock"] -= i["Cant"]
                df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                if cli_p != "Consumidor Final":
                    ic = df_clientes[df_clientes["Nombre"] == cli_p].index[0]
                    df_clientes.at[ic, "Saldo"] += t; df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                pd.concat([df_movs, pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": cli_p, "Tipo": "VENTA", "Monto": t, "Metodo": "-", "Detalle": "Venta de productos"}])]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                st.session_state.carrito = []; st.success("Venta Exitosa"); st.rerun()

    with tabs[5]: st.dataframe(df_movs.sort_index(ascending=False), use_container_width=True)
    with tabs[6]: st.metric("Saldo Total Clientes", formatear_moneda(df_clientes["Saldo"].sum()))
