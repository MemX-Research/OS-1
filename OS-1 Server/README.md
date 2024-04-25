# OS-1 Server

## Prerequisites

### Software Requirements
Ensure that Python is installed on your system. You can install the required Python libraries using pip:

```bash
pip install -r requirements.txt
```

### Configurations

#### Language Model API
```shell
export OPENAI_API_KEY=sk-...
export OPENAI_API_BASE_URL="https://api.openai.com/v1"
export PROMPTLAYER_API_KEY=...
```
If you have multiple keys, you can configure them in the following file:
- `tools/openai_api.py`

#### ASR & TTS Configuration
Configure the Aliyun ASR and TTS services:
```shell
export ALI_ACCESS_KEY_ID=...
export ALI_ACCESS_KEY_SECRET=...
export ALI_APP_KEY=...

# Related files:
# - `tools/ali_asr_api.py`
# - `tools/tts_ali_nls.py`
```

#### Vision-Language Model
Set up the vision-language model by following the link provided for LLaVA:
- [LLaVA Setup Link](https://llava-vl.github.io/)

### Database Installation

Install the necessary databases using the links provided:

- MongoDB:
  ```bash
  sudo apt-get install -y mongodb
  ```

- Milvus:
  - Visit the Milvus installation guide: [Milvus Installation](https://milvus.io/docs)

## Deployment

Run the deployment script to start the server
  ```bash
  bash start.sh
  ```