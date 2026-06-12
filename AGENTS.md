# AGENTS.md — Inventory Manager

ეს დოკუმენტი განკუთვნილია AI აგენტებისთვის, რომლებიც ამ რეპოზიტორიაზე მუშაობენ.

## პროექტის შეჯამება

Python/Streamlit აპლიკაცია კომპიუტერული ტექნიკის ინვენტარისა და ფასების მართვისთვის. მონაცემები მოდის:

- **Excel ფაილებიდან** — ERC, Oasis, VRTX (`data/distributor_files/`)
- **REST API-დან** — GITEC B2B
- **Storera Excel upload-ით** — მარაგების განახლება ე-კომერციისთვის

ყველა მონაცემი ინახება **SQLite** (`inventory.db`).

---

## Entry Points

| ფაილი | დანიშნულება | გაშვება |
|------|-------------|---------|
| `app.py` | Production — ავტორიზაცია, login/register | `streamlit run app.py` |
| `main.py` | Dev — ავტორიზაციის გარეშე | `streamlit run main.py` (მხოლოდ თუ `.env`-ში `ALLOW_DEV_NO_AUTH=true`) |

**არ გაუშვა** `python main.py` ან `python app.py` — Streamlit აპია, საჭიროა `streamlit run`.

Cursor Run/Debug: `.vscode/launch.json` — კონფიგურაციები `Streamlit Dev` / `Streamlit Production`.

---

## არქიტექტურა

```

Excel/API  →  Parser/Client  →  ProductService  →  DatabaseManager  →  inventory.db
                                                              ↓
Storera .xlsx upload  →  StoreraService  →  (მარაგის განახლება + changes report)
                                                              ↓
Streamlit UI  ←  load_inventory_df()  ←  fetch_products_dataframe()
```

### ფენები

| ფოლდერი | როლი |
|---------|------|
| `api_clients/` | გარე API (GITEC) |
| `parsers/` | Excel პარსინგი, `distributors.json` კონფიგი |
| `services/` | ბიზნეს ლოგიკა (`ProductService`, `StoreraService`) |
| `database/` | SQLite CRUD |
| `models/` | `Product` dataclass |
| `utils/` | `data_loader`, `logger` |
| `config/` | `distributors.json` — სვეტების mapping თითოეული მომწოდებლისთვის |
| `app.py` | UI ფუნქციები + production entry (`if __name__ == "__main__"`) |

### UI ფუნქციები (`app.py`)

- `render_inventory_ui(db)` — სინქრონიზაცია, ფილტრები, ცხრილი, CSV export
- `render_storera_ui(db)` — Storera Excel upload, მარაგის ოპტიმიზაცია, ცვლილებების რეპორტი

`main.py` იმპორტებს ამ ფუნქციებს `app.py`-დან. **`if __name__ == "__main__"` ბლოკი `app.py`-ში არ გაეშვება** იმპორტისას.

---

## მონაცემთა ნაკადი

### სინქრონიზაცია (`utils/data_loader.py`)

1. `sync_inventory()` — Excel ფოლდერი + GITEC API → ბაზაში ჩაწერა
2. `load_inventory_df()` — `@st.cache_data(ttl=600)` — ბაზიდან წაკითხვა

**Cache:** სინქრონიზაციის შემდეგ ყოველთვის გამოიძახე `load_inventory_df.clear()`.

### იმპორტი (`services/product_service.py`)

- დისტრიბუტორი განისაზღვრება ფაილის სახელით (`erc`, `oasis`, `vrtx`)
- იმპორტამდე: `delete_products_by_distributor(distributor)` — ძველი ჩანაწერების წაშლა
- შენახვამდე: `Product.validate()`

### Storera (`services/storera_service.py`)

- Storera Excel სვეტები: `სახელი`, `რაოდენობა`, `კატეგორია`, `აქტიური`
- PC build კატეგორიები **არ შეხება**: `სათამაშო/სარენდერო`, `პრემიალური`, `საოფისე`
- **ამჟამინდელი matching:** სახელის fuzzy + model code extraction (პრობლემატური — იხ. Roadmap)

---

## ბაზის schema

### `products`

| სვეტი | ტიპი | შენიშვნა |
|-------|------|---------|
| id | INTEGER PK | |
| brand | TEXT | |
| name | TEXT | |
| quantity | INTEGER | |
| price | REAL | |
| rrp_price | REAL | |
| category | TEXT | |
| distributor | TEXT | |

**Unique index:** `(name, distributor)`

UI-ში სვეტები ქართულად: `ბრენდი`, `დასახელება`, `რაოდენობა`, `ფასი (₾)`, `RRP ფასი`, `კატეგორია`, `მომწოდებელი`

### `users`

ავტორიზაცია `streamlit-authenticator`-ით. პაროლი bcrypt hash-ით (`$2...`).

---

## კონფიგურაცია

### `.env` (არ დაcommitო — `.gitignore`-შია)

| ცვლადი | აღწერა |
|--------|--------|
| `GITEC_USERNAME` / `GITEC_PASSWORD` | GITEC API |
| `AUTH_COOKIE_KEY` | მინ. 32 სიმბოლო — **აუცილებელი** `app.py`-სთვის |
| `ALLOW_REGISTRATION` | `true`/`false` — ღია რეგისტრაცია |
| `ALLOW_DEV_NO_AUTH` | `true` — Dev რეჟიმი `main.py`-სთვის |

