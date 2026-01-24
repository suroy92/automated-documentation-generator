# 🚨 QUICK FIX FOR TIMEOUT ISSUES

## ✅ What I Fixed

1. **Updated `LLM` class** (the one your code actually uses)
   - Default timeout: 120s → 300s
   - Max retries: 3 → 5
   - Exponential backoff: 10s → 20s → 40s → 80s → 160s
   - Auto-detects model size and adjusts timeout

2. **Fixed config parsing** in `main.py`
   - Now reads `timeout` from config.yaml correctly
   - Auto-adjusts for 14B models (minimum 300s)

3. **Better error messages** with actionable suggestions

## 🎯 Run It Now

```bash
# Option 1: Use config.yaml timeout (400s)
python -m src.main

# Option 2: Override with environment variable (recommended)
$env:DOCGEN_TIMEOUT=600
python -m src.main

# Option 3: Switch to faster model
# Edit config.yaml: model: qwen2.5-coder:7b
python -m src.main
```

## Expected Behavior

- **1st attempt**: 400s timeout
- **Retry 1**: Wait 10s, try again with 400s
- **Retry 2**: Wait 20s, try again with 400s
- **Retry 3**: Wait 40s, try again with 400s
- **Retry 4**: Wait 80s, try again with 400s
- **Retry 5**: Wait 160s, try again with 400s
- **Total**: ~2310s (38 minutes) max before giving up

## What Each Error Means

### "Timeout after 5 attempts"
- Model is too slow for your hardware
- **Fix**: Use `$env:DOCGEN_TIMEOUT=900` or switch to 7B model

### "Connection error"
- Ollama not running
- **Fix**: Run `ollama serve` in another terminal

### "Empty response"
- Model crashed or out of memory
- **Fix**: Check `ollama ps` and restart Ollama

## Quick Tests

```bash
# Test if timeout is picked up
python -c "from src.config_loader import ConfigLoader; c = ConfigLoader('config.yaml'); print(c.config['llm']['timeout'])"

# Test model response
ollama run qwen2.5-coder:14b "Say hello"

# Check GPU usage
ollama ps
```

## Model Recommendations for Your Hardware

| Model | Speed | Quality | Recommended Timeout |
|-------|-------|---------|---------------------|
| qwen2.5-coder:7b | Fast (15-20 tok/s) | Good | 120s |
| **qwen2.5-coder:14b** | Medium (6-8 tok/s) | Better | **400-600s** |
| deepseek-r1:8b | Fast (12-15 tok/s) | Better | 180s |
| qwen3-coder:30b | Slow (3-5 tok/s) | Best | 900s |

## If Still Failing

1. **Check Ollama status**:
   ```bash
   ollama ps  # Should show model loaded
   ```

2. **Restart Ollama with more GPU**:
   ```bash
   ollama stop qwen2.5-coder:14b
   $env:OLLAMA_NUM_GPU=40
   ollama serve
   ```

3. **Use faster model temporarily**:
   ```yaml
   # config.yaml
   llm:
     model: qwen2.5-coder:7b
     timeout: 120
   ```

4. **Environment variable override** (quickest):
   ```powershell
   $env:DOCGEN_TIMEOUT=900
   $env:DOCGEN_MODEL="qwen2.5-coder:7b"
   python -m src.main
   ```

## What Changed in Files

- ✅ [config.yaml](config.yaml): timeout: 400
- ✅ [ollama_client.py](src/providers/ollama_client.py): LLM class improved
- ✅ [main.py](src/main.py): Fixed config parsing

## Test It Now!

```bash
python -m src.main
```

If it times out again, the error message will now tell you exactly what to do.
