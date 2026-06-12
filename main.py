import os

import streamlit as st
from dotenv import load_dotenv

from app import render_inventory_ui
from database.database_manager import DatabaseManager

load_dotenv()

if os.getenv("ALLOW_DEV_NO_AUTH", "false").lower() != "true":
    st.set_page_config(page_title="Inventory Manager (Dev)", layout="wide", page_icon="🖥️")
    st.error("Dev რეჟიმი გამორთულია. Production-ისთვის გამოიყენეთ: streamlit run app.py")
    st.info("ლოკალური განვითარებისთვის დაამატეთ .env ფაილში: ALLOW_DEV_NO_AUTH=true")
    st.stop()

db = DatabaseManager()

st.set_page_config(page_title="Inventory Manager (Dev)", layout="wide", page_icon="🖥️")

st.title("🖥️ კომპიუტერული ნაწილების ინვენტარი (Dev ვერსია)")
st.warning("⚠️ Dev რეჟიმი — ავტორიზაცია გამორთულია. Production-ში გამოიყენეთ app.py.")

render_inventory_ui(db, filters_in_sidebar=True)
