import streamlit as st
import pandas as pd
import os
from database.database_manager import DatabaseManager
from services.product_service import ProductService
from api_clients.gitec_client import GitecClient
from dotenv import load_dotenv

# ტვირთავს .env ფაილს (პაროლებისთვის)
load_dotenv()

# გვერდის კონფიგურაცია
st.set_page_config(page_title="Inventory Manager", layout="wide", page_icon="🖥️")

st.title("🖥️ კომპიუტერული ნაწილების ინვენტარი")
st.write("მონაცემების სინქრონიზაცია და ჩვენება (GITEC + Excel)")


@st.cache_data(ttl=600)  # მონაცემები განახლდება ყოველ 10 წუთში
def sync_and_load_data():
    """ამ ფუნქციას შემოაქვს მონაცემები ბაზაში და მერე კითხულობს მათ საჩვენებლად"""
    try:
        db = DatabaseManager()
        service = ProductService(db)

        # 1. Excel ფაილების იმპორტი (თუ საქაღალდე არსებობს)
        data_path = "data/distributor_files/"
        if os.path.exists(data_path):
            with st.spinner('Excel ფაილების იმპორტი ბაზაში...'):
                service.import_all_from_folder(data_path)

        # 2. GITEC API-დან წამოღება და ბაზაში შენახვა
        with st.spinner('GITEC API-სთან სინქრონიზაცია...'):
            gitec = GitecClient()
            gitec_prods = gitec.fetch_products()
            if gitec_prods:
                db.save_products(gitec_prods, "gitec")

        # 3. ყველა მონაცემის წამოღება ბაზიდან საჩვენებლად
        # ვიყენებთ შენს db მენეჯერს, რომ ყველაფერი ერთიანად წამოვიღოთ
        query = "SELECT category, name, price, quantity, distributor FROM products"
        # შენი DatabaseManager-ის მიხედვით, შეიძლება დაგჭირდეს db.execute_query ან მსგავსი
        # თუ db.get_all_products() არ გაქვს, გამოვიყენოთ SQLite-ის პირდაპირი წაკითხვა:
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        df = pd.read_sql_query(query, conn)
        conn.close()

        return df

    except Exception as e:
        st.error(f"შეცდომა მონაცემების დამუშავებისას: {e}")
        return pd.DataFrame()


# მონაცემების ჩატვირთვა
df = sync_and_load_data()

if df.empty:
    st.warning("ბაზა ცარიელია ან მოხდა შეცდომა ჩატვირთვისას.")
else:
    # სვეტების სახელების ქართულად გადარქმევა საჩვენებლად
    df.columns = ["კატეგორია", "დასახელება", "ფასი", "რაოდენობა", "მომწოდებელი"]

    # --- Sidebar ფილტრები ---
    st.sidebar.header("🔍 ფილტრაცია")

    distributors = st.sidebar.multiselect("მომწოდებელი:", df["მომწოდებელი"].unique(),
                                          default=df["მომწოდებელი"].unique())
    categories = st.sidebar.multiselect("კატეგორია:", df["კატეგორია"].unique(), default=df["კატეგორია"].unique())
    search_query = st.text_input("მოძებნე პროდუქტი:", "")

    # ფილტრაცია
    filtered_df = df[
        (df["მომწოდებელი"].isin(distributors)) &
        (df["კატეგორია"].isin(categories))
        ]

    if search_query:
        filtered_df = filtered_df[filtered_df["დასახელება"].str.contains(search_query, case=False, na=False)]

    # --- Metrics ---
    c1, c2, c3 = st.columns(3)
    c1.metric("ჯამური მოდელები", len(filtered_df))
    c2.metric("საშუალო ფასი", f"{round(filtered_df['ფასი'].mean(), 2)} ₾")
    c3.metric("საერთო მარაგი", int(filtered_df["რაოდენობა"].sum()))

    # --- ცხრილი ---
    st.subheader("ინვენტარის სრული სია")
    st.dataframe(
        filtered_df.sort_values(by="ფასი", ascending=False),
        use_container_width=True,
        hide_index=True
    )

    # ჩამოტვირთვის ღილაკი
    csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 ჩამოტვირთე სია (CSV)", csv, "inventory.csv", "text/csv")