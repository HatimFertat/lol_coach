from openai import OpenAI

client = OpenAI(
    api_key="LLAMA_API_KEY",
    base_url="https://api.llama.com/compat/v1/"
)

# Create chat completion request
completion = client.chat.completions.create(
    model="Llama-3.3-8B-Instruct",
    messages=[
        {
          "role": "developer",
          "content": "You are a helpful assistant."
        },
        {
          "role": "user",
          "content": "Hello!"
        }
    ],
)


# Please install OpenAI SDK first: `pip3 install openai`

from openai import OpenAI

client = OpenAI(api_key="<DeepSeek API Key>", base_url="https://api.deepseek.com")

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello"},
    ],
    stream=False
)


from openai import OpenAI

client = OpenAI(
    api_key="ANTHROPIC_API_KEY",  # Your Anthropic API key
    base_url="https://api.anthropic.com/v1/"  # Anthropic's API endpoint
)

response = client.chat.completions.create(
    model="claude-3-5-sonnet-20240620	", # Anthropic model name
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Who are you?"}
    ],
)

print(response.choices[0].message.content)


client = OpenAI(
    # This is the default and can be omitted
    api_key="OPENAI_API_KEY",
)

response = client.responses.create(
    model="gpt-4o",
    instructions="You are a coding assistant that talks like a pirate.",
    input="How do I check if a Python object is an instance of a class?",
)