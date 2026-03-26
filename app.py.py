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
            # CORRECCIÓN 1: sep=None para evitar que las columnas se corran en el backup
            df = pd.read_csv(archivo, sep=None, engine='python', on_bad_lines='skip')
            df.columns = df.columns.str.strip()
            # Asegurar que todas las columnas existan
            for col in columnas:
                if col not in df.columns:
                    if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Flete", "Stock", "% Ganancia"]):
                        df[col] = 0.0
                    else:
                        df[col] = ""
            
            # Limpieza y conversión de tipos
            for col in df.columns:
                if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Flete", "Stock", "% Ganancia"]):
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
            
            return df[columnas]
        except Exception as e:
            st.error(f"Error cargando {archivo}: {e}")
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

COLS_ARTICULOS = ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"]
COLS_CLIENTES = ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"]
COLS_MOVS = ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"]

# Carga inicial
df_stock = cargar_datos(ARCHIVO_ARTICULOS, COLS_ARTICULOS)
df_clientes = cargar_datos(ARCHIVO_CLIENTES, COLS_CLIENTES)
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, COLS_MOVS)

# Estado del carrito
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
        try:
            self.image('logo.jpg', 10, 8, 33)
        except:
            pass
        self.set_font("Helvetica", "B", 15)
        self.cell(40)
        self.cell(0, 10, "AF ACCESORIOS - ALUMINIO", ln=True)
        self.set_font("Helvetica", "I", 9)
        self.cell(40)
        self.cell(0, 5, "Herrajes y Accesorios para Carpintería de Aluminio", ln=True)
        self.set_font("Helvetica", "", 9)
        self.cell(40)
        self.cell(0, 5, "Casilda, Santa Fe | WhatsApp: +54 9 341 351-2049", ln=True)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")

def generar_pdf_binario(cliente_nombre, carrito, total, df_clientes, titulo="PRESUPUESTO"):
    try:
        pdf = PDF()
        pdf.add_page()
        
        # Info Cliente
        info_cli = df_clientes[df_clientes["Nombre"] == cliente_nombre]
        tel = str(info_cli["Tel"].values[0]) if not info_cli.empty else "-"
        loc = str(info_cli["Localidad"].values[0]) if not info_cli.empty else "-"
        dir = str(info_cli["Direccion"].values[0]) if not info_cli.empty else "-"

        # Encabezado Documento
        pdf.set_fill_color(230, 230, 230)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, f" {titulo}", ln=True, fill=True)
        pdf.ln(2)
        
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(95, 8, f"CLIENTE: {cliente_nombre}", border="LT")
        pdf.cell(95, 8, f"FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}", border="RT", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(95, 8, f"TEL: {tel}", border="L")
        pdf.cell(95, 8, f"LOCALIDAD: {loc}", border="R", ln=True)
        pdf.cell(190, 8, f"DIRECCIÓN: {dir}", border="LRB", ln=True)
        pdf.ln(8)
        
        # Tabla
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
        
        # CORRECCIÓN 2: dest='S' para compatibilidad total con dispositivos móviles
        output = pdf.output(dest='S')
        if isinstance(output, str):
            return output.encode('latin-1')
        return bytes(output)
    except Exception as e:
        st.error(f"Error generando PDF: {e}")
        return None

# --- LÓGICA DE INTERFAZ ---
if es_cliente:
    st.title("🛒 Catálogo de Productos - AF Accesorios")
    busqueda = st.text_input("🔍 Buscar accesorio...", "").upper()
    
    df_ver = df_stock[df_stock["Accesorio"].str.contains(busqueda, na=False, case=False)]
    
    col_vta = st.columns(3)
    for idx, row in df_ver.reset_index().iterrows():
        with col_vta[idx % 3]:
            with st.container(border=True):
                # Foto
                nombre_foto = re.sub(r'[^a-zA-Z0-9]', '', str(row['Accesorio']))
                foto_path = os.path.join(CARPETA_FOTOS, f"{nombre_foto}.jpg")
                if os.path.exists(foto_path):
                    st.image(foto_path, use_container_width=True)
                else:
                    st.info("📷 Imagen no disponible")
                
                st.subheader(row["Accesorio"])
                st.write(f"**Rubro:** {row['Rubro']}")
                
                # Selección de lista para el cliente
                l_vta = st.radio("Condición de pago:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"], key=f"lv_{idx}")
                precio_vta = row[l_vta]
                st.markdown(f"### {formatear_moneda(precio_vta)}")
                
                cant_vta = st.number_input("Cantidad:", min_value=0, step=1, key=f"nv_{idx}")
                
                if st.button("Pedir por WhatsApp", key=f"bv_{idx}", use_container_width=True):
                    if cant_vta > 0:
                        msg = f"Hola! Quisiera pedir {cant_vta} unidades de: {row['Accesorio']} ({l_vta})."
                        link = f"https://wa.me/{WHATSAPP_NUM}?text={msg}"
                        st.markdown(f'<a href="{link}" target="_blank">📲 Confirmar pedido en WhatsApp</a>', unsafe_allow_html=True)
                    else:
                        st.warning("Ingresá una cantidad")

