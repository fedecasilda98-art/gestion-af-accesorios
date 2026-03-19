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

if not os.path.exists(CARPETA_FOTOS): os.makedirs(CARPETA_FOTOS)

# --- CARGA DE DATOS ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            df.columns = df.columns.str.strip()
            # Escudo de columnas: asegura que Dirección y otras existan
            for col in columnas:
                if col not in df.columns: 
                    df[col] = 0.0 if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo"]) else ""
            return df[columnas]
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

COLS_ARTICULOS = ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"]
# Agregamos "Direccion" a la lista oficial de columnas
COLS_CLIENTES = ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"]
COLS_MOVS = ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"]

df_stock = cargar_datos(ARCHIVO_ARTICULOS, COLS_ARTICULOS)
df_clientes = cargar_datos(ARCHIVO_CLIENTES, COLS_CLIENTES)
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, COLS_MOVS)

if "carrito" not in st.session_state:
    st.session_state.carrito = []

# --- CLASE PDF ---
class PDF(FPDF):
    def header(self):
        try: self.image('logo.jpg', 10, 8, 30)
        except: pass
        self.set_font("Helvetica", "B", 16)
        self.cell(35)
        self.cell(0, 10, "ACCESORIOS DE ALUMINIO", ln=True)
        self.ln(10)

