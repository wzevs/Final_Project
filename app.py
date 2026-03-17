import streamlit as st
import pandas as pd
import os
import sqlite3
from database.database_manager import DatabaseManager
from services.product_service import ProductService
from api_clients.gitec_client import GitecClient
from dotenv import load_dotenv

# ტვირთავს .env ფაილს
load_dotenv()

# გვერდის კონფიგურაცია
st.set_page_config(page_title="Inventory Manager", layout="wide", page_icon="🖥️")

# სტილის დამატება
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🖥️ კომპიუტერული ნაწილების ინვენტარი")
st.write("მონაცემები GITEC API-დან და ლოკალური Excel ფაილებიდან (ბაზის გავლით)")


@st.cache_data(ttl=600)  # მონაცემები ინახება 10 წუთით
def load_and_sync_data():
    try:
        # 1. ინიციალიზაცია
        db = DatabaseManager()
        # გადავცემთ db_manager-ს, როგორც ამას ProductService-ის __init__ ითხოვს
        service = ProductService(db_manager=db)

        # 2. Excel ფაილების იმპორტი
        data_path = "data/distributor_files/"
        if os.path.exists(data_path):
            with st.spinner('Excel ფაილების სინქრონიზაცია...'):
                service.import_all_from_folder(data_path)

        # 3. GITEC API სინქრონიზაცია
        with st.spinner('GITEC API სინქრონიზაცია...'):
            gitec = GitecClient()
            gitec_prods = gitec.fetch_products()
            if gitec_prods:
                db.save_products(gitec_prods, "gitec")

        # 4. მონაცემების წამოღება ბაზიდან
        # ვიყენებთ SQLite-ს პირდაპირ წასაკითხად DataFrame-ში
        conn = sqlite3.connect(db.db_path)
        query = "SELECT distributor, name, category, price, quantity FROM products"
        df_result = pd.read_sql_query(query, conn)
        conn.close()

        # სვეტების ქართულად გადარქმევა
        df_result.columns = ["მომწოდებელი", "დასახელება", "კატეგორია", "ფასი (₾)", "რაოდენობა"]
        return df_result

    except Exception as e:
        st.error(f"კრიტიკული შეცდომა მონაცემების დამუშავებისას: {e}")
        return pd.DataFrame()


# მონაცემების ჩატვირთვა
df = load_and_sync_data()

if df.empty:
    st.warning("მონაცემები ვერ მოიძებნა. შეამოწმეთ API, ფაილები და მონაცემთა ბაზა.")
else:
    # --- Sidebar ფილტრები ---
    st.sidebar.header("🔍 ფილტრაცია")

    selected_brand = st.sidebar.multiselect(
        "მომწოდებელი:",
        options=df["მომწოდებელი"].unique(),
        default=df["მომწოდებელი"].unique()
    )

    selected_cat = st.sidebar.multiselect(
        "კატეგორია:",
        options=df["კატეგორია"].unique(),
        default=df["კატეგორია"].unique()
    )

    search_query = st.text_input("მოძებნე პროდუქტი დასახელების მიხედვით:", "")

    # ფილტრაციის გამოყენება
    mask = (df["მომწოდებელი"].isin(selected_brand)) & \
           (df["კატეგორია"].isin(selected_cat))

    if search_query:
        mask = mask & (df["დასახელება"].str.contains(search_query, case=False, na=False))

    filtered_df = df[mask]

    # --- Metrics (სტატისტიკა) ---
    c1, c2, c3 = st.columns(3)
    c1.metric("სულ დასახელება", len(filtered_df))
    c2.metric("საშუალო ფასი", f"{round(filtered_df['ფასი (₾)'].mean(), 2) if not filtered_df.empty else 0} ₾")
    c3.metric("მარაგი ჯამში", int(filtered_df["რაოდენობა"].sum()))

    # --- მთავარი ცხრილი ---
    st.subheader("პროდუქტების სია")
    st.dataframe(
        filtered_df.sort_values(by="ფასი (₾)", ascending=True),
        width="stretch",  # აქ ჩავასწორე Warning-ის მიხედვით
        hide_index=True
    )

    # --- ჩამოტვირთვის ღილაკი ---
    csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 ჩამოტვირთე სია CSV ფორმატში",
        data=csv,
        file_name='inventory_report.csv',
        mime='text/csv',
    )