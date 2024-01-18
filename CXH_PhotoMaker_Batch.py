
from diffusers.utils import load_image
from diffusers import EulerDiscreteScheduler

from .photomaker.pipeline import PhotoMakerStableDiffusionXLPipeline

import os
import torch
import numpy as np
import folder_paths
from PIL import Image


import time

comfy_path = os.path.dirname(folder_paths.__file__)
custom_nodes_path = os.path.join(comfy_path, "custom_nodes")
photoMaker_path = os.path.join(custom_nodes_path, "Comfyui-Mine-PhotoMaker")
cache_dir = os.path.join(photoMaker_path, "modes")
save_dir = os.path.join(photoMaker_path, "images")

device = "cuda" if torch.cuda.is_available() else "cpu"

from huggingface_hub import hf_hub_download

photomaker_ckpt = hf_hub_download(repo_id="TencentARC/PhotoMaker", filename="photomaker-v1.bin", repo_type="model",cache_dir = cache_dir)
 
class CXH_PhotoMaker_Batch:
   
    def __init__(self):
        self.cur_model_path = None
        self.pipe = None
    
    @classmethod
    def INPUT_TYPES(cls):
        return {"required":
                {   
                "dir_path": ("STRING", {"default": "", "multiline": False}),
                "num_steps":("INT", {"default":50, "min": 20, "max": 100}),  
                "style_strength_ratio":("INT", {"default":20, "min": 15, "max": 50}),  
                "guidance_scale":("INT", {"default":5, "min": 0.1, "max": 10}),  
                "out_number":("INT", {"default":1, "min": 1, "max": 50}),  
                "open_save":("INT", {"default":1, "min": 0, "max": 1}),   # 0 不缓存，1缓存
                "trigger_word": ("STRING", {"default": "img","multiline": False}),
                "base_model_path": ("STRING", {"default": "SG161222/RealVisXL_V3.0","multiline": False}),             
                "positive": ("STRING", {"default": "UHD, 8K, ultra detailed, a cinematic photograph of a girl img wearing the sunglasses in Iron man suit , beautiful lighting, great composition","multiline": True}),
                "negative": ("STRING", {"default": "ugly, deformed, noisy, blurry, NSFW", "multiline": True}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 99999999}),
                "width": ("INT", {"default": 1024, "min": 512, "max": 2048}),
                "height": ("INT", {"default": 1024, "min": 512, "max": 2048}),   
                }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    OUTPUT_NODE = True
    FUNCTION = "sample"
    CATEGORY = "CXH"

    def sample(self,
                dir_path,
                num_steps,
                style_strength_ratio,
                guidance_scale,
                out_number,
                open_save,
                trigger_word,
                base_model_path,
                positive,
                negative,
                seed,
                width,
                height):
        
        if self.pipe == None or self.cur_model_path == None or self.cur_model_path != base_model_path:
            self.pipe = PhotoMakerStableDiffusionXLPipeline.from_pretrained(
                base_model_path, 
                torch_dtype=torch.bfloat16, 
                use_safetensors=True, 
                variant="fp16",
                cache_dir = cache_dir
            ).to(device)
            
            self.pipe.load_photomaker_adapter(
                os.path.dirname(photomaker_ckpt),
                subfolder="",
                weight_name=os.path.basename(photomaker_ckpt),
                trigger_word=trigger_word
            )  
            
            self.pipe.fuse_lora() 
        
        self.cur_model_path = base_model_path
        
        generator = torch.Generator(device=device).manual_seed(seed)
        
        image_basename_list = os.listdir(dir_path)
        image_path_list = [os.path.join(dir_path, basename) for basename in image_basename_list if os.path.isfile(os.path.join(dir_path, basename))]
        image_path_list = sorted(image_path_list)

        input_id_images = []
        for image_path in image_path_list:
            input_id_images.append(load_image(image_path))
    
        start_merge_step = int(float(style_strength_ratio) / 100 * num_steps)
        if start_merge_step > 30:
            start_merge_step = 30
            
        num_images = out_number
        
        images = self.pipe(
            prompt=positive,
            input_id_images=input_id_images,
            negative_prompt=negative,
            num_images_per_prompt=num_images,
            num_inference_steps=num_steps,
            start_merge_step=start_merge_step,
            generator=generator,
            guidance_scale=guidance_scale,
            width=width,
            height=height
        ).images
        
        if open_save == 1:
            # 获取当前时间
            t = time.time()  # 当前时间
            t = int(t)
            os.makedirs(save_dir, exist_ok=True)
            for idx, image in enumerate(images):
                t = t + idx
                image.save(os.path.join(save_dir, f"{t}_{idx:02d}.png"))
        
        out_images = []
        for img in images:
            out_images.append(pil2tensor(img))

        return (out_images)

     

def tensor2pil(image):
    return Image.fromarray(np.clip(255. * image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8))

# Convert PIL to Tensor
def pil2tensor(image):
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)