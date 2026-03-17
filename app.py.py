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
            return df
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

df_stock = cargar_datos(ARCHIVO_ARTICULOS, ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"])
df_clientes = cargar_datos(ARCHIVO_CLIENTES, ["Nombre", "Tel", "Localidad", "Saldo"])
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, ["Fecha", "Cliente", "Tipo", "Monto", "Detalle"])

if "carrito" not in st.session_state:
    st.session_state.carrito = []

# --- FUNCIÓN CORREGIDA PARA EL PDF ---
def generar_pdf_binario(cliente, carrito, total):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Encabezado principal
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "ACCESORIOS DE ALUMINIO", ln=True)
    pdf.ln(5)
    
    # Datos de la transacción
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 7, f"Cliente: {cliente}", ln=True)
    pdf.cell(0, 7, f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    
    # Título central
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "PRESUPUESTO", ln=True, align="C")
    pdf.ln(5)
    
    # Tabla - Encabezados con líneas
    pdf.set_font("Helvetica", "B", 10)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.cell(100, 10, "Articulo", border=0)
    pdf.cell(20, 10, "Cant.", border=0, align="C")
    pdf.cell(35, 10, "P. Unit", border=0, align="R")
    pdf.cell(35, 10, "Subtotal", border=0, align="R")
    pdf.ln(10)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    
    # Tabla - Items
    pdf.set_font("Helvetica", "", 10)
    for item in carrito:
        pdf.cell(100, 8, str(item['Producto']), border=0)
        pdf.cell(20, 8, str(item['Cant']), border=0, align="C")
        pdf.cell(35, 8, f"$ {item['Precio U.']:,.2f}", border=0, align="R")
        pdf.cell(35, 8, f"$ {item['Subtotal']:,.2f}", border=0, align="R")
        pdf.ln(8)
    
    # Total Final
    pdf.ln(5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(120, 10, "", border=0)
    pdf.cell(35, 10, "TOTAL:", border=0, align="R")
    pdf.cell(35, 10, f"$ {total:,.2f}", border=0, align="R")
    
    # IMPORTANTE: Devolvemos los bytes del PDF para que Streamlit los maneje bien
    return pdf.output(dest='S').encode('latin-1')

# --- LÓGICA DE INTERFAZ ---
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
            total_costo = (df_calc["Costo Base"] * df_calc["Stock"]).sum()
            total_l1 = (df_calc["Lista 1 (Cheques)"] * df_calc["Stock"]).sum()
            total_l2 = (df_calc["Lista 2 (Efectivo)"] * df_calc["Stock"]).sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("Valor del Stock (Costo)", f"$ {total_costo:,.2f}")
            c2.metric("Total Lista 1", f"$ {total_l1:,.2f}")
            c3.metric("Total Lista 2", f"$ {total_l2:,.2f}")
            st.divider()
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

    with tabs[1]: # LOTE
        st.header("🚚 Carga por Lote")
        df_lote_base = pd.DataFrame(columns=["articulo", "rubro", "cantidad", "costos", "flete", "articulo existente/nuevo"])
        st.data_editor(df_lote_base, num_rows="dynamic", use_container_width=True, key="ed_lote_new")
        if st.button("Actualizar Stock", key="btn_lote_new"):
            st.success("Mercadería ingresada.")

    with tabs[2]: # MAESTRO
        st.header("⚙️ Maestro de Artículos")
        df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True, key="ed_maestro_new")
        if st.button("Guardar Cambios Maestro", key="btn_save_maestro_new"):
            df_ed.to_csv(ARCHIVO_ARTICULOS, index=False)
            st.success("¡Base de datos actualizada!")

    with tabs[3]: # CTA CTE
        st.header("👥 Gestión de Clientes")
        col_c1, col_c2 = st.columns([1, 2])
        with col_c1:
            st.subheader("Nuevo Cliente")
            n_cli = st.text_input("Nombre", key="reg_nom_n")
            t_cli = st.text_input("Teléfono", key="reg_tel_n")
            l_cli = st.text_input("Localidad", key="reg_loc_n")
            if st.button("Registrar Cliente", key="btn_reg_n"):
                nuevo = pd.DataFrame([[n_cli, t_cli, l_cli, 0.0]], columns=df_clientes.columns)
                pd.concat([df_clientes, nuevo]).to_csv(ARCHIVO_CLIENTES, index=False)
                st.rerun()
        with col_c2:
            st.subheader("Buscador de Saldos")
            if not df_clientes.empty:
                sel_cli = st.selectbox("Seleccionar Cliente:", df_clientes["Nombre"].tolist(), key="sel_cli_v_n")
                saldo = df_clientes[df_clientes["Nombre"] == sel_cli]["Saldo"].values[0]
                st.metric(f"Saldo de {sel_cli}", f"$ {saldo:,.2f}")
                monto_pago = st.number_input("Registrar Pago $:", min_value=0.0, key="pago_v_n")
                if st.button("Confirmar Pago", key="btn_pago_n"):
                    df_clientes.loc[df_clientes["Nombre"] == sel_cli, "Saldo"] -= monto_pago
                    df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                    st.rerun()

    with tabs[4]: # PRESUPUESTADOR
        st.header("📄 Generador de Presupuestos")
        cliente_p = st.selectbox("Seleccionar Cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"], key="cli_pres_n")
        st.divider()
        p1, p2, p3 = st.columns([2, 1, 1])
        with p1:
            item_p = st.selectbox("Seleccionar Artículo:", df_stock["Accesorio"].tolist(), key="item_pres_n")
        with p2:
            cant_p = st.number_input("Cant:", min_value=1, value=1, key="cant_pres_n")
        with p3:
            lista_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"], key="lista_pres_n")

        if st.button("Agregar al Presupuesto", key="btn_add_n"):
            precio_u = df_stock[df_stock["Accesorio"] == item_p][lista_p].values[0]
            st.session_state.carrito.append({"Producto": item_p, "Cant": cant_p, "Precio U.": precio_u, "Subtotal": precio_u * cant_p})
            st.rerun()

        if st.session_state.carrito:
            df_car = pd.DataFrame(st.session_state.carrito)
            st.table(df_car)
            total_fin = df_car["Subtotal"].sum()
            
            b1, b2, b3 = st.columns(3)
            with b1:
                # AQUÍ ESTÁ EL ARREGLO PARA EL PDF
                pdf_data = generar_pdf_binario(cliente_p, st.session_state.carrito, total_fin)
                st.download_button(
                    label="📥 DESCARGAR PDF",
                    data=pdf_data,
                    file_name=f"Presupuesto_{cliente_p}.pdf",
                    mime="application/pdf",
                    key="btn_pdf_final_new",
                    use_container_width=True
                )
            with b2:
                if st.button("✅ ORDEN DE TRABAJO", key="btn_ord_n", use_container_width=True):
                    for item in st.session_state.carrito:
                        df_stock.loc[df_stock["Accesorio"] == item["Producto"], "Stock"] -= item["Cant"]
                    if cliente_p != "Consumidor Final":
                        df_clientes.loc[df_clientes["Nombre"] == cliente_p, "Saldo"] += total_fin
                        df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                    df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                    st.session_state.carrito = []
                    st.success("Orden Procesada.")
                    st.rerun()
            with b3:
                if st.button("🗑️ LIMPIAR", key="btn_clr_n", use_container_width=True):
                    st.session_state.carrito = []
                    st.rerun()

    with tabs[5]: # ÓRDENES
        st.header("📋 Órdenes de Trabajo")
        st.dataframe(df_movs, use_container_width=True)

    with tabs[6]: # CIERRE DE CAJA
        st.header("🏁 Cierre de Caja")
        z1, z2 = st.columns(2)
        total_st = (df_stock["Stock"] * df_stock["Costo Base"]).sum()
        total_deu = df_clientes["Saldo"].sum()
        z1.metric("Valor del Stock (Costo)", f"$ {total_st:,.2f}")
        z2.metric("Total Deuda Clientes", f"$ {total_deu:,.2f}")
