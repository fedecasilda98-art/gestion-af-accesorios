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
            df = pd.read_csv(archivo)
            df.columns = df.columns.str.strip()
            for col in columnas:
                if col not in df.columns: 
                    df[col] = 0.0 if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo"]) else ""
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

# --- UTILIDADES ---
def formatear_moneda(valor):
    v = 0.0 if abs(valor) < 0.001 else valor
    return f"$ {v:,.2f}"

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
    pdf = PDF() 
    pdf.add_page()
    info_cli = df_clientes[df_clientes["Nombre"] == cliente_nombre]
    tel = info_cli["Tel"].values[0] if not info_cli.empty else "-"
    loc = info_cli["Localidad"].values[0] if not info_cli.empty else "-"
    dir = info_cli["Direccion"].values[0] if not info_cli.empty else "-"

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
        pdf.cell(35, 8, f"$ {item['Precio U.']:,.2f} ", border=1, align="R")
        pdf.cell(35, 8, f"$ {item['Subtotal']:,.2f} ", border=1, align="R")
        pdf.ln(8)
    
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(120, 10, "", border=0)
    pdf.cell(35, 10, "TOTAL:", border=0, align="R")
    pdf.cell(35, 10, f"$ {total:,.2f}", border=0, align="R")
    return pdf.output(dest='S').encode('latin-1')

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
                st.write(f"**$ {p:,.2f}**")
                c = st.number_input("Cantidad", 0, key=f"cn_{idx}")
                if st.button("Pedir", key=f"cb_{idx}"):
                    msg = f"Hola AF Accesorios! Quiero pedir {c} de {row['Accesorio']} ({l_tipo})."
                    st.markdown(f"[Confirmar en WhatsApp](https://wa.me/{WHATSAPP_NUM}?text={msg})")
