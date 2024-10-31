# A fine tuning practice

reference:
- https://towardsdatascience.com/fine-tune-your-own-llama-2-model-in-a-colab-notebook-df9823a04a32
- https://www.datacamp.com/tutorial/fine-tuning-llama-2

### 1. wrapped to a python script and packaged to container 
```
python3 ft.py --original_model /model --training_dataset /data --output_model /outputmodel 
```
[tf.py](https://github.com/wyike/knowledgerepository/blob/main/gpu/llm/ft.py)

```
apiVersion: batch/v1
kind: Job
metadata:
  name: demo-ft-job
spec:
  template:
    spec:
      volumes:
      - name: model
        hostPath:
          path: /home/yikew/model  # Replace with the local path on the node
          type: Directory
      - name: data
        hostPath:
          path: /home/yikew/data  # Replace with the local path on the node
          type: Directory
      - name: outputmodel
        hostPath:
          path: /home/yikew/outputmodel  # Replace with the local path on the node
          type: Directory
      restartPolicy: OnFailure
      containers:
      - name: ft-container
        image: fine-tunning:1.2
        command: ["python3", "ft.py"]
        args:
        - "--original_model=$(MODEL)"
        - "--training_dataset=$(DATASET)"
        - "--output_model=$(OUTPUT_MODEL)"
        env:
        - name: MODEL
          value: /model
        - name: DATASET
          value: /data
        - name: OUTPUT_MODEL
          value: /outputmodel
        volumeMounts:
        - mountPath: /model  # Path inside the container
          name: model
        - mountPath: /data  # Path inside the container
          name: data
        - mountPath: /outputmodel  # Path inside the container
          name: outputmodel
        resources:
          limits:
             nvidia.com/gpu: 1
```

### 2. run in jupyter notebook

[llama2-training.py](https://github.com/wyike/knowledgerepository/blob/main/gpu/llm/llama2-passed-16G-update.ipynb)