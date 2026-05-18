import os
import streamlit as st
import pandas as pd
from database.database_manager import DatabaseManager
from services.product_service import ProductService
from api_clients.gitec_client import GitecClient


def sync_inventory():
    """ბაზაში მონაცემების ჩაწერა (Write-Only)"""
    try:
        db = DatabaseManager()
        service = ProductService(db)

        data_path = "data/distributor_files/"
        if os.path.exists(data_path):
            service.import_all_from_folder(data_path)

        gitec = GitecClient()
        try:
            gitec_products = gitec.fetch_products()
            if gitec_products:
                service.import_gitec_products(gitec_products)
        except Exception as api_error:
            st.warning(f"GITEC API სინქრონიზაციის ხარვეზი: {api_error}")

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