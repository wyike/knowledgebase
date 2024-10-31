
# Build your cuda application

### 1. Find a base image

https://hub.docker.com/r/nvidia/cuda 

- Find a base image that has cuda runtime and cuda libraries (optional) that satisfy your application requirement

    >  - base: Includes the CUDA runtime (cudart)
    >  - runtime: Builds on the base and includes the CUDA math libraries and NCC. A runtime image that also includes cuDNN is available. 
    >  - devel: Builds on the runtime and includes headers, development tools for building CUDA images. These images are particularly useful for multi-stage builds.
- It should be consistent with the nvidia driver version installed on the container host.

```
  root@nvidia-driver-daemonset-hzv96:/drivers# nvidia-smi
Thu Oct 31 09:19:04 2024
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 550.90.07              Driver Version: 550.90.07      CUDA Version: 12.4
  ```

Given above, I choose nvidia/cuda:12.4.1-runtime-ubuntu22.04


### 2. Write a Dockerfile with your app dependencies and launch script
```
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

RUN apt-get update && \
    apt install python3-pip -y --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -q accelerate==0.21.0 peft==0.4.0 bitsandbytes transformers==4.31.0 trl==0.4.7 xformers

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY ft.py /usr/src/app/ft.py

# Run the application
CMD ["python3", "ft.py"]
```

- base image: 2.29GB
- after all installations: 8.41GB

### 3. Make the image
```
docker buildx build --platform linux/amd64  -f Dockerfile -t "fine-tunning:1.2"  . --load
```