შაბლონი: `.env.example`

### `config/distributors.json`

Excel სვეტების mapping: `name_col`, `brand_col`, `price_cols`, `quantity_col`, `category_col`, keywords/filters.

**ERC მაგალითი:** `Name`, `Brand`, `Model` (SKU — ჯერ არ ინახება ბაზაში, იხ. Roadmap), `Quantity`, `PROMO PRICE GEL`.

---

## უსაფრთხოება

- **არ დაcommitო:** `.env`, `inventory.db`, distributor Excel ფაილები ბიზნეს მონაცემებით
- **Production:** მხოლოდ `app.py`; `main.py` Dev-ისთვისაა
- **SQL:** მხოლოდ parameterized queries (`?`)
- **Storera upload:** max 10 MB (`STORERA_MAX_UPLOAD_BYTES`)
- **GITEC credentials:** HTTP headers-ში — არ ლოგავდე პაროლს

---

## კოდის სტაილი

- ენა: Python 3.10+
- UI ტექსტი და კომენტარები: **ქართული**
- Dataclass მოდელები (`models/`)
- ლოგირება: `from utils.logger import logger`
- Streamlit cache: `@st.cache_data` — clear sync-ის შემდეგ
- **მინიმალური diff** — არ refactor-ო უკავშირდებულის გარეშე
- **არ დაამატო** ზედმეტი abstraction, ზედმეტი ტესტები, ან დოკუმენტაცია, თუ მომხმარებელმა არ მოითხოვა

### ახალი მომწოდებლის დამატება

1. Excel ფაილი `data/distributor_files/` (სახელში: `erc`/`oasis`/`vrtx` ან `_detect_distributor`-ის გაფართოება)
2. `config/distributors.json`-ში ახალი ბლოკი
3. საჭიროების შემთხვევაში `ExcelParser._identify_category` ლოგიკის შემოწმება

---

## გაშვება და დამოკიდებულებები

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r Requirements.txt
copy .env.example .env
# დაარედაქტირე .env
streamlit run app.py
```

Dependencies: `Requirements.txt` (ფაილის სახელი capital R-ით).

---

## ცნობილი პრობლემები და Roadmap

### აქტუალური პრობლემა: Storera matching

Storera-სა და მომწოდებლებს შორის შედარება **სახელით** ხდება (`rapidfuzz`), რაც ხშირად არასწორ შედეგს იძლევა.

**დაგეგმილი გადაწყვეტა (პრიორიტეტი):**

1. `Product.sku` + DB სვეტი `sku`
2. ERC `Model` სვეტის იმპორტი (`distributors.json` → `model_col`)
3. Storera Excel-ში ხელით დამატებული `SKU` სვეტიდან exact match
4. დაუსმეჩებელი პროდუქტები → manual review queue (მარაგი **არ** იცვლება)
5. `sku_mappings` ცხრილი — Storera სახელი → SKU პერსისტენტური mapping
6. Best Price Dashboard — SKU-ზე მომწოდებლების შედარება

აგენტმა SKU-სთან დაკავშირებული ცვლილებები უნდა გააკეთოს ამ გეგმის მიხედვით, fuzzy name matching-ის წაშლით Storera stock update-ისთვის.

### სხვა roadmap (`readme.md`)

- Price Tracking (ფასის ისტორია)
- Best Price Report

---

## ფაილები რომლებსაც ეხება ცვლილებები

| ცვლილების ტიპი | ფაილები |
|----------------|---------|
| UI | `app.py`, `main.py` |
| Storera ლოგიკა | `services/storera_service.py` |
| იმპორტი | `services/product_service.py`, `parsers/excel_parser.py` |
| ბაზა | `database/database_manager.py`, `models/product.py` |
| API | `api_clients/gitec_client.py` |
| კონფიგი | `config/distributors.json`, `.env.example` |

---

## არ გააკეთო

- `python main.py` / `python app.py` როგორც ჩვეულებრივი სკრიპტის გაშვება
- `.env`, პაროლები, `inventory.db` commit
- Production-ში `ALLOW_DEV_NO_AUTH=true`
- UI კოდის დუბლირება `main.py` და `app.py` შორის — გამოიყენე `render_inventory_ui` / `render_storera_ui`
- Storera-ზე fuzzy name matching-ის დაბრუნება SKU ფაზის შემდეგ
- README/AGENTS.md ცვლილება, თუ მომხმარებელმა არ მოითხოვა

---

## სწრაფი დიაგნოსტიკა

| სიმპტომი | მიზეზი |
|----------|--------|
| Dev რეჟიმი გამორთულია | `.env`-ში არ არის `ALLOW_DEV_NO_AUTH=true` |
| AUTH_COOKIE_KEY შეცდომა | გასაღები < 32 სიმბოლო ან არ არსებობს |
| ცარიელი ბაზა sync-ის შემდეგ | Excel ფაილი არ არის `data/distributor_files/`-ში |
| ძველი მონაცემები UI-ში | cache — `load_inventory_df.clear()` ან sync ღილაკი |
| GITEC warning | credentials ან API ხელმიუწვდომელია |
