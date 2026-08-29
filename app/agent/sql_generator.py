from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
)


def generate_sql(question: str, investigation_step: str) -> str:

    prompt = f"""
You are a SQL analyst for an operations investigation system.

User question:
{question}

Investigation step:
{investigation_step}

Available database tables:

warehouses:
- warehouse_id
- name
- region
- capacity

carriers:
- carrier_id
- name

orders:
- order_id
- warehouse_id
- region
- created_at
- promised_at

shipments:
- shipment_id
- order_id
- warehouse_id
- carrier_id
- shipped_at
- delivered_at

sla_events:
- event_id
- order_id
- warehouse_id
- event_type
- expected_time
- actual_time
- delay_minutes
- created_at

Generate ONE PostgreSQL SELECT query that answers the investigation step.

Rules:
- Only generate SELECT queries.
- Do not INSERT, UPDATE, DELETE, DROP, ALTER, or CREATE.
- Use only the tables and columns provided above.
- PostgreSQL has no ROUND(double precision, integer) overload. If you call
  ROUND() on an AVG(), SUM(), or other expression that may be a double
  precision value, cast it to numeric first, e.g. ROUND(AVG(x)::numeric, 2).
- Return ONLY the SQL query.
"""

    response = llm.invoke(prompt)

    content = response.content

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts = []

        for block in content:
            if isinstance(block, dict) and "text" in block:
                text_parts.append(block["text"])

        if text_parts:
            return "\n".join(text_parts).strip()

    raise ValueError(f"LLM returned unexpected content format: {type(content)}")