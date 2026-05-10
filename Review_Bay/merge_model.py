from unsloth import FastLanguageModel
from transformers import AutoTokenizer

# Path to your adapter
adapter_path = r"C:\Users\L\.unsloth\studio\outputs\unsloth_Llama-3.1-8B-Instruct-unsloth-bnb-4bit_1775573282"

# Base model (same one you trained from)
base_model = "unsloth/Llama-3.1-8B-Instruct-unsloth-bnb-4bit"

# Load model + tokenizer
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = base_model,
    max_seq_length = 2048,
    dtype = None,
    load_in_4bit = True,
)

# Load your LoRA adapter
model.load_adapter(adapter_path)

# Merge and save to 16-bit
model.save_pretrained_merged(
    "C:/Users/L/merged_model",
    tokenizer,
    save_method = "merged_16bit",
)

print("✅ Merged model saved to C:/Users/L/merged_model")