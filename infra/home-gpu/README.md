# Home GPU bridge — Cloudflare Tunnel + Caddy bearer auth
#
# App Runner (AWS) cannot reach Tailscale IP 100.99.15.47 directly. This folder
# runs on the GPU box and exposes vLLM (:8001) + Ollama (:11434) as public HTTPS
# hostnames that App Runner reaches via NAT.
#
# Layout on the GPU box (paul@100.99.15.47):
#
#   Internet ──HTTPS──▶ Cloudflare Tunnel ──▶ Caddy (:8787 / :8788)
#                                              ├─ / → vLLM :8001
#                                              └─ / → Ollama :11434
#   App Runner sends:  Authorization: Bearer <HOME_GPU_API_KEY>
#
# Prerequisites on the GPU box:
#   - cloudflared  (https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/)
#   - caddy        (https://caddyserver.com/docs/install)
#   - vLLM on :8001, Ollama on :11434 (already your setup)
#
# One-time Cloudflare setup (from any machine logged into Cloudflare):
#
#   cloudflared tunnel login
#   cloudflared tunnel create mymemory-gpu
#   # note the Tunnel UUID + credentials JSON path printed
#   cloudflared tunnel route dns mymemory-gpu mymemory-llm.YOURDOMAIN.com
#   cloudflared tunnel route dns mymemory-gpu mymemory-embed.YOURDOMAIN.com
#
# Then on the GPU box:
#
#   1. Copy this folder to ~/mymemory-home-gpu/
#   2. Fill config.yml (tunnel UUID + credentials-file path)
#   3. Fill Caddyfile bearer with the key from:
#        cd infra && terraform output -raw home_gpu_api_key
#      (or the value you set in terraform.tfvars as home_gpu_api_key)
#   4. Start:
#        ./run.sh
#
# Terraform (infra/terraform.tfvars):
#
#   llm_backend              = "home_gpu"
#   home_gpu_openai_base_url = "https://mymemory-llm.YOURDOMAIN.com/v1"
#   home_gpu_embed_base_url  = "https://mymemory-embed.YOURDOMAIN.com"
#   home_gpu_chat_model      = "Qwen/Qwen2.5-0.5B-Instruct"
#   home_gpu_embed_model     = "mxbai-embed-large"
#   home_gpu_embed_dim       = 1024
#   # home_gpu_api_key       = ""   # blank → Terraform generates one
#
# Verify from your Mac (should be 401 without the key, 200 with it):
#
#   curl -sS -o /dev/null -w "%{http_code}\n" \
#     https://mymemory-llm.YOURDOMAIN.com/v1/models
#   curl -sS -H "Authorization: Bearer $KEY" \
#     https://mymemory-llm.YOURDOMAIN.com/v1/models | head
#   curl -sS -H "Authorization: Bearer $KEY" \
#     -d '{"model":"mxbai-embed-large","prompt":"hi"}' \
#     https://mymemory-embed.YOURDOMAIN.com/api/embeddings | head
#
# Keep the GPU box awake; if Ollama/vLLM or cloudflared dies, prod chat fails.
