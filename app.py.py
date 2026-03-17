import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re
import base64

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

# --- FUNCIÓN DE FORMATO PDF (SEGÚN TU MODELO) ---
def generar_html_presupuesto(cliente, carrito, total):
    # Formato de fecha exacto al modelo: 16/03/2026 15:24
    fecha_formateada = datetime.now().strftime("%d/%m/%Y %H:%M") [cite: 3]
    
    filas_tabla = ""
    for item in carrito:
        filas_tabla += f"""
        <tr>
            <td style="border: none; padding: 8px;">{item['Producto']}</td>
            <td style="border: none; padding: 8px; text-align: center;">{item['Cant']}</td>
            <td style="border: none; padding: 8px; text-align: right;">$ {item['Precio U.']:,.2f}</td>
            <td style="border: none; padding: 8px; text-align: right;">$ {item['Subtotal']:,.2f}</td>
        </tr>
        """
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Helvetica', sans-serif; padding: 40px; color: #000; }}
            .header {{ margin-bottom: 20px; }}
            .title-box {{ font-weight: bold; font-size: 24px; margin-bottom: 5px; }}
            .subtitle-box {{ font-size: 14px; margin-bottom: 30px; border-bottom: 1px solid #000; padding-bottom: 10px; }}
            .client-info {{ margin-bottom: 20px; font-size: 16px; }}
            .presu-label {{ font-weight: bold; font-size: 20px; text-align: center; margin-top: 30px; margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th {{ border-bottom: 2px solid #000; border-top: 2px solid #000; padding: 10px; text-align: left; background-color: #fff; }}
            .total-row {{ font-weight: bold; font-size: 18px; }}
            .total-label {{ text-align: right; padding-right: 20px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="title-box">ACCESORIOS DE ALUMINIO</div> 
        </div>
        
        <div class="client-info">
            <strong>Cliente:</strong> {cliente}<br> [cite: 2]
            <strong>Fecha:</strong> {fecha_formateada} [cite: 3]
        </div>

        <div class="presu-label">PRESUPUESTO</div> [cite: 4]

        <table>
            <thead>
                <tr>
                    <th style="text-align: left;">Articulo</th> 
                    <th style="text-align: center;">Cant.</th> 
                    <th style="text-align: right;">P. Unit</th> 
                    <th style="text-align: right;">Subtotal</th> 
                </tr>
            </thead>
            <tbody>
                {filas_tabla}
                <tr>
                    <td colspan="2" style="border-top: 2px solid #000;"></td>
                    <td class="total-label" style="border-top: 2px solid #000; padding: 10px;">TOTAL:</td> 
                    <td style="border-top: 2px solid #000; text-align: right; padding: 10px; font-weight: bold;">$ {total:,.2f}</td> 
                </tr>
            </tbody>
        </table>
    </body>
    </html>
    """
    return html

# --- LÓGICA DE INTERFAZ (RESTO DEL CÓDIGO INTACTO) ---

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
                l_tipo = st.radio("Condición:", ["Cheques", "Efectivo/Transf."], key=f"c_{idx}")
                p = row["Lista 1 (Cheques)"] if l_tipo == "Cheques" else row["Lista 2 (Efectivo)"]
                st.write(f"**$ {p:,.2f}**")
                c = st.number_input("Cantidad", 0, key=f"n_{idx}")
                if st.button("Pedir", key=f"b_{idx}"):
                    msg = f"Hola AF Accesorios! Quiero pedir {c} de {row['Accesorio']} ({l_tipo})."
                    st.markdown(f"[Confirmar en WhatsApp](https://wa.me/{WHATSAPP_NUM}?text={msg})")
else:
    menu = ["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre de Caja"]
    choice = st.tabs(menu)

    with choice[0]: # STOCK
        st.header("Inventario Actual")
        if not df_stock.empty:
            df_calc = df_stock.copy()
            for col in ["Stock", "Costo Base", "Lista 1 (Cheques)", "Lista 2 (Efectivo)"]:
                df_calc[col] = pd.to_numeric(df_calc[col], errors='coerce').fillna(0)
            total_costo = (df_calc["Costo Base"] * df_calc["Stock"]).sum()
            total_l1 = (df_calc["Lista 1 (Cheques)"] * df_calc["Stock"]).sum()
            total_l2 = (df_calc["Lista 2 (Efectivo)"] * df_calc["Stock"]).sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("Importe Stock (Costo)", f"$ {total_costo:,.2f}")
            c2.metric("Total Lista 1", f"$ {total_l1:,.2f}")
            c3.metric("Total Lista 2", f"$ {total_l2:,.2f}")
            st.divider()
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

    with choice[1]: # LOTE
        st.header("🚚 Carga por Lote")
        df_lote_base = pd.DataFrame(columns=["articulo", "rubro", "cantidad", "costos", "flete", "articulo existente/nuevo"])
        ed_lote = st.data_editor(df_lote_base, num_rows="dynamic", use_container_width=True)
        if st.button("Actualizar Stock"):
            st.success("Mercadería ingresada.")

    with choice[2]: # MAESTRO
        st.header("⚙️ Maestro de Artículos")
        df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True)
        if st.button("Guardar Cambios Maestro"):
            df_ed.to_csv(ARCHIVO_ARTICULOS, index=False)
            st.success("¡Base de datos actualizada!")

    with choice[3]: # CTA CTE
        st.header("👥 Gestión de Clientes")
        col_c1, col_c2 = st.columns([1, 2])
        with col_c1:
            st.subheader("Nuevo Cliente")
            n_cli = st.text_input("Nombre", key="n_cli_reg")
            t_cli = st.text_input("Teléfono", key="t_cli_reg")
            l_cli = st.text_input("Localidad", key="l_cli_reg")
            if st.button("Registrar Cliente"):
                nuevo = pd.DataFrame([[n_cli, t_cli, l_cli, 0.0]], columns=df_clientes.columns)
                pd.concat([df_clientes, nuevo]).to_csv(ARCHIVO_CLIENTES, index=False)
                st.rerun()
        with col_c2:
            st.subheader("Buscador de Saldos")
            if not df_clientes.empty:
                sel_cli = st.selectbox("Seleccionar Cliente:", df_clientes["Nombre"].tolist(), key="sel_cli_vista")
                saldo = df_clientes[df_clientes["Nombre"] == sel_cli]["Saldo"].values[0]
                st.metric(f"Saldo de {sel_cli}", f"$ {saldo:,.2f}")
                monto_pago = st.number_input("Registrar Pago/Entrega $:", min_value=0.0, key="pago_cli")
                if st.button("Confirmar Pago"):
                    df_clientes.loc[df_clientes["Nombre"] == sel_cli, "Saldo"] -= monto_pago
                    df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                    st.success("Saldo actualizado")
                    st.rerun()

    with choice[4]: # PRESUPUESTADOR (DISEÑO PDF ACTUALIZADO)
        st.header("📄 Generador de Presupuestos")
        cliente_p = st.selectbox("Seleccionar Cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"], key="cli_presu")
        st.divider()
        col_p1, col_p2, col_p3 = st.columns([2, 1, 1])
        with col_p1:
            item_p = st.selectbox("Seleccionar Artículo:", df_stock["Accesorio"].tolist(), key="item_presu")
        with col_p2:
            cant_p = st.number_input("Cant:", min_value=1, value=1, key="cant_presu")
        with col_p3:
            lista_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"], key="lista_presu")

        if st.button("Agregar al Presupuesto"):
            precio_u = df_stock[df_stock["Accesorio"] == item_p][lista_p].values[0]
            st.session_state.carrito.append({"Producto": item_p, "Cant": cant_p, "Precio U.": precio_u, "Subtotal": precio_u * cant_p})
            st.rerun()

        if st.session_state.carrito:
            df_car = pd.DataFrame(st.session_state.carrito)
            st.table(df_car)
            total = df_car["Subtotal"].sum()
            st.write(f"### TOTAL PARA {cliente_p}: $ {total:,.2f}")
            
            cp1, cp2, cp3 = st.columns(3)
            
            with cp1:
                html_res = generar_html_presupuesto(cliente_p, st.session_state.carrito, total)
                b64 = base64.b64encode(html_res.encode()).decode()
                href = f'<a href="data:text/html;base64,{b64}" download="presupuesto_{cliente_p}.html" style="text-decoration:none;"><button style="width:100%; height:40px; border-radius:5px; background-color:#F0F2F6; border:1px solid #dcdde1; cursor:pointer;">📥 Descargar Presupuesto</button></a>'
                st.markdown(href, unsafe_allow_html=True)

            with cp2:
                if st.button("✅ Confirmar Orden de Trabajo", use_container_width=True):
                    for item in st.session_state.carrito:
                        df_stock.loc[df_stock["Accesorio"] == item["Producto"], "Stock"] -= item["Cant"]
                    if cliente_p != "Consumidor Final":
                        df_clientes.loc[df_clientes["Nombre"] == cliente_p, "Saldo"] += total
                        df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                    df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                    nuevo_mov = pd.DataFrame([[datetime.now().strftime("%d/%m/%Y"), cliente_p, "VENTA", total, f"Venta de {len(st.session_state.carrito)} items"]], columns=df_movs.columns)
                    pd.concat([df_movs, nuevo_mov]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                    st.session_state.carrito = []
                    st.success("Orden Procesada.")
                    st.rerun()

            with cp3:
                if st.button("🗑️ Limpiar", use_container_width=True):
                    st.session_state.carrito = []
                    st.rerun()

    with choice[5]: # ÓRDENES
        st.header("📋 Órdenes de Trabajo")
        st.dataframe(df_movs, use_container_width=True)

    with choice[6]: # CIERRE DE CAJA
        st.header("🏁 Cierre de Caja")
        col_z1, col_z2 = st.columns(2)
        total_stock_c = (df_stock["Stock"] * df_stock["Costo Base"]).sum()
        total_deuda = df_clientes["Saldo"].sum()
        col_z1.metric("Valor del Stock (Costo)", f"$ {total_stock_c:,.2f}")
        col_z2.metric("Total Deuda Clientes", f"$ {total_deuda:,.2f}")
        st.subheader("Últimos Movimientos")
        st.dataframe(df_movs.tail(10), use_container_width=True)