else:
    tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre de Caja"])

    with tabs[0]: # STOCK
        st.header("Inventario Actual")
        if not df_stock.empty:
            df_calc = df_stock.copy()
            for col in ["Stock", "Costo Base", "Lista 1 (Cheques)", "Lista 2 (Efectivo)"]:
                df_calc[col] = pd.to_numeric(df_calc[col], errors='coerce').fillna(0)
            c1, c2, c3 = st.columns(3)
            c1.metric("Valor Stock (Costo)", formatear_moneda((df_calc['Costo Base'] * df_calc['Stock']).sum()))
            c2.metric("Total Lista 1", formatear_moneda((df_calc['Lista 1 (Cheques)'] * df_calc['Stock']).sum()))
            c3.metric("Total Lista 2", formatear_moneda((df_calc['Lista 2 (Efectivo)'] * df_calc['Stock']).sum()))
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

    with tabs[1]: # LOTE
        st.header("🚚 Carga por Lote")
        df_lote_base = pd.DataFrame(columns=["articulo", "rubro", "cantidad", "costos", "flete", "articulo existente/nuevo"])
        st.data_editor(df_lote_base, num_rows="dynamic", use_container_width=True, key="ed_lote_full")
        st.info("Esta sección permite pre-cargar una lista antes de impactar en el Maestro.")

    with tabs[2]: # MAESTRO
        st.header("⚙️ Maestro de Artículos")
        df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True, key="ed_maestro_full")
        if st.button("Guardar Cambios Maestro"):
            df_ed.to_csv(ARCHIVO_ARTICULOS, index=False)
            st.success("¡Base de datos actualizada!"); st.rerun()

    with tabs[3]: # CTA CTE - COMPLETO CON REIMPRESIÓN
        st.header("👥 Gestión de Cuentas Corrientes")
        if not df_clientes.empty:
            cli_sel = st.selectbox("🔍 Seleccionar Cliente:", df_clientes["Nombre"].tolist(), key="busqueda_global_cli")
            idx_c = df_clientes[df_clientes["Nombre"] == cli_sel].index[0]
            
            c_info1, c_info2, c_info3 = st.columns(3)
            c_info1.metric("Saldo Pendiente", formatear_moneda(df_clientes.at[idx_c, "Saldo"]))
            c_info2.write(f"📞 **Tel:** {df_clientes.at[idx_c, 'Tel']} | 📍 **Loc:** {df_clientes.at[idx_c, 'Localidad']}")
            c_info3.write(f"🏠 **Dirección:** {df_clientes.at[idx_c, 'Direccion']}")
            
            st.divider()
            col_movs, col_ops = st.columns([2, 1])
            with col_movs:
                st.subheader("Historial de Movimientos")
                hist = df_movs[df_movs["Cliente"] == cli_sel].sort_index(ascending=False)
                for i, row in hist.iterrows():
                    color = "🔴" if row["Tipo"] == "VENTA" else "🟢" if row["Tipo"] == "PAGO" else "🔵"
                    with st.expander(f"{color} {row['Fecha']} | {row['Tipo']} | {formatear_moneda(row['Monto'])}"):
                        st.write(f"**Método:** {row['Metodo']}")
                        st.write(f"**Detalle:**")
                        if "," in str(row["Detalle"]):
                            for item in row["Detalle"].split(", "): st.markdown(f"* {item}")
                        else: st.write(row["Detalle"])
                        
                        if row["Tipo"] in ["VENTA", "N. CRÉDITO"]:
                            temp_carrito = []
                            items_raw = str(row["Detalle"]).split(", ")
                            for it in items_raw:
                                match = re.search(r"(\d+)x (.*) \(á \$ (.*)\)", it)
                                if match:
                                    cant, prod, pu = match.groups()
                                    pu_float = float(pu.replace(".", "").replace(",", "."))
                                    temp_carrito.append({"Producto": prod, "Cant": int(cant), "Precio U.": pu_float, "Subtotal": int(cant)*pu_float})
                            
                            if temp_carrito:
                                pdf_re = generar_pdf_binario(cli_sel, temp_carrito, row["Monto"], df_clientes, row["Tipo"])
                                st.download_button(f"🖨️ REIMPRIMIR {row['Tipo']}", pdf_re, f"Reimpresion_{row['Tipo']}_{i}.pdf", "application/pdf", key=f"re_{i}")

            with col_ops:
                st.subheader("Registrar Pago")
                monto_p = st.number_input("Monto $:", min_value=0.0, key="m_p_oper")
                metodo_p = st.selectbox("Método:", ["Efectivo", "Transferencia", "Cheque"], key="met_p_oper")
                detalle_p = st.text_input("Nota:", key="nota_p_oper")
                if st.button("Confirmar Pago"):
                    if monto_p > 0:
                        df_clientes.at[idx_c, "Saldo"] = round(df_clientes.at[idx_c, "Saldo"] - monto_p, 2)
                        df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                        n_mov = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": cli_sel, "Tipo": "PAGO", "Monto": monto_p, "Metodo": metodo_p, "Detalle": detalle_p}])
                        pd.concat([df_movs, n_mov]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                        st.success("Pago registrado."); st.rerun()

        st.divider()
        col_alta, col_mod, col_del = st.columns(3)
        with col_alta:
            with st.expander("➕ Nuevo Cliente"):
                n_n = st.text_input("Nombre"); n_t = st.text_input("Tel"); n_l = st.text_input("Loc"); n_d = st.text_input("Dir")
                if st.button("Guardar Nuevo"):
                    pd.concat([df_clientes, pd.DataFrame([[n_n, n_t, n_l, n_d, 0.0]], columns=COLS_CLIENTES)], ignore_index=True).to_csv(ARCHIVO_CLIENTES, index=False)
                    st.success("Cliente creado"); st.rerun()
        with col_mod:
            with st.expander("✏️ Editar Cliente"):
                if not df_clientes.empty:
                    cli_e = st.selectbox("Elegir:", df_clientes["Nombre"].tolist())
                    idx_e = df_clientes[df_clientes["Nombre"] == cli_e].index[0]
                    e_n = st.text_input("Nombre", value=df_clientes.at[idx_e, "Nombre"])
                    e_t = st.text_input("Teléfono", value=df_clientes.at[idx_e, "Tel"])
                    e_l = st.text_input("Localidad", value=df_clientes.at[idx_e, "Localidad"])
                    e_d = st.text_input("Dirección", value=df_clientes.at[idx_e, "Direccion"])
                    e_s = st.number_input("Saldo", value=float(df_clientes.at[idx_e, "Saldo"]))
                    if st.button("Actualizar Datos"):
                        v_n = df_clientes.at[idx_e, "Nombre"]
                        if v_n != e_n:
                            df_movs.loc[df_movs["Cliente"] == v_n, "Cliente"] = e_n
                            df_movs.to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                        df_clientes.at[idx_e, "Nombre"], df_clientes.at[idx_e, "Tel"], df_clientes.at[idx_e, "Localidad"], df_clientes.at[idx_e, "Direccion"], df_clientes.at[idx_e, "Saldo"] = e_n, e_t, e_l, e_d, round(e_s, 2)
                        df_clientes.to_csv(ARCHIVO_CLIENTES, index=False); st.success("Actualizado"); st.rerun()
        with col_del:
            with st.expander("🗑️ Borrar Cliente"):
                if not df_clientes.empty:
                    cli_d = st.selectbox("Borrar:", df_clientes["Nombre"].tolist(), key="del_sel_tab")
                    if st.checkbox("Confirmar eliminación"):
                        if st.button("ELIMINAR CLIENTE", type="primary"):
                            df_movs = df_movs[df_movs["Cliente"] != cli_d]
                            df_movs.to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                            df_clientes = df_clientes[df_clientes["Nombre"] != cli_d]
                            df_clientes.to_csv(ARCHIVO_CLIENTES, index=False); st.rerun()

    with tabs[4]: # PRESUPUESTADOR - COMPLETO CON N. CRÉDITO
        st.header("📄 Generador de Presupuestos e Impacto")
        cli_p = st.selectbox("Cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"], key="cp_p")
        p1, p2, p3 = st.columns([2, 1, 1])
        with p1: i_p = st.selectbox("Artículo:", df_stock["Accesorio"].tolist(), key="ip_p")
        with p2: q_p = st.number_input("Cant:", min_value=1, value=1)
        with p3: l_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])

        if st.button("Agregar al Carrito"):
            p_u = df_stock[df_stock["Accesorio"] == i_p][l_p].values[0]
            st.session_state.carrito.append({"Producto": i_p, "Cant": q_p, "Precio U.": p_u, "Subtotal": p_u * q_p})
            st.rerun()

        if st.session_state.carrito:
            df_car = pd.DataFrame(st.session_state.carrito); st.table(df_car)
            t_f = df_car["Subtotal"].sum()
            b1, b2, b3, b4 = st.columns(4)
            with b1:
                pdf_p = generar_pdf_binario(cli_p, st.session_state.carrito, t_f, df_clientes, "PRESUPUESTO")
                st.download_button("📥 DESCARGAR PRE.", pdf_p, f"Presu_{cli_p}.pdf", "application/pdf")
            with b2:
                if st.button("✅ ORDEN DE TRABAJO", use_container_width=True):
                    det_prod = ", ".join([f"{item['Cant']}x {item['Producto']} (á {formatear_moneda(item['Precio U.'])})" for item in st.session_state.carrito])
                    for item in st.session_state.carrito:
                        df_stock.loc[df_stock["Accesorio"] == item["Producto"], "Stock"] -= item["Cant"]
                    df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                    if cli_p != "Consumidor Final":
                        idx_cp = df_clientes[df_clientes["Nombre"] == cli_p].index[0]
                        df_clientes.at[idx_cp, "Saldo"] = round(df_clientes.at[idx_cp, "Saldo"] + t_f, 2)
                        df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                        pd.concat([df_movs, pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": cli_p, "Tipo": "VENTA", "Monto": t_f, "Metodo": "-", "Detalle": det_prod}])]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                    st.session_state.orden_lista = generar_pdf_binario(cli_p, st.session_state.carrito, t_f, df_clientes, "ORDEN DE TRABAJO")
                    st.rerun()
            with b3:
                if st.button("🔵 NOTA DE CRÉDITO", use_container_width=True):
                    det_prod = ", ".join([f"{item['Cant']}x {item['Producto']} (á {formatear_moneda(item['Precio U.'])})" for item in st.session_state.carrito])
                    for item in st.session_state.carrito:
                        df_stock.loc[df_stock["Accesorio"] == item["Producto"], "Stock"] += item["Cant"]
                    df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                    if cli_p != "Consumidor Final":
                        idx_cp = df_clientes[df_clientes["Nombre"] == cli_p].index[0]
                        df_clientes.at[idx_cp, "Saldo"] = round(df_clientes.at[idx_cp, "Saldo"] - t_f, 2)
                        df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                        pd.concat([df_movs, pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": cli_p, "Tipo": "N. CRÉDITO", "Monto": t_f, "Metodo": "-", "Detalle": det_prod}])]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                    st.session_state.orden_lista = generar_pdf_binario(cli_p, st.session_state.carrito, t_f, df_clientes, "NOTA DE CRÉDITO")
                    st.rerun()
            with b4:
                if st.button("🗑️ LIMPIAR TODO", use_container_width=True):
                    st.session_state.carrito = []; st.rerun()

            if "orden_lista" in st.session_state:
                st.download_button("⬇️ DESCARGAR COMPROBANTE FINAL", data=st.session_state.orden_lista, file_name=f"Final_{cli_p}.pdf", mime="application/pdf", type="primary", use_container_width=True)

    with tabs[5]: # ÓRDENES
        st.header("📋 Historial Global")
        st.dataframe(df_movs, use_container_width=True, hide_index=True)

    with tabs[6]: # CIERRE
        st.header("🏁 Cierre de Caja")
        c1, c2 = st.columns(2)
        v_s = (df_stock['Stock'] * pd.to_numeric(df_stock['Costo Base'], errors='coerce').fillna(0)).sum()
        c1.metric("Valor Total Stock (Costo)", formatear_moneda(v_s))
        c2.metric("Total Deuda Clientes", formatear_moneda(df_clientes['Saldo'].sum()))
