# PC Hardware Inventory & Storera Sync

Python/Streamlit აპლიკაცია კომპიუტერული ტექნიკის ინვენტარისთვის: მომწოდებლების ფასლისტების იმპორტი, ერთიანი SQLite ბაზა და Storera-ს ექსპორტის მარაგის სინქრონიზაცია.

## ძირითადი ფუნქციები

- **მრავალწყარო ინტეგრაცია:** Excel (ERC, Oasis, Yversy) + REST/SOAP API (VRTX, GITEC, Alta)
- **Streamlit UI:** ფასლისტების ნახვა/ფილტრაცია კატეგორიის ჯგუფებით; Storera ექსელის სინქრონიზაცია
- **SKU მეჩინგი:** `შიდა კოდი` ↔ მომწოდებლის SKU; `1C / FINA / FMG` ↔ VRTX `vrtx_code`
- **მარაგი და აქტიურობა:** Storera-ში `რაოდენობა` და `აქტიური` (0 მარაგი → არ ჩანს საიტზე, რჩება ადმინში)
- **კატეგორიის ჯგუფები:** ~13 ჯგუფი (`config/category_groups.json`) — UI-ში ჩართვა/გამორთვა
- **ავტორიზაცია:** `app.py` — `streamlit-authenticator`; `main.py` — dev რეჟიმი ავტორიზაციის გარეშე

## მომწოდებლები

| წყარო | ტიპი | კონფიგი / env |
|--------|------|----------------|
| ERC | Excel | `config/distributors.json` → `erc` |
| Oasis | Excel | `oasis` |
| Yversy | Excel | `yversy` (`default_category: Yversy`) |
| VRTX | API | `VRTX_API_TOKEN` (Excel გამოტოვებულია, თუ token არის) |
| GITEC | API | `GITEC_USERNAME`, `GITEC_PASSWORD` |
| Alta | SOAP API | `ALTA_USERNAME`, `ALTA_PASSWORD` |

ფაილები: `data/distributor_files/` — სახელში უნდა იყოს დისტრიბუტორის keyword (მაგ. `erc`, `oasis`, `yversy`).

## პროექტის სტრუქტურა

```text
├── api_clients/          # Alta, GITEC, VRTX კლიენტები
├── config/
│   ├── distributors.json # Excel პარსერის კონფიგი
│   └── category_groups.json
├── data/distributor_files/  # მომწოდებლების Excel (ლოკალურად)
├── database/             # SQLite (inventory.db)
├── models/                 # Product
├── parsers/                # ExcelParser
├── services/               # ProductService, StoreraService
├── utils/                  # data_loader, sku_utils, category_groups, logger
├── scripts/                # დიაგნოსტიკა (test_alta_api, compare_site_monitors...)
├── app.py                  # Production UI + ავტორიზაცია
├── main.py                 # Dev UI (ALLOW_DEV_NO_AUTH=true)
├── .env.example
└── Requirements.txt
```

## ინსტალაცია

**საჭიროა:** Python 3.10+

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r Requirements.txt
```

შექმენით `.env` ფაილი `.env.example`-ის მიხედვით (API credentials, `AUTH_COOKIE_KEY`, dev flag).

მოათავსეთ მომწოდებლების `.xlsx` ფაილები `data/distributor_files/`-ში.

## გაშვება

**Production (ავტორიზაციით):**

```bash
streamlit run app.py
```

**Dev (მხოლოდ ლოკალურად, ავტორიზაციის გარეშე):**

```bash
# .env: ALLOW_DEV_NO_AUTH=true
streamlit run main.py
```

## სინქრონიზაციის ნაკადი

### 1. მომწოდებლები → ბაზა

Sidebar → **„მონაცემების სინქრონიზაცია“** (ან პირველი გახსნისას ავტომატურად).

რიგი: Excel → VRTX API → GITEC API → Alta API. თითო მომწოდებელზე ბაზა სრულად იხლება და ხელახლა ივსება.

### 2. ბაზა → Storera

ტაბი **„Storera“** → ატვირთე Storera ექსპორტი → **„სინქრონიზაცია“** → ჩამოტვირთე `storera_synced.xlsx` → ატვირთე Storera-ში.

მეჩინგი თითო ხაზზე:

1. `1C / FINA / FMG` → VRTX `vrtx_code`
2. `შიდა კოდი` → მომწოდებლის SKU

გამოტოვებული კატეგორიები (PC build): `სათამაშო/სარენდერო`, `პრემიალური`, `საოფისე`.

**Storera ველების რეკომენდაცია:**

| ველი | შიგთავსი |
|------|----------|
| შიდა კოდი | მწარმოებლის SKU / მოდელი |
| 1C / FINA / FMG | VRTX კოდი (მაგ. `14086`) |

## Roadmap

- [ ] Best Price Dashboard — იგივე SKU-ზე მომწოდებლების შედარება
- [ ] Alta `item` fallback — `1C / FINA / FMG` ↔ Alta შიდა კოდი
- [ ] დაუსმეჩებელი პროდუქტების რიგი და SKU mapping მეხსიერება
- [ ] ფასის ისტორია
