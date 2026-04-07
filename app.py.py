import streamlit as st
import pandas as pd
import os

st.title("Prueba de Conexión AF")
st.write("Si ves esto, el servidor funciona correctamente.")

# Verificar carpeta de datos
if os.path.exists("/app/data"):
    st.success("La carpeta de datos está vinculada correctamente.")
else:
    st.warning("No se detecta la carpeta /app/data. Revisá los Volumes en Railway.")

st.info(f"El archivo se está ejecutando como: {__file__}")
