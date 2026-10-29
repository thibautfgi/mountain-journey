import gradio as gr
from huggingface_hub import InferenceClient

MODEL_ID = "deepseek-ai/DeepSeek-V4.1-Flash-1017"
DEFAULT_SYSTEM = "You are a helpful assistant."


def respond(
        message: str,
        history: list[dict],
        system_message: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        hf_token: gr.OAuthToken | None = None,
):
    """Stream a reply from the model through Inference Providers."""
    if hf_token is None or not hf_token.token:
        yield "Please sign in with Hugging Face (button in the sidebar) to use the model."
        return

    client = InferenceClient(token=hf_token.token, model=MODEL_ID)

    messages = [{"role": "system", "content": system_message}]
    messages.extend({"role": m["role"], "content": m["content"]} for m in history)
    messages.append({"role": "user", "content": message})

    reply = ""
    try:
        for chunk in client.chat_completion(
                messages,
                max_tokens=max_tokens,
                stream=True,
                temperature=temperature,
                top_p=top_p,
        ):
            if not chunk.choices:
                continue
            reply += chunk.choices[0].delta.content or ""
            yield reply
    except Exception as err:  # surface provider errors (quota, auth, etc.) in the chat
        yield f"{reply}\n\n⚠️ Request failed: {err}"


chatbot = gr.ChatInterface(
    respond,
    additional_inputs=[
        gr.Textbox(value=DEFAULT_SYSTEM, label="System message"),
        gr.Slider(minimum=64, maximum=8192, value=2048, step=64, label="Max new tokens"),
        gr.Slider(minimum=0.0, maximum=2.0, value=1.0, step=0.05, label="Temperature"),
        gr.Slider(minimum=0.05, maximum=1.0, value=1.0, step=0.05, label="Top-p"),
    ],
    examples=[
        ["Explain KV cache compression in simple terms."],
        ["Write a Python function that merges overlapping intervals, with tests."],
        ["Give me a 3-day itinerary for hiking in Corsica."],
    ],
    cache_examples=False,
)

with gr.Blocks(title="DeepSeek-V4.1-Flash-1017") as demo:
    with gr.Sidebar():
        gr.Markdown(
            f"# 🐋 DeepSeek-V4.1-Flash-1017\n"
            f"Chat with [{MODEL_ID}](https://huggingface.co/{MODEL_ID}) "
            f"through Inference Providers.\n\n"
            f"Sampling defaults follow the model card (temperature 1.0, top-p 1.0)."
        )
        gr.LoginButton()
    chatbot.render()

if __name__ == "__main__":
    demo.launch()