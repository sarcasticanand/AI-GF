import google.generativeai as genai

genai.configure(api_key="AIzaSyD3EziUkcLvitJ_mNXh5v6Z2tAchYOvNn8")

models = genai.list_models()

for model in models:
    print(model.name, model.supported_generation_methods)