def generar_pdf_binario(cliente, carrito, total):
    pdf = PDF() 
    pdf.add_page()
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 7, f"Cliente: {cliente}", ln=True)
    pdf.cell(0, 7, f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "PRESUPUESTO", ln=True, align="C")
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 10)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.cell(100, 10, "Articulo", border=0)
    pdf.cell(20, 10, "Cant.", border=0, align="C")
    pdf.cell(35, 10, "P. Unit", border=0, align="R")
    pdf.cell(35, 10, "Subtotal", border=0, align="R")
    pdf.ln(10)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.set_font("Helvetica", "", 10)
    for item in carrito:
        pdf.cell(100, 8, str(item['Producto']), border=0)
        pdf.cell(20, 8, str(item['Cant']), border=0, align="C")
        pdf.cell(35, 8, f"$ {item['Precio U.']:,.2f}", border=0, align="R")
        pdf.cell(35, 8, f"$ {item['Subtotal']:,.2f}", border=0, align="R")
        pdf.ln(8)
    pdf.ln(5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
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
    menu = ["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre de Caja"]
    tabs = st.tabs(menu)

    with tabs[0]: # STOCK
        st.header("Inventario Actual")
        if not df_stock.empty:
            df_calc = df_stock.copy()
            for col in ["Stock", "Costo Base", "Lista 1 (Cheques)", "Lista 2 (Efectivo)"]:
                df_calc[col] = pd.to_numeric(df_calc[col], errors='coerce').fillna(0)
            c1, c2, c3 = st.columns(3)
            c1.metric("Valor Stock (Costo)", f"$ {(df_calc['Costo Base'] * df_calc['Stock']).sum():,.2f}")
            c2.metric("Total Lista 1", f"$ {(df_calc['Lista 1 (Cheques)'] * df_calc['Stock']).sum():,.2f}")
            c3.metric("Total Lista 2", f"$ {(df_calc['Lista 2 (Efectivo)'] * df_calc['Stock']).sum():,.2f}")
            st.divider()
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

    with tabs[1]: # LOTE
        st.header("🚚 Carga por Lote")
        df_lote_base = pd.DataFrame(columns=["articulo", "rubro", "cantidad", "costos", "flete", "articulo existente/nuevo"])
        st.data_editor(df_lote_base, num_rows="dynamic", use_container_width=True, key="ed_lote_full")

    with tabs[2]: # MAESTRO
        st.header("⚙️ Maestro de Artículos")
        df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True, key="ed_maestro_full")
        if st.button("Guardar Cambios Maestro"):
            df_ed.to_csv(ARCHIVO_ARTICULOS, index=False)
            st.success("¡Base de datos actualizada!")

    with tabs[3]: # CTA CTE - DIRECCIÓN AGREGADA
        st.header("👥 Gestión de Cuentas Corrientes")
        
        if not df_clientes.empty:
            cliente_seleccionado = st.selectbox("🔍 Buscar Cliente para ver Estado e Historial:", df_clientes["Nombre"].tolist(), key="busqueda_global_cli")
            
            idx_c = df_clientes[df_clientes["Nombre"] == cliente_seleccionado].index[0]
            saldo_raw = df_clientes.at[idx_c, "Saldo"]
            saldo_mostrable = 0.0 if abs(saldo_raw) < 1e-9 else saldo_raw
            
            # Mostrar datos del cliente seleccionado
            c_info1, c_info2, c_info3 = st.columns(3)
            c_info1.metric("Saldo Pendiente", f"$ {saldo_mostrable:,.2f}")
            c_info2.write(f"📞 **Tel:** {df_clientes.at[idx_c, 'Tel']}")
            c_info2.write(f"📍 **Localidad:** {df_clientes.at[idx_c, 'Localidad']}")
            c_info3.write(f"🏠 **Dirección:** {df_clientes.at[idx_c, 'Direccion']}")
            
            st.divider()
            
            col_movs, col_ops = st.columns([2, 1])
            
            with col_movs:
                st.subheader("Historial de Movimientos")
                hist = df_movs[df_movs["Cliente"] == cliente_seleccionado].sort_index(ascending=False)
                st.dataframe(hist, use_container_width=True, hide_index=True)
            
            with col_ops:
                st.subheader("Registrar Pago")
                monto_p = st.number_input("Monto a cobrar $:", min_value=0.0, key="m_p_oper")
                metodo_p = st.selectbox("Método:", ["Efectivo", "Transferencia", "Cheque"], key="met_p_oper")
                detalle_p = ""
                if metodo_p == "Cheque":
                    c_n = st.text_input("N° Cheque", key="c_n_oper")
                    c_b = st.text_input("Banco", key="c_b_oper")
                    c_v = st.date_input("Vencimiento", key="c_v_oper")
                    detalle_p = f"Cheque N°{c_n} - {c_b} (Vto: {c_v})"
                else:
                    detalle_p = st.text_input("Nota adicional:", key="nota_p_oper")
                
                if st.button("Confirmar Pago", key="btn_p_oper"):
                    if monto_p > 0:
                        df_clientes.at[idx_c, "Saldo"] -= monto_p
                        df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                        n_mov = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": cliente_seleccionado, "Tipo": "PAGO", "Monto": monto_p, "Metodo": metodo_p, "Detalle": detalle_p}])
                        pd.concat([df_movs, n_mov]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                        st.success("Pago registrado exitosamente.")
                        st.rerun()
                    else:
                        st.warning("El monto debe ser mayor a 0.")

        st.divider()
        st.subheader("Añadir Nuevo Cliente")
        with st.expander("Abrir formulario de alta"):
            c_n, c_t, c_l, c_d = st.columns(4)
            new_n = c_n.text_input("Nombre completo")
            new_t = c_t.text_input("Teléfono")
            new_l = c_l.text_input("Localidad")
            new_d = c_d.text_input("Dirección Exacta")
            if st.button("Dar de Alta"):
                if new_n:
                    # Guardamos incluyendo la nueva columna Dirección
                    nuevo_df = pd.DataFrame([[new_n, new_t, new_l, new_d, 0.0]], columns=COLS_CLIENTES)
                    pd.concat([df_clientes, nuevo_df], ignore_index=True).to_csv(ARCHIVO_CLIENTES, index=False)
                    st.success(f"Cliente {new_n} agregado."); st.rerun()

    with tabs[4]: # PRESUPUESTADOR
        st.header("📄 Generador de Presupuestos")
        cliente_p = st.selectbox("Cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"], key="cp_p")
        p1, p2, p3 = st.columns([2, 1, 1])
        with p1: i_p = st.selectbox("Artículo:", df_stock["Accesorio"].tolist(), key="ip_p")
        with p2: q_p = st.number_input("Cant:", min_value=1, value=1, key="qp_p")
        with p3: l_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"], key="lp_p")

        if st.button("Agregar", key="btn_add_p"):
            p_u = df_stock[df_stock["Accesorio"] == i_p][l_p].values[0]
            st.session_state.carrito.append({"Producto": i_p, "Cant": q_p, "Precio U.": p_u, "Subtotal": p_u * q_p})
            st.rerun()

        if st.session_state.carrito:
            df_car = pd.DataFrame(st.session_state.carrito)
            st.table(df_car)
            t_f = df_car["Subtotal"].sum()
            b1, b2, b3 = st.columns(3)
            with b1:
                pdf_d = generar_pdf_binario(cliente_p, st.session_state.carrito, t_f)
                st.download_button("📥 DESCARGAR PDF", pdf_d, f"Presupuesto_{cliente_p}.pdf", "application/pdf", use_container_width=True)
            with b2:
                if st.button("✅ ORDEN DE TRABAJO", use_container_width=True):
                    for item in st.session_state.carrito:
                        df_stock.loc[df_stock["Accesorio"] == item["Producto"], "Stock"] -= item["Cant"]
                    if cliente_p != "Consumidor Final":
                        idx_cp = df_clientes[df_clientes["Nombre"] == cliente_p].index[0]
                        df_clientes.at[idx_cp, "Saldo"] += t_f
                        df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                        n_v = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": cliente_p, "Tipo": "VENTA", "Monto": t_f, "Metodo": "-", "Detalle": f"Venta {len(st.session_state.carrito)} ítems"}])
                        pd.concat([df_movs, n_v]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                    df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                    st.session_state.carrito = []; st.success("Orden Procesada."); st.rerun()
            with b3:
                if st.button("🗑️ LIMPIAR", use_container_width=True): st.session_state.carrito = []; st.rerun()

    with tabs[5]: # ÓRDENES
        st.header("📋 Historial Global")
        st.dataframe(df_movs, use_container_width=True, hide_index=True)

    with tabs[6]: # CIERRE
        st.header("🏁 Cierre de Caja")
        c1, c2 = st.columns(2)
        v_s = (df_stock['Stock'] * pd.to_numeric(df_stock['Costo Base'], errors='coerce').fillna(0)).sum()
        c1.metric("Valor Stock (Costo)", f"$ {v_s:,.2f}")
        c2.metric("Total Deuda Clientes", f"$ {df_clientes['Saldo'].sum():,.2f}")
