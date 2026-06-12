import os
import streamlit as st
import pandas as pd
from database.database_manager import DatabaseManager
from services.product_service import ProductService
from api_clients.alta_client import AltaClient
from api_clients.gitec_client import GitecClient
from api_clients.vrtx_client import VrtxClient


def sync_inventory():
    """ბაზაში მონაცემების ჩაწერა (Write-Only)"""
    try:
        db = DatabaseManager()
        service = ProductService(db)

        skip_excel = set()
        if os.getenv("VRTX_API_TOKEN", "").strip():
            skip_excel.add("vrtx")

        data_path = "data/distributor_files/"
        if os.path.exists(data_path):
            service.import_all_from_folder(data_path, skip_distributors=skip_excel)

        if os.getenv("VRTX_API_TOKEN", "").strip():
            try:
                vrtx = VrtxClient()
                vrtx_products = vrtx.fetch_products()
                if vrtx_products:
                    service.import_vrtx_products(vrtx_products)
            except Exception as api_error:
                st.warning(f"VRTX API სინქრონიზაციის ხარვეზი: {api_error}")

        gitec = GitecClient()
        try:
            gitec_products = gitec.fetch_products()
            if gitec_products:
                service.import_gitec_products(gitec_products)
        except Exception as api_error:
            st.warning(f"GITEC API სინქრონიზაციის ხარვეზი: {api_error}")

        if os.getenv("ALTA_USERNAME") and os.getenv("ALTA_PASSWORD"):
            try:
                alta = AltaClient()
                alta_products = alta.fetch_products()
                if alta_products:
                    service.import_alta_products(alta_products)
            except Exception as api_error:
                st.warning(f"Alta API სინქრონიზაციის ხარვეზი: {api_error}")

    except Exception as e:
        st.error(f"სინქრონიზაციის შეცდომა: {e}")


@st.cache_data(ttl=600)
def load_inventory_df():
    """ბაზიდან მონაცემების წაკითხვა (Read-Only)"""
    try:
        db = DatabaseManager()
        # 🚀 პირდაპირ ვიღებთ ბაზიდან უკვე დაფორმატებულ, 7-სვეტიან მზა DataFrame-ს
        df_raw = db.fetch_products_dataframe()

        if df_raw.empty:
            return pd.DataFrame()

        return df_raw
    except Exception as e:
        st.error(f"ბაზიდან მონაცემების წაკითხვის შეცდომა: {e}")
        return pd.DataFrame()