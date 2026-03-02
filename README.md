# merch7am Price Estimator API

AI-powered price estimation for custom merchandise. Analyzes uploaded design images (logo size, color count) and applies pricing rules.

**Stack:** Python 3.11+, FastAPI, OpenAI

## Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

## Run

```bash
uvicorn main:app --reload --port 3001   # Development
uvicorn main:app --port 3001           # Production
```

Server runs at `http://localhost:3001` by default.

- **Docs:** http://localhost:3001/docs
- **Health:** http://localhost:3001/api/health

## API

### `POST /api/estimate-price`

**Request body:**
```json
{
  "quantity": 50,
  "size": "M",
  "color": "Black",
  "front_design": "data:image/png;base64,...",
  "back_design": "data:image/png;base64,...",
  "no_designs": false,
  "base_price_cents": 1500
}
```

**Response:**
```json
{
  "estimate": 1250.00,
  "estimate_id": "EST-20240225-0001",
  "total_cents": 125000,
  "currency": "USD",
  "breakdown": { ... },
  "analysis": { "front": {...}, "back": {...} }
}
```

### Saving estimates

When `client_name` and/or `client_email` are sent:

1. **Storage** – Estimate is saved to `data/estimates/` as JSON (e.g. `EST-20240225-0001.json`)
2. **Emails** – If `RESEND_API_KEY` and `ADMIN_EMAIL` are set:
   - Admin receives full details (price, product, quantity, logo analysis, client info)
   - Client receives a summary with their quote ID

## Dummy Pricing Rules

Currently in `lib/pricing.py`:

| Factor | Values |
|--------|--------|
| Base price | $15.00 (1500 cents) |
| Logo size | small 1.0x, medium 1.2x, large 1.5x, full 2.0x |
| Per extra color | $0.50 |
| Quantity 50+ | 5% off |
| Quantity 100+ | 10% off |

Replace these with your real rules when ready.

## Without OpenAI Key

If `OPENAI_API_KEY` is not set, the API uses dummy image analysis (medium/small logo, 2/1 colors) so you can test the flow without Vision API costs.

## Company report (every 2 weeks)

Sends an email with all companies that created estimates.

**Setup:** Add to `.env`:
```
REPORT_EMAIL=your-email@merch7am.com
REPORT_TOKEN=some-secret-string
```

**Option 1 – Cron job** (run script every 14 days):
```bash
# Example: 1st and 15th of each month at 9am
0 9 1,15 * * cd /path/to/merch-ai/backend && python -m scripts.send_company_report
```

**Option 2 – HTTP trigger** (e.g. cron-job.org, GitHub Actions):
```
GET https://your-api.com/api/reports/companies?token=YOUR_REPORT_TOKEN
```

## Chatbot (FAQs + product recommendations)

AI assistant that answers FAQs and recommends products.

**Endpoint:** `POST /api/chat`

**Request:**
```json
{
  "messages": [
    {"role": "user", "content": "¿Qué remeras tienen para eventos?"}
  ],
  "include_products": true
}
```

**Response:**
```json
{
  "reply": "Tenemos varias opciones de remeras... [con enlaces a productos]"
}
```

**Setup:** Uses `OPENAI_API_KEY`. For product recommendations, add:
- `SHOPIFY_STORE_DOMAIN` – e.g. merch7am.myshopify.com
- `SHOPIFY_STOREFRONT_TOKEN` – Storefront API token (Shopify Admin > Apps > Develop apps)
- `SHOPIFY_STORE_URL` – (optional) https://merch7am.com for product links

## Deploy to AWS

See [docs/DEPLOY-AWS.md](docs/DEPLOY-AWS.md) for:
- **App Runner** – connect GitHub, deploy in minutes
- **ECS Fargate** – Docker + ECR, industry standard
