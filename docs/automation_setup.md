# OPS-004: User Research Automation Workflow — Setup Guide

## Overview

This guide walks you through setting up the automated workflow to validate Phase 1 AI insights using real user research. The pipeline:

**Google Form → Zapier/n8n → Airtable/Sheets → Python Processor (Groq AI) → Insight Quality Score**

---

## Step 1: Create the Screening Form

### Google Form Fields

| Field Name | Type | Required | Options/Notes |
|------------|------|----------|---------------|
| Respondent ID | Short text | Yes | Auto-generated or email-based |
| Age Range | Dropdown | Yes | 18-24, 25-34, 35-44, 45+ |
| Primary Platform | Dropdown | Yes | Swiggy Instamart, Blinkit, Zepto, BigBasket, Other |
| Monthly Order Frequency | Dropdown | Yes | 1-3, 4-8, 9-15, 15+ |
| Categories Purchased | Checkboxes | Yes | Groceries, Snacks, Beverages, Household, Personal Care, Pet Supplies, Baby Products, Dairy, Packaged Food, Cleaning |
| Do you typically order the same items each time? | Linear Scale (1-5) | Yes | 1 = Always same, 5 = Always different |
| What prevents you from trying new categories? | Long text | Yes | Open-ended |
| How do you currently discover new products? | Checkboxes | Yes | App recommendations, Browsing, Word of mouth, Social media, Search, I don't discover new products |
| What would make you try a category you haven't bought before? | Long text | Yes | Open-ended |
| Describe a time you found a new product on a quick-commerce app. | Long text | No | Optional detailed response |

### Form Settings
- Collect email addresses (for follow-up screening)
- Limit to 1 response per person
- Show progress bar

---

## Step 2: Set Up the Tracker (Airtable or Google Sheets)

### Airtable Base: "Phase 1 Research Tracker"

| Column Name | Type | Notes |
|-------------|------|-------|
| Respondent ID | Single line text | Primary field |
| Submitted At | Date | Auto-filled on submission |
| Age Range | Single select | Matches form dropdown |
| Primary Platform | Single select | |
| Monthly Orders | Single select | |
| Categories Purchased | Multiple select | |
| Repetition Score | Number (1-5) | Linear scale response |
| Discovery Barriers | Long text | Open-ended response |
| Discovery Methods | Multiple select | |
| Trial Motivation | Long text | Open-ended response |
| Discovery Story | Long text | Optional response |
| AI Summary | Long text | Filled by processor |
| Matched Themes | Multiple select | Filled by processor |
| Quality Score | Number (0-100) | Filled by processor |
| Processing Status | Single select | Pending / Processed / Failed |

---

## Step 3: Configure Zapier Workflow

### Zap 1: Form → Tracker + Processor

**Trigger:** Google Forms — New Form Response

**Action 1:** Airtable — Create Record
- Map each form field to the corresponding Airtable column
- Set Processing Status = "Pending"

**Action 2:** Webhook by Zapier — POST
- URL: `https://your-server.com/webhook/process-survey`
- Payload Type: JSON
- Map the full form response as JSON body:
```json
{
  "respondent_id": "{{Respondent ID}}",
  "age_range": "{{Age Range}}",
  "primary_platform": "{{Primary Platform}}",
  "monthly_orders": "{{Monthly Order Frequency}}",
  "categories_purchased": "{{Categories Purchased}}",
  "repetition_score": "{{Do you typically order...}}",
  "discovery_barriers": "{{What prevents you...}}",
  "discovery_methods": "{{How do you currently discover...}}",
  "trial_motivation": "{{What would make you try...}}",
  "discovery_story": "{{Describe a time...}}"
}
```

**Action 3 (Optional):** Airtable — Update Record
- Update Processing Status = "Processed" after webhook returns 200

---

## Step 4: Alternative — n8n Workflow

If using n8n instead of Zapier:

1. **Trigger:** Google Forms Trigger node (poll interval: 5 min)
2. **Set Node:** Structure the data into the JSON schema above
3. **HTTP Request Node:** POST to the Python processor endpoint
4. **Airtable Node:** Create/update record with AI results

---

## Step 5: Python Processor

The `scripts/research_processor.py` script handles:
- Receiving the webhook JSON payload
- Sending survey responses to Groq AI for summarization
- Matching responses against Phase 1 themes (from `docs/ai_insights.md`)
- Generating an insight quality score (0-100)

### Running Locally (for testing)

```bash
# Process a single mock survey response
python scripts/research_processor.py --input database/mock_survey.json

# Process from stdin
echo '{"respondent_id":"TEST-001",...}' | python scripts/research_processor.py --stdin
```

### Running as a Webhook Server (for production)

```bash
# Start the Flask/FastAPI webhook listener
python scripts/research_processor.py --serve --port 8080
```

---

## Step 6: End-to-End Flow

1. User fills out Google Form
2. Zapier/n8n captures the response
3. Response is written to Airtable/Sheets tracker
4. Processor is triggered via webhook
5. Groq AI summarizes the response and matches themes
6. Quality score is calculated and written back to tracker
7. Researcher reviews responses with scores to validate AI insights

---

## Environment Variables Required

```
GROQ_API_KEY=gsk_...
```

Load from `.env` file in the project root.
