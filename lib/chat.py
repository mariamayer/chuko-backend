"""
AI Chatbot - FAQs and product recommendations.
"""

import os
from openai import OpenAI

from lib.shopify_products import fetch_products, products_to_context

SYSTEM_PROMPT = """Eres el asistente de merch7am, una tienda de merchandising personalizado (remeras, gorras, tazas, etc.) con impresión y bordado.

Tu rol:
1. Responder preguntas frecuentes sobre productos, pedidos mínimos, tiempos de entrega, métodos de pago, envíos, personalización, etc.
2. Recomendar productos según lo que el cliente busque (ej: "remeras para evento", "gorras con logo", "merchandising para empresa").

Reglas:
- Responde en español de forma amigable y concisa.
- Si preguntan por productos, usa el catálogo que te proporciono para recomendar opciones concretas con sus URLs.
- Si no tienes información, sugiere que contacten por email (hola@merch7am.com) o que soliciten un presupuesto en la web.
- No inventes precios ni productos que no estén en el catálogo.
"""


def chat(messages: list[dict], include_products: bool = True) -> str:
    """
    Send messages to the chatbot and get a response.
    messages: [{"role": "user"|"assistant"|"system", "content": "..."}]
    """
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    if not client.api_key:
        return "El asistente no está configurado. Por favor contacta a hola@merch7am.com."

    system = SYSTEM_PROMPT
    if include_products:
        products = fetch_products(limit=30)
        if products:
            system += f"\n\n--- Catálogo de productos actual ---\n{products_to_context(products)}\n\nUsa este catálogo para recomendar productos. Incluye el enlace cuando sea relevante."

    full_messages = [{"role": "system", "content": system}] + [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in messages
    ]

    try:
        response = client.chat.completions.create(
            model=os.environ.get("CHAT_MODEL", "gpt-4o-mini"),
            messages=full_messages,
            max_tokens=500,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as e:
        return f"Lo siento, hubo un error. Por favor intenta de nuevo o contacta a hola@merch7am.com. ({str(e)[:80]})"