else:
    # --- INTERFAZ ADMINISTRADOR ---
    tabs = st.tabs(["📊 Stock", "🚚 Carga Lote", "⚙️ Maestro", "👥 Cuentas Corrientes", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre"])

    with tabs[0]: # TAB STOCK
        st.header("📊 Resumen de Inventario")
        if not df_stock.empty:
            m1, m2, m3 = st.columns(3)
            val_c = (df_stock['Costo Base'] * df_stock['Stock']).sum()
            val_l1 = (df_stock['Lista 1 (Cheques)'] * df_stock['Stock']).sum()
            val_l2 = (df_stock['Lista 2 (Efectivo)'] * df_stock['Stock']).sum()
            
            m1.metric("Capital (Costo)", formatear_moneda(val_c))
            m2.metric("Total Lista 1", formatear_moneda(val_l1))
            m3.metric("Total Lista 2", formatear_moneda(val_l2))
        
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

    with tabs[1]: # TAB LOTE
        st.header("🚚 Carga Masiva por Lote")
        df_lote = st.data_editor(pd.DataFrame(columns=COLS_ARTICULOS), num_rows="dynamic", use_container_width=True, key="editor_lote")
        if st.button("📥 Procesar e Integrar Lote"):
            df_lote = df_lote.dropna(subset=["Accesorio"])
            if not df_lote.empty:
                df_stock = pd.concat([df_stock, df_lote]).drop_duplicates(subset=["Accesorio"], keep="last")
                df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                st.success("Lote integrado al maestro"); st.rerun()

    with tabs[2]: # TAB MAESTRO
        st.header("⚙️ Gestión del Maestro")
        df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True, key="maestro_full")
        if st.button("💾 Guardar Cambios en Maestro"):
            df_ed.to_csv(ARCHIVO_ARTICULOS, index=False)
            st.success("Cambios guardados"); st.rerun()

    with tabs[3]: # TAB CUENTAS CORRIENTES
        st.header("👥 Cuentas Corrientes")
        if not df_clientes.empty:
            c_sel = st.selectbox("Seleccionar Cliente:", df_clientes["Nombre"].tolist())
            idx_cli = df_clientes[df_clientes["Nombre"] == c_sel].index[0]
            
            col_d1, col_d2 = st.columns(2)
            col_d1.metric("Saldo Pendiente", formatear_moneda(df_clientes.at[idx_cli, "Saldo"]))
            col_d2.write(f"**Tel:** {df_clientes.at[idx_cli, 'Tel']} | **Localidad:** {df_clientes.at[idx_cli, 'Localidad']}")
            
            st.divider()
            col_hist, col_pago = st.columns([2, 1])
            
            with col_hist:
                st.subheader("Historial")
                h_cli = df_movs[df_movs["Cliente"] == c_sel].sort_index(ascending=False)
                for i, r in h_cli.iterrows():
                    # Lógica de colores según tipo
                    emoji = "🔴" if r["Tipo"] == "VENTA" else "🟢" if r["Tipo"] == "PAGO" else "🔵"
                    with st.expander(f"{emoji} {r['Fecha']} | {r['Tipo']} | {formatear_moneda(r['Monto'])}"):
                        st.write(f"**Detalle:** {r['Detalle']}")
                        if r["Tipo"] in ["VENTA", "N. CRÉDITO"]:
                            # Intentar reconstruir mini carrito para reimpresión
                            t_car = []
                            try:
                                items = str(r["Detalle"]).split(", ")
                                for it in items:
                                    m = re.search(r"(\d+)x (.*) \(á \$ (.*)\)", it.replace(".", "").replace(",", "."))
                                    if m:
                                        t_car.append({"Producto": m.group(2), "Cant": int(m.group(1)), "Precio U.": float(m.group(3)), "Subtotal": int(m.group(1))*float(m.group(3))})
                                if t_car:
                                    pdf_r = generar_pdf_binario(c_sel, t_car, r["Monto"], df_clientes, r["Tipo"])
                                    if pdf_r: st.download_button(f"🖨️ Reimprimir {r['Tipo']}", pdf_r, f"Re_{i}.pdf", "application/pdf", key=f"reim_{i}")
                            except: pass

            with col_pago:
                st.subheader("Registrar Cobro")
                m_pago = st.number_input("Monto:", min_value=0.0, step=100.0)
                met_pago = st.selectbox("Medio:", ["Efectivo", "Transferencia", "Cheque"])
                if st.button("Confirmar Pago"):
                    if m_pago > 0:
                        df_clientes.at[idx_cli, "Saldo"] -= m_pago
                        df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                        nuevo_p = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": c_sel, "Tipo": "PAGO", "Monto": m_pago, "Metodo": met_pago, "Detalle": f"Cobro en {met_pago}"}])
                        pd.concat([df_movs, nuevo_p]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                        st.success("Pago registrado"); st.rerun()

    with tabs[4]: # TAB PRESUPUESTADOR
        st.header("📄 Presupuestador y Ventas")
        c_p = st.selectbox("Cliente:", ["Consumidor Final"] + df_clientes["Nombre"].tolist(), key="sel_cli_pre")
        
        col_p1, col_p2, col_p3 = st.columns([3, 1, 1])
        with col_p1: prod_p = st.selectbox("Accesorio:", df_stock["Accesorio"].tolist())
        with col_p2: cant_p = st.number_input("Cant:", min_value=1, value=1)
        with col_p3: list_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
        
        if st.button("➕ Agregar al Carrito"):
            pu = df_stock[df_stock["Accesorio"] == prod_p][list_p].values[0]
            st.session_state.carrito.append({"Producto": prod_p, "Cant": cant_p, "Precio U.": pu, "Subtotal": pu * cant_p})
            st.rerun()
            
        if st.session_state.carrito:
            st.table(pd.DataFrame(st.session_state.carrito).assign(Subtotal=lambda x: x['Subtotal'].apply(formatear_moneda)))
            tot_pre = sum(i['Subtotal'] for i in st.session_state.carrito)
            st.subheader(f"Total: {formatear_moneda(tot_pre)}")
            
            b_p1, b_p2, b_p3 = st.columns(3)
            with b_p1:
                pdf_pre = generar_pdf_binario(c_p, st.session_state.carrito, tot_pre, df_clientes, "PRESUPUESTO")
                if pdf_pre: st.download_button("📥 Descargar Presupuesto", pdf_pre, "presupuesto.pdf", "application/pdf")
            with b_p2:
                if st.button("🚀 CONFIRMAR VENTA (ORDEN)"):
                    det_v = ", ".join([f"{i['Cant']}x {i['Producto']} (á {formatear_moneda(i['Precio U.'])})" for i in st.session_state.carrito])
                    # Descontar stock
                    for i in st.session_state.carrito:
                        df_stock.loc[df_stock["Accesorio"] == i["Producto"], "Stock"] -= i["Cant"]
                    df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                    # Sumar a saldo
                    if c_p != "Consumidor Final":
                        idx_c = df_clientes[df_clientes["Nombre"] == c_p].index[0]
                        df_clientes.at[idx_c, "Saldo"] += tot_pre
                        df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                    # Movimiento
                    pd.concat([df_movs, pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": c_p, "Tipo": "VENTA", "Monto": tot_pre, "Metodo": "-", "Detalle": det_v}])]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                    st.session_state.last_vta = generar_pdf_binario(c_p, st.session_state.carrito, tot_pre, df_clientes, "ORDEN DE TRABAJO")
                    st.session_state.carrito = []
                    st.success("Venta procesada con éxito"); st.rerun()
            with b_p3:
                if st.button("🗑️ Vaciar Carrito"):
                    st.session_state.carrito = []; st.rerun()
            
            if "last_vta" in st.session_state:
                st.download_button("⬇️ Descargar Último Comprobante", st.session_state.last_vta, "comprobante_final.pdf", "application/pdf")

    with tabs[5]: # TAB ÓRDENES
        st.header("📋 Historial Global")
        st.dataframe(df_movs.sort_index(ascending=False), use_container_width=True, hide_index=True)

    with tabs[6]: # TAB CIERRE
        st.header("🏁 Estado General")
        sc1, sc2 = st.columns(2)
        sc1.metric("Deuda Total de Clientes", formatear_moneda(df_clientes["Saldo"].sum()))
        sc2.metric("Valor Inventario (Costo)", formatear_moneda((df_stock["Stock"] * df_stock["Costo Base"]).sum()))
