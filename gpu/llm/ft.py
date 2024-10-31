import argparse
import os
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    HfArgumentParser,
    TrainingArguments,
    pipeline,
    logging,
)
from peft import LoraConfig, PeftModel
from trl import SFTTrainer

import logging
import warnings
warnings.filterwarnings("ignore")

logging.basicConfig(
    level=logging.INFO,                # Set the minimum log level to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Customize format
    handlers=[
        logging.FileHandler("app.log"), # Logs to a file
        logging.StreamHandler()         # Logs to the console
    ]
)
logger = logging.getLogger("LOGGER")


def finetuning(args):
    os.environ['TRANSFORMERS_NO_ADVISORY_WARNINGS'] = 'true'
    # The model that you want to train
    # module is downloaded from hugging face: "NousResearch/Llama-2-7b-chat-hf"
    model_path = args.original_model

    # The instruction dataset to use
    # dataset is downloaded frm hugging face: "mlabonne/guanaco-llama2-1k"
    dataset_path = args.training_dataset

    # adapter model generated after training
    adapter_model_path = args.original_model + "/generate-adapter"

    # The merged new model after training
    new_model_path = args.output_model

    ################################################################################
    # QLoRA parameters
    ################################################################################

    # LoRA attention dimension
    lora_r = 64

    # Alpha parameter for LoRA scaling
    lora_alpha = 16

    # Dropout probability for LoRA layers
    lora_dropout = 0.1

    ################################################################################
    # bitsandbytes parameters
    ################################################################################

    # Activate 4-bit precision base model loading
    use_4bit = True

    # Compute dtype for 4-bit base models
    bnb_4bit_compute_dtype = "float16"

    # Quantization type (fp4 or nf4)
    bnb_4bit_quant_type = "nf4"

    # Activate nested quantization for 4-bit base models (double quantization)
    use_nested_quant = False

    ################################################################################
    # TrainingArguments parameters
    ################################################################################

    # Output directory where the model predictions and checkpoints will be stored
    output_dir = "./results"

    # Number of training epochs
    num_train_epochs = 1

    # Enable fp16/bf16 training (set bf16 to True with an A100)
    fp16 = False
    bf16 = True

    # Batch size per GPU for training
    per_device_train_batch_size = 4

    # Batch size per GPU for evaluation
    per_device_eval_batch_size = 4

    # Number of update steps to accumulate the gradients for
    gradient_accumulation_steps = 1

    # Enable gradient checkpointing
    gradient_checkpointing = True

    # Maximum gradient normal (gradient clipping)
    max_grad_norm = 0.3

    # Initial learning rate (AdamW optimizer)
    learning_rate = 2e-4

    # Weight decay to apply to all layers except bias/LayerNorm weights
    weight_decay = 0.001

    # Optimizer to use
    optim = "paged_adamw_32bit"

    # Learning rate schedule
    lr_scheduler_type = "cosine"

    # Number of training steps (overrides num_train_epochs)
    max_steps = -1

    # Ratio of steps for a linear warmup (from 0 to learning rate)
    warmup_ratio = 0.03

    # Group sequences into batches with same length
    # Saves memory and speeds up training considerably
    group_by_length = True

    # Save checkpoint every X updates steps
    save_steps = 0

    # Log every X updates steps
    logging_steps = 25

    ################################################################################
    # SFT parameters
    ################################################################################

    # Maximum sequence length to use
    max_seq_length = None

    # Pack multiple short examples in the same input sequence to increase efficiency
    packing = False

    # Load the entire model on the GPU 0
    device_map = {"": 0}

    # Load dataset (you can process it here)
    dataset_file_path = ""
    # temporally hard code, assuming only one data file with parquet format in the folder.
    for root, dirs, files in os.walk(dataset_path):
        dataset_file_path = os.path.join(root, files[0])
    dataset = load_dataset("parquet", data_files=dataset_file_path, split="train")
    logger.info("Loading dataset from {}".format(dataset_file_path))

    # Load tokenizer and model with QLoRA configuration
    compute_dtype = getattr(torch, bnb_4bit_compute_dtype)

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=use_4bit,
        bnb_4bit_quant_type=bnb_4bit_quant_type,
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=use_nested_quant,
    )

    # Check GPU compatibility with bfloat16
    # if compute_dtype == torch.float16 and use_4bit:
    #     major, _ = torch.cuda.get_device_capability()
    #     if major >= 8:
    #         print("=" * 80)
    #         print("Your GPU supports bfloat16: accelerate training with bf16=True")
    #         print("=" * 80)

    logger.info("Loading model from {}".format(model_path))
    # Load base model
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        quantization_config=bnb_config,
        device_map=device_map
    )
    model.config.use_cache = False
    model.config.pretraining_tp = 1

    # Load LLaMA tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"  # Fix weird overflow issue with fp16 training

    # Load LoRA configuration
    peft_config = LoraConfig(
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        r=lora_r,
        bias="none",
        task_type="CAUSAL_LM",
    )

    # Run text generation pipeline with our current model
    print("=" * 80)
    print("Testing with current model")
    print("=" * 80)
    prompt = "请用中文回答你会如何准备一场面试?"
    pipe = pipeline(task="text-generation", model=model, tokenizer=tokenizer, max_length=200)
    result = pipe(f"<s>[INST] {prompt} [/INST]")
    print(result[0]['generated_text'])
    print("=" * 80)
    prompt = "请用中文回答哪个星球有外星人?"
    pipe = pipeline(task="text-generation", model=model, tokenizer=tokenizer, max_length=200)
    result = pipe(f"<s>[INST] {prompt} [/INST]")
    print(result[0]['generated_text'])
    print("=" * 80)
    print("Testing done")
    print("=" * 80)

    logger.info("Preparing training parameters")
    # Set training parameters
    training_arguments = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_train_epochs,
        per_device_train_batch_size=per_device_train_batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        optim=optim,
        save_steps=save_steps,
        logging_steps=logging_steps,
        learning_rate=learning_rate,
        weight_decay=weight_decay,
        fp16=fp16,
        bf16=bf16,
        max_grad_norm=max_grad_norm,
        max_steps=max_steps,
        warmup_ratio=warmup_ratio,
        group_by_length=group_by_length,
        lr_scheduler_type=lr_scheduler_type,
        report_to=[]
    )

    logger.info("Preparing trainer")
    # Set supervised fine-tuning parameters
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        peft_config=peft_config,
        dataset_text_field="text",
        max_seq_length=max_seq_length,
        tokenizer=tokenizer,
        args=training_arguments,
        packing=packing,
    )

    logger.info("Start to train")
    # Train model
    trainer.train()
    logger.info("Training is completed")
    logger.info("Saving the adapter model to {}".format(adapter_model_path))
    # Save trained model
    trainer.model.save_pretrained(adapter_model_path)
    trainer.tokenizer.save_pretrained(adapter_model_path)

    print("=" * 80)
    print("Re-testing with the fine tuned model")
    print("=" * 80)
    prompt = "请用中文回答你会如何准备一场面试?"
    pipe = pipeline(task="text-generation", model=model, tokenizer=tokenizer, max_length=200)
    result = pipe(f"<s>[INST] {prompt} [/INST]")
    print(result[0]['generated_text'])
    print("=" * 80)
    prompt = "请用中文回答哪个星球有外星人?"
    pipe = pipeline(task="text-generation", model=model, tokenizer=tokenizer, max_length=200)
    result = pipe(f"<s>[INST] {prompt} [/INST]")
    print(result[0]['generated_text'])
    print("=" * 80)
    print("Testing done")
    print("=" * 80)

    # Empty VRAM
    del model
    del pipe
    del trainer
    import gc
    gc.collect()
    gc.collect()

    logger.info("Reloading original model and merging it with adapter model")
    # Reload model in FP16 and merge it with LoRA weights
    base_model = AutoModelForCausalLM.from_pretrained(
        model_path,
        low_cpu_mem_usage=True,
        return_dict=True,
        torch_dtype=torch.float16,
        device_map=device_map,
    )
    model_to_merge = PeftModel.from_pretrained(base_model, adapter_model_path)
    merged_model = model_to_merge.merge_and_unload()
    merged_model.save_pretrained(new_model_path)
    tokenizer.save_pretrained(new_model_path)
    logger.info("Saved new model to {}".format(new_model_path))

def main():
    parser = argparse.ArgumentParser(description="Fine tuning your modules")
    # Example of a flag that turns on verbose mode
    parser.add_argument('--original_model', type=str, required=True, help="Enable verbose output")
    parser.add_argument('--training_dataset', type=str, required=True, help="Enable verbose output")
    parser.add_argument('--output_model', type=str, required=True, help="Enable verbose output")
    args = parser.parse_args()

    finetuning(args)


if __name__ == "__main__":
    main()


