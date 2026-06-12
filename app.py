import io
import os
import pandas as pd
import streamlit as st
import streamlit_authenticator as stauth
from database.database_manager import DatabaseManager
from dotenv import load_dotenv
from services.storera_service import StoreraService
from utils.category_groups import add_group_column, get_group_definitions
from utils.data_loader import load_inventory_df, sync_inventory

STORERA_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
WEAK_COOKIE_KEYS = {"", "fallback_secret_key_for_safety"}


def _is_registration_allowed() -> bool:
    return os.getenv("ALLOW_REGISTRATION", "false").lower() == "true"


def _get_cookie_signature_key() -> str | None:
    key = os.getenv("AUTH_COOKIE_KEY", "").strip()
    if key in WEAK_COOKIE_KEYS or len(key) < 32:
        return None
    return key


def _group_checkbox_key(group_label: str) -> str:
    return f"pricelist_group_{group_label}"


def _set_all_groups(group_labels: list[str], enabled: bool):
    for label in group_labels:
        st.session_state[_group_checkbox_key(label)] = enabled


def _render_distributor_summary(df: pd.DataFrame):
    distributors = sorted(df["მომწოდებელი"].unique())
    if not distributors:
        return
    cols = st.columns(min(len(distributors), 6))
    for idx, dist in enumerate(distributors):
        sub = df[df["მომწოდებელი"] == dist]
        in_stock = int((sub["რაოდენობა"] > 0).sum())
        cols[idx % len(cols)].metric(
            label=str(dist),
            value=len(sub),
            delta=f"მარაგში {in_stock}",
        )


def _detail_category_key(group_label: str, category: str) -> str:
    return f"pricelist_cat_{group_label}__{category}"


def _render_group_toggles(df: pd.DataFrame, distributor_filter: list) -> tuple[list[str], bool]:
    """ზედა დონის ჯგუფები + ოფციური დეტალური კატეგორიები."""
    sub = df[df["მომწოდებელი"].isin(distributor_filter)]
    if sub.empty:
        return [], False

    present_groups = sorted(sub["ჯგუფი"].dropna().astype(str).unique())
    icon_by_label = {g["label"]: g.get("icon", "") for g in get_group_definitions()}

    for label in present_groups:
        key = _group_checkbox_key(label)
        if key not in st.session_state:
            st.session_state[key] = True

    st.sidebar.markdown("##### 🏷️ ჯგუფები")
    btn1, btn2 = st.sidebar.columns(2)
    if btn1.button("ყველა ✓", key="groups_enable_all", use_container_width=True):
        _set_all_groups(present_groups, True)
        st.rerun()
    if btn2.button("გამორთ ✗", key="groups_disable_all", use_container_width=True):
        _set_all_groups(present_groups, False)
        st.rerun()

    enabled_groups: list[str] = []
    for label in present_groups:
        icon = icon_by_label.get(label, "")
        group_df = sub[sub["ჯგუფი"] == label]
        count = len(group_df)
        in_stock = int((group_df["რაოდენობა"] > 0).sum())
        checkbox_label = f"{icon} {label} — {count} ({in_stock} მარაგში)"
        if st.sidebar.checkbox(checkbox_label, key=_group_checkbox_key(label)):
            enabled_groups.append(label)

    detail_mode = st.sidebar.checkbox(
        "დეტალური კატეგორიები",
        value=False,
        key="pricelist_detail_categories",
        help="ჯგუფის ქვეშ ცალკეული კატეგორიების ჩართვა/გამორთვა",
    )

    if detail_mode and enabled_groups:
        st.sidebar.markdown("##### 📂 ქვეკატეგორიები")
        for label in present_groups:
            if label not in enabled_groups:
                continue
            group_df = sub[sub["ჯგუფი"] == label]
            cats = sorted(group_df["კატეგორია"].dropna().astype(str).unique())
            icon = icon_by_label.get(label, "")
            with st.sidebar.expander(f"{icon} {label}", expanded=False):
                for cat in cats:
                    key = _detail_category_key(label, cat)
                    if key not in st.session_state:
                        st.session_state[key] = True
                    cat_df = group_df[group_df["კატეგორია"] == cat]
                    count = len(cat_df)
                    in_stock = int((cat_df["რაოდენობა"] > 0).sum())
                    st.checkbox(f"{cat} — {count} ({in_stock})", key=key)

    return enabled_groups, detail_mode


def render_pricelist_ui(df: pd.DataFrame, filters_in_sidebar: bool = True):
    """ფასლისტის ნახვა: მომწოდებლები, ჯგუფების ჩექბოქსები, ძებნა, ცხრილი."""
    df = add_group_column(df)
    filter_container = st.sidebar if filters_in_sidebar else st

    if filters_in_sidebar:
        filter_container.markdown("##### 🔍 ფილტრები")

    all_distributors = sorted(df["მომწოდებელი"].unique())
    selected_distributors = filter_container.multiselect(
        "მომწოდებლები",
        options=all_distributors,
        default=all_distributors,
        key="pricelist_distributors",
    )

    if filters_in_sidebar:
        enabled_groups, detail_mode = _render_group_toggles(df, selected_distributors)
    else:
        enabled_groups = sorted(df["ჯგუფი"].unique())
        detail_mode = False

    search_query = st.text_input("🔎 ძებნა (სახელი / SKU)", "", key="pricelist_search")
    only_in_stock = st.checkbox("მხოლოდ მარაგში", value=False, key="pricelist_in_stock")

    mask = df["მომწოდებელი"].isin(selected_distributors)
    if enabled_groups:
        mask = mask & df["ჯგუფი"].isin(enabled_groups)
    if detail_mode and enabled_groups:
        detail_mask = pd.Series(False, index=df.index)
        for label in enabled_groups:
            group_df = df[df["ჯგუფი"] == label]
            for cat in group_df["კატეგორია"].dropna().astype(str).unique():
                if st.session_state.get(_detail_category_key(label, cat), True):
                    detail_mask |= (df["ჯგუფი"] == label) & (df["კატეგორია"] == cat)
        mask = mask & detail_mask
    if search_query:
        q = search_query.strip()
        mask = mask & (
            df["დასახელება"].str.contains(q, case=False, na=False)
            | df["SKU"].astype(str).str.contains(q, case=False, na=False)
        )
    if only_in_stock:
        mask = mask & (df["რაოდენობა"] > 0)

    filtered_df = df[mask].copy()

    st.caption(
        f"ნაჩვენებია **{len(filtered_df)}** / {len(df)} პროდუქტი · "
        f"მომწოდებლები: {', '.join(selected_distributors) if selected_distributors else '—'}"
    )
    _render_distributor_summary(filtered_df)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ნაჩვენები", len(filtered_df))
    c2.metric("მარაგში", int((filtered_df["რაოდენობა"] > 0).sum()) if not filtered_df.empty else 0)
    c3.metric(
        "საშუალო ფასი",
        f"{round(filtered_df['ფასი (₾)'].mean(), 2) if not filtered_df.empty else 0} ₾",
    )
    c4.metric("მარაგის ერთეული", int(filtered_df["რაოდენობა"].sum()) if not filtered_df.empty else 0)

    display_cols = [
        "მომწოდებელი", "ჯგუფი", "კატეგორია", "ბრენდი", "დასახელება", "SKU",
        "ფასი (₾)", "RRP ფასი", "რაოდენობა",
    ]
    show_df = filtered_df[[c for c in display_cols if c in filtered_df.columns]]
    st.dataframe(
        show_df.sort_values(by=["ჯგუფი", "მომწოდებელი", "კატეგორია", "ფასი (₾)"]),
        width="stretch",
        hide_index=True,
        height=520,
    )

    csv = filtered_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 ჩამოტვირთე ფილტრირებული სია (CSV)",
        csv,
        "pricelist_filtered.csv",
        "text/csv",
        key="pricelist_csv_download",
    )


def render_inventory_ui(db: DatabaseManager, filters_in_sidebar: bool = True):
    """ინვენტარის UI: სინქრონიზაცია + ფასლისტები / Storera ტაბები."""
    if "initial_sync_done" not in st.session_state:
        with st.spinner("მიმდინარეობს საწყისი სინქრონიზაცია..."):
            sync_inventory()
            load_inventory_df.clear()
        st.session_state["initial_sync_done"] = True

    st.sidebar.header("🔄 მონაცემთა ბაზა")
    if st.sidebar.button("მონაცემების სინქრონიზაცია", use_container_width=True):
        with st.spinner("მიმდინარეობს ბაზის განახლება..."):
            sync_inventory()
            load_inventory_df.clear()
        st.success("ბაზა წარმატებით განახლდა!")
        st.rerun()

    df = load_inventory_df()
    if df.empty:
        st.warning("მონაცემები ცარიელია. დააჭირეთ 'მონაცემების სინქრონიზაცია'-ს.")
        return

    tab_pricelist, tab_storera = st.tabs(["📦 ფასლისტები", "🛒 Storera"])

    with tab_pricelist:
        render_pricelist_ui(df, filters_in_sidebar=filters_in_sidebar)

    with tab_storera:
        render_storera_ui(db)


def _storera_excel_download(df: pd.DataFrame, file_name: str, button_key: str, label: str):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="პროდუქციის ჩამონათვალი")
    buffer.seek(0)
    st.download_button(
        label=label,
        data=buffer,
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=button_key,
    )


def render_storera_ui(db_manager: DatabaseManager):
    """Storera-ს ექსელის სინქრონიზაცია — მარაგი SKU-ით."""
    st.subheader("🔄 Storera სინქრონიზაცია")
    st.caption(
        "ატვირთე Storera-ს ექსპორტი (.xlsx). მარაგი: **1C / FINA / FMG ↔ VRTX**, "
        "შემდეგ **შიდა კოდი ↔ SKU**. მარაგი 0 → არააქტიური, >0 → აქტიური."
    )

    storera_file = st.file_uploader(
        "Storera ექსელის ფაილი (.xlsx)",
        type=["xlsx"],
        key="storera_global_excel_upload",
    )

    if storera_file is not None:
        try:
            if storera_file.size > STORERA_MAX_UPLOAD_BYTES:
                st.error(f"ფაილი ძალიან დიდია. მაქსიმუმი: {STORERA_MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
                return

            storera_input_df = pd.read_excel(storera_file)

            if st.button("სინქრონიზაცია", key="storera_sync_btn", type="primary"):
                storera_service = StoreraService(db_manager)

                with st.spinner("მარაგების სინქრონიზაცია..."):
                    final_df, changes_df, unmatched_df = storera_service.process_storera_feed(
                        storera_input_df
                    )

                st.success("სინქრონიზაცია დასრულდა.")

                if not changes_df.empty:
                    st.dataframe(changes_df, width="stretch", hide_index=True)
                else:
                    st.info("მარაგის ცვლილება არ მოხდა.")

                if unmatched_df is not None and not unmatched_df.empty:
                    with st.expander(f"დაუსმეჩებელი პროდუქტები ({len(unmatched_df)})"):
                        st.dataframe(unmatched_df, width="stretch", hide_index=True)

                _storera_excel_download(
                    final_df,
                    "storera_synced.xlsx",
                    "storera_global_download_btn",
                    "📥 ჩამოტვირთე განახლებული Excel",
                )
        except Exception as e:
            st.error(f"ფაილის დამუშავებისას მოხდა შეცდომა: {e}")


if __name__ == "__main__":
    load_dotenv()
    st.set_page_config(page_title="Inventory Manager", layout="wide", page_icon="🖥️")
    db = DatabaseManager()
    db.create_user_table()

    cookie_signature_key = _get_cookie_signature_key()
    if not cookie_signature_key:
        st.error(
            "AUTH_COOKIE_KEY არ არის დაყენებული ან სუსტია. "
            "დაამატეთ .env ფაილში მინიმუმ 32 სიმბოლოანი შემთხვევითი გასაღები."
        )
        st.stop()

    if "auth_mode" not in st.session_state:
        st.session_state["auth_mode"] = "login"

    def load_users_from_db():
        return db.get_all_users()

    if "credentials" not in st.session_state or st.session_state.get("reload_users"):
        st.session_state["credentials"] = load_users_from_db()
        st.session_state["reload_users"] = False

    authenticator = stauth.Authenticate(
        st.session_state["credentials"],
        "inventory_cookie",
        cookie_signature_key,
        cookie_expiry_days=30,
    )

    st.markdown(
        """
        <style>
        .main { background-color: #0e1117; }
        div[data-testid="stMetricValue"], div[data-testid="stMetricLabel"] {
            background-color: #1a1d24;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            border: 1px solid #36393f;
        }
        div[data-testid="stMetricValue"] { color: #ffffff !important; font-size: 2.5rem !important; font-weight: 700 !important; }
        div[data-testid="stMetricLabel"] { color: rgba(255, 255, 255, 0.8) !important; font-size: 1rem !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    authentication_status = st.session_state.get("authentication_status")

    if authentication_status:
        with st.sidebar:
            st.write(f"👋 მომხმარებელი: **{st.session_state['name']}**")
            authenticator.logout(location="sidebar")
            st.divider()

        st.title("🖥️ კომპიუტერული ნაწილების ინვენტარი")
        render_inventory_ui(db, filters_in_sidebar=True)

    else:
        if st.session_state["auth_mode"] == "login":
            authenticator.login(location="main")
            if st.session_state.get("authentication_status") is False:
                st.error("მომხმარებლის სახელი ან პაროლი არასწორია")
            elif st.session_state.get("authentication_status") is None:
                st.info("გთხოვთ შეიყვანოთ მონაცემები სისტემაში შესასვლელად")

            if _is_registration_allowed():
                st.write("")
                st.write("ჯერ არ გაქვთ სისტემის ანგარიში?")
                if st.button("📝 ახალი მომხმარებლის რეგისტრაცია"):
                    st.session_state["auth_mode"] = "register"
                    st.rerun()

        elif st.session_state["auth_mode"] == "register":
            if not _is_registration_allowed():
                st.session_state["auth_mode"] = "login"
                st.rerun()

            st.title("📝 ახალი მომხმარებლის რეგისტრაცია")
            try:
                if authenticator.register_user(location="main"):
                    db_usernames = db.get_all_usernames()
                    current_users = st.session_state["credentials"].get("usernames", {})

                    for u_name, u_data in current_users.items():
                        if u_name not in db_usernames:
                            u_email = u_data.get("email", "")
                            u_name_real = u_data.get("name", u_name)
                            u_pass = u_data.get("password", "")

                            if not u_pass.startswith("$2"):
                                st.error("პაროლის ჰეშირება ვერ მოხერხდა. სცადეთ თავიდან.")
                                st.stop()

                            db.add_user(u_name, u_pass, u_email, u_name_real)
                            st.success("რეგისტრაცია წარმატებულია! გადადით ავტორიზაციის გვერდზე.")
                            st.session_state["reload_users"] = True
                            st.session_state["auth_mode"] = "login"
                            st.rerun()
            except Exception as e:
                st.error(f"რეგისტრაციის შეცდომა: {e}")

            st.write("")
            if st.button("🔙 უკვე გაქვთ ანგარიში? ავტორიზაციის გვერდი"):
                st.session_state["auth_mode"] = "login"
                st.rerun()
