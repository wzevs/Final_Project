import streamlit as st
from utils.data_loader import sync_inventory, load_inventory_df
from dotenv import load_dotenv

# 1. .env კონფიგურაციის ჩატვირთვა
load_dotenv()

# 2. გვერდის საწყისი პარამეტრები
st.set_page_config(page_title="Inventory Manager (Dev)", layout="wide", page_icon="🖥️")

st.title("🖥️ კომპიუტერული ნაწილების ინვენტარი")
st.write("მონაცემების სინქრონიზაცია და ჩვენება (GITEC + Excel)")

# 3. საწყისი ავტომატური სინქრონიზაცია (გაეშვება მხოლოდ სესიის დასაწყისში ერთხელ)
if 'initial_sync_done' not in st.session_state:
    with st.spinner("მიმდინარეობს საწყისი სინქრონიზაცია (Dev)..."):
        sync_inventory()
    st.session_state['initial_sync_done'] = True

# 4. --- Sidebar: ბაზის იძულებითი განახლების ღილაკი ---
st.sidebar.header("🔄 მონაცემთა ბაზა")
if st.sidebar.button("მონაცემების სინქრონიზაცია"):
    with st.spinner("მიმდინარეობს ბაზის განახლება..."):
        sync_inventory()
        st.cache_data.clear()
    st.success("ბაზა წარმატებით განახლდა!")
    st.rerun()

# 5. ჩატვირთვა დაქეშირებული მოდულიდან (Read-Only ოპერაცია, სადაც SQL უკვე დამალულია)
df = load_inventory_df()

if df.empty:
    st.warning("ბაზა ცარიელია ან მოხდა შეცდომა ჩატვირთვისას.")
else:
    # --- Sidebar ფილტრები ---
    st.sidebar.header("🔍 ფილტრაცია")

    distributors = st.sidebar.multiselect(
        "მომწოდებელი:",
        options=df["მომწოდებელი"].unique(),
        default=df["მომწოდებელი"].unique()
    )
    categories = st.sidebar.multiselect(
        "კატეგორია:",
        options=df["კატეგორია"].unique(),
        default=df["კატეგორია"].unique()
    )
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
    c2.metric("საშუალო ფასი", f"{round(filtered_df['ფასი (₾)'].mean(), 2) if not filtered_df.empty else 0} ₾")
    c3.metric("საერთო მარაგი", int(filtered_df["რაოდენობა"].sum()) if not filtered_df.empty else 0)

    # --- ცხრილი (შენი ახალი ვიზუალური პარამეტრებით) ---
    st.subheader("ინვენტარის სრული სია")
    st.dataframe(
        filtered_df.sort_values(by="ფასი (₾)", ascending=False),  # სორტირება ფასით
        use_container_width=True,
        hide_index=True  # ინდექსის დამალვა
    )

    # ჩამოტვირთვის ღილაკი
    csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 ჩამოტვირთე სია (CSV)", csv, "inventory.csv", "text/csv")