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
            # CORRECCIÓN PARA CELULAR: sep=None detecta automáticamente , o ;
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

def formatear_moneda(valor):
    try:
        v = round(float(valor), 2)
        return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "$ 0,00"

# --- CLASE PDF ---
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
        # CORRECCIÓN PDF CELULAR: dest='S'
        output = pdf.output(dest='S')
        return output.encode('latin-1') if isinstance(output, str) else bytes(output)
    except: return None

# --- INTERFAZ ---
if es_cliente:
    st.title("🛒 Catálogo AF Accesorios")
    busqueda = st.text_input("🔍 Buscar...", "").upper()
    df_ver = df_stock[df_stock["Accesorio"].str.contains(busqueda, na=False, case=False)]
    col_v = st.columns(3)
    for idx, row in df_ver.reset_index().iterrows():
        with col_v[idx % 3]:
            with st.container(border=True):
                n_f = re.sub(r'[^a-zA-Z0-9]', '', str(row['Accesorio']))
                fp = os.path.join(CARPETA_FOTOS, f"{n_f}.jpg")
                if os.path.exists(fp): st.image(fp, use_container_width=True)
                st.subheader(row["Accesorio"])
                l_t = st.radio("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"], key=f"lv_{idx}")
                p_v = row[l_t]; st.write(f"### {formatear_moneda(p_v)}")
                c_v = st.number_input("Cant:", 0, key=f"nv_{idx}")
                if st.button("Pedir", key=f"bv_{idx}"):
                    msg = f"Pedido: {c_v} de {row['Accesorio']} ({l_t})"
                    st.markdown(f'<a href="https://wa.me/{WHATSAPP_NUM}?text={msg}" target="_blank">📲 WhatsApp</a>', unsafe_allow_html=True)
else:
    tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cuentas Corrientes", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre"])

    with tabs[0]: # --- STOCK ---
        st.header("📊 Stock")
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

    with tabs[1]: # --- LOTE ---
        st.header("🚚 Carga Masiva")
        df_lote = st.data_editor(pd.DataFrame(columns=COLS_ARTICULOS), num_rows="dynamic")
        if st.button("Integrar"):
            pd.concat([df_stock, df_lote.dropna(subset=["Accesorio"])]).to_csv(ARCHIVO_ARTICULOS, index=False); st.rerun()

    with tabs[2]: # --- MAESTRO ---
        st.header("⚙️ Maestro")
        df_m = st.data_editor(df_stock, use_container_width=True, hide_index=True)
        if st.button("Guardar"): df_m.to_csv(ARCHIVO_ARTICULOS, index=False); st.rerun()

    with tabs[3]: # --- CUENTAS CORRIENTES (COLOR Y GESTIÓN) ---
        st.header("👥 Gestión de Clientes")
        with st.expander("➕ NUEVO CLIENTE"):
            with st.form("nuevo_cli"):
                n_n = st.text_input("Nombre:")
                n_t = st.text_input("Tel:")
                n_l = st.text_input("Localidad:")
                n_d = st.text_input("Dirección:")
                n_s = st.number_input("Saldo Inicial:", value=0.0)
                if st.form_submit_button("Guardar"):
                    nuevo = pd.DataFrame([{"Nombre": n_n, "Tel": n_t, "Localidad": n_l, "Direccion": n_d, "Saldo": n_s}])
                    pd.concat([df_clientes, nuevo]).to_csv(ARCHIVO_CLIENTES, index=False); st.success("Creado"); st.rerun()

        if not df_clientes.empty:
            c_sel = st.selectbox("Seleccionar Cliente:", df_clientes["Nombre"].tolist())
            idx = df_clientes[df_clientes["Nombre"] == c_sel].index[0]
            
            with st.expander("📝 MODIFICAR / ELIMINAR"):
                m_n = st.text_input("Nombre:", df_clientes.at[idx, "Nombre"])
                m_t = st.text_input("Tel:", df_clientes.at[idx, "Tel"])
                if st.button("Actualizar"):
                    df_clientes.at[idx, "Nombre"], df_clientes.at[idx, "Tel"] = m_n, m_t
                    df_clientes.to_csv(ARCHIVO_CLIENTES, index=False); st.success("Guardado"); st.rerun()
                if st.button("🗑️ ELIMINAR CLIENTE"):
                    st.error(f"¿Desea eliminar definitivamente a {c_sel}?")
                    if st.button("SÍ, CONFIRMAR ELIMINACIÓN"):
                        df_clientes.drop(idx).to_csv(ARCHIVO_CLIENTES, index=False); st.rerun()

            st.divider()
            col_h, col_p = st.columns([2, 1])
            with col_h:
                st.subheader("Historial")
                h = df_movs[df_movs["Cliente"] == c_sel].sort_index(ascending=False)
                for i, r in h.iterrows():
                    emo = "🔴" if r["Tipo"] == "VENTA" else "🟢" if r["Tipo"] == "PAGO" else "🔵"
                    with st.expander(f"{emo} {r['Fecha']} | {r['Tipo']} | {formatear_moneda(r['Monto'])}"):
                        st.write(f"Detalle: {r['Detalle']}")
            with col_p:
                st.subheader("Cobro")
                m_p = st.number_input("Monto:", min_value=0.0)
                if st.button("Confirmar Pago"):
                    df_clientes.at[idx, "Saldo"] -= m_p
                    pd.concat([df_movs, pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": c_sel, "Tipo": "PAGO", "Monto": m_p, "Metodo": "Efectivo", "Detalle": "Cobro registrado"}])]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                    df_clientes.to_csv(ARCHIVO_CLIENTES, index=False); st.rerun()

    with tabs[4]: # --- PRESUPUESTADOR COMPLETO ---
        st.header("📄 Presupuestador")
        c_p = st.selectbox("Cliente:", ["Consumidor Final"] + df_clientes["Nombre"].tolist())
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1: prod = st.selectbox("Accesorio:", df_stock["Accesorio"].tolist())
        with col2: cant = st.number_input("Cant:", 1)
        with col3: lista = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
        
        if st.button("➕ AGREGAR"):
            precio = df_stock[df_stock["Accesorio"] == prod][lista].values[0]
            st.session_state.carrito.append({"Producto": prod, "Cant": cant, "Precio U.": precio, "Subtotal": precio*cant}); st.rerun()

        if st.session_state.carrito:
            st.subheader("Items Seleccionados")
            for i, it in enumerate(st.session_state.carrito):
                c = st.columns([4, 1, 2, 2, 1])
                c[0].write(it["Producto"])
                c[1].write(f"x{it['Cant']}")
                c[2].write(formatear_moneda(it["Precio U."]))
                c[3].write(formatear_moneda(it["Subtotal"]))
                if c[4].button("🗑️", key=f"d_{i}"):
                    st.session_state.carrito.pop(i); st.rerun()
            
            total_p = sum(x["Subtotal"] for x in st.session_state.carrito)
            st.markdown(f"### Total: {formatear_moneda(total_p)}")
            
            b1, b2, b3 = st.columns(3)
            with b1:
                pdf_pres = generar_pdf_binario(c_p, st.session_state.carrito, total_p, df_clientes, "PRESUPUESTO")
                if pdf_pres: st.download_button("📥 IMPRIMIR PRESUPUESTO", pdf_pres, "Presupuesto.pdf")
            with b2:
                if st.button("✅ CONFIRMAR VENTA/ORDEN"):
                    det = ", ".join([f"{x['Cant']}x {x['Producto']}" for x in st.session_state.carrito])
                    for x in st.session_state.carrito: df_stock.loc[df_stock["Accesorio"] == x["Producto"], "Stock"] -= x["Cant"]
                    if c_p != "Consumidor Final":
                        ic = df_clientes[df_clientes["Nombre"] == c_p].index[0]
                        df_clientes.at[ic, "Saldo"] += total_p
                    pd.concat([df_movs, pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": c_p, "Tipo": "VENTA", "Monto": total_p, "Metodo": "-", "Detalle": det}])]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                    df_stock.to_csv(ARCHIVO_ARTICULOS, index=False); df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                    st.session_state.last_pdf = generar_pdf_binario(c_p, st.session_state.carrito, total_p, df_clientes, "ORDEN DE TRABAJO")
                    st.session_state.carrito = []; st.success("Venta Exitosa"); st.rerun()
            with b3:
                if st.button("🧹 Vaciar"): st.session_state.carrito = []; st.rerun()
            
            if "last_pdf" in st.session_state:
                st.download_button("🖨️ IMPRIMIR ORDEN DE TRABAJO", st.session_state.last_pdf, "Orden.pdf", type="primary")

    with tabs[5]: st.header("📋 Órdenes"); st.dataframe(df_movs.sort_index(ascending=False), use_container_width=True)
    with tabs[6]: st.header("🏁 Cierre"); st.metric("Saldo Total en la Calle", formatear_moneda(df_clientes["Saldo"].sum()))
