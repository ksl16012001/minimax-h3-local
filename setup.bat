@echo off
setlocal EnableDelayedExpansion
REM ============================================================================
REM  MiniMax-H3 local video generation on consumer GPUs (stable-diffusion.cpp)
REM  setup.bat            -> DEFAULT = max: all requirements + everything (~140 GB):
REM                          Q3 + Q8 FL2VA DiTs, Q8 Ref2VA, Q2 + Q4 text encoders, VAEs,
REM                          turbo 8-step + Ref2V 4-step LoRAs, bf16 DiT for LoRA baking, torch (CUDA)
REM  setup.bat recommended-> ~28 GB: Q3 DiT + Q2 text encoder + VAEs + turbo LoRA
REM  setup.bat fast       -> ~25 GB: Q2 DiT + Q2 text encoder + VAEs
REM  setup.bat test       -> smoke test (~1.4 GB): binaries + audio VAE only
REM  Requirements: Windows 10/11, NVIDIA GPU (8 GB VRAM min, tested RTX 3070), Python 3.10+, ~32 GB RAM, ~150 GB disk.
REM  Run from the folder you want as project root (models/, bin/, outputs/ are created here).
REM ============================================================================
set "TIER=%~1"
if "%TIER%"=="" set "TIER=max"
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "SDCPP_TAG=master-845-80bac2d"
set "SDCPP_BASE=https://github.com/leejet/stable-diffusion.cpp/releases/download/%SDCPP_TAG%"
set "SDCPP_ASSET=sd-master-80bac2d-bin-win-cuda12-x64.zip"
set "CUDART_ASSET=cudart-sd-bin-win-cu12-x64.zip"
set "GGUF_REPO=unsloth/MiniMax-H3-GGUF"
set "COMFY_REPO=Comfy-Org/MiniMax-H3"

echo.
echo === MiniMax-H3 setup (tier: %TIER%) in %ROOT%
echo.

REM ---- 1. python + packages
where python >nul 2>nul || (echo [ERROR] python not found in PATH. Install Python 3.10+ and retry. & exit /b 1)
python -c "import sys; assert sys.version_info>=(3,10)" 2>nul || (echo [ERROR] Python 3.10+ required. & exit /b 1)
echo [1/4] Installing Python packages (huggingface_hub, imageio-ffmpeg, safetensors, gguf)...
python -m pip install -q -U huggingface_hub imageio-ffmpeg safetensors gguf pillow || (echo [ERROR] pip install failed & exit /b 1)
if /i "%TIER%"=="max" (
  python -c "import torch" 2>nul || (
    echo        Installing torch CUDA 12.4 ^(needed by bake_lora.py, ~2.5 GB^)...
    python -m pip install -q torch --index-url https://download.pytorch.org/whl/cu124 || (echo [ERROR] torch install failed & exit /b 1)
  )
) else (
  python -c "import torch" 2>nul || echo [NOTE] torch not installed: only needed for bake_lora.py ^(pip install torch --index-url https://download.pytorch.org/whl/cu124^).
)

REM ---- 2. folders
for %%d in (models models\vae models\loras models\diffusion_models bin outputs outputs_max inputs samples) do if not exist "%ROOT%\%%d" mkdir "%ROOT%\%%d"

REM ---- 3. stable-diffusion.cpp binaries (CUDA 12)
echo [2/4] Downloading stable-diffusion.cpp %SDCPP_TAG% (win-cuda12 + cudart)...
if not exist "%ROOT%\bin\sd-cli.exe" (
  REM a zip already in bin\ (manual/offline copy or a previous partial run) is reused instead of re-downloaded
  if not exist "%ROOT%\bin\sdcpp-cuda12.zip" curl -L --fail --retry 8 --retry-delay 5 --retry-all-errors -C - -o "%ROOT%\bin\sdcpp-cuda12.zip" "%SDCPP_BASE%/%SDCPP_ASSET%" || goto :dlfail
  if not exist "%ROOT%\bin\cudart.zip" curl -L --fail --retry 8 --retry-delay 5 --retry-all-errors -C - -o "%ROOT%\bin\cudart.zip" "%SDCPP_BASE%/%CUDART_ASSET%" || goto :dlfail
  tar -xf "%ROOT%\bin\sdcpp-cuda12.zip" -C "%ROOT%\bin" || goto :dlfail
  tar -xf "%ROOT%\bin\cudart.zip" -C "%ROOT%\bin" || goto :dlfail
  del /q "%ROOT%\bin\sdcpp-cuda12.zip" "%ROOT%\bin\cudart.zip"
) else (echo        bin\sd-cli.exe already present, skipping)
"%ROOT%\bin\sd-cli.exe" --list-devices || (echo [ERROR] sd-cli failed to start. Check NVIDIA driver / CUDA 12 support. & exit /b 1)

REM ---- 4. models
echo [3/4] Downloading models (tier: %TIER%)...
set "HF="
where hf >nul 2>nul && set "HF=hf"
if not defined HF where huggingface-cli >nul 2>nul && set "HF=huggingface-cli"
if not defined HF (echo [ERROR] hf / huggingface-cli not found after pip install. Check your PATH for Python Scripts. & exit /b 1)

if /i "%TIER%"=="test" (
  REM smoke test of this script: binaries + the small audio VAE only
  call :hfdl %GGUF_REPO% vae/minimax_h3_audio_vae_fp32.safetensors
  goto :models_done
)
REM common: VAEs
call :hfdl %GGUF_REPO% vae/minimax_h3_video_vae_fp16.safetensors vae/minimax_h3_audio_vae_fp32.safetensors

if /i "%TIER%"=="fast" (
  call :hfdl %GGUF_REPO% minimax_h3_fl2va_pruned-UD-Q2_K_XL.gguf qwen3vl_32b_minimax_h3-Q2_K_M.gguf
  goto :models_done
)
REM recommended
call :hfdl %GGUF_REPO% minimax_h3_fl2va_pruned-UD-Q3_K_XL.gguf qwen3vl_32b_minimax_h3-Q2_K_M.gguf
call :hfdl %COMFY_REPO% loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors
if /i not "%TIER%"=="max" goto :models_done
REM max (default)
call :hfdl %GGUF_REPO% minimax_h3_fl2va_pruned-Q8_0.gguf minimax_h3_ref2va_pruned-Q8_0.gguf qwen3vl_32b_minimax_h3-Q4_K_M.gguf
call :hfdl %COMFY_REPO% loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors diffusion_models/minimax_h3_fl2va_pruned_bf16.safetensors
echo        [max] To bake the turbo LoRA into a Q8_0 DiT (removes the per-job LoRA cost): powershell -File bake_chain.ps1

:models_done
echo [4/4] Done. Files:
dir /s /b "%ROOT%\models\*.gguf" "%ROOT%\models\*.safetensors" 2>nul
echo.
echo Next:
echo   .\run_t2v.ps1 -Prompt "..."                      one-shot render (sd-cli)
echo   .\start_server.ps1  then  python batch_gen.py    resident server + batch API (recommended)
echo   .\run_max.ps1 ...                                max-quality render (Q8, 768p, Ref2VA)
echo   .\story15.ps1                                    15s storyboard (3x5s, Ref2VA consistency)
echo   See NOTES.md for measured timings and VRAM limits.
exit /b 0

:hfdl
REM %1 = repo, %2.. = files
set "REPO=%~1"
shift
set "FILES="
:collect
if "%~1"=="" goto :run
set "FILES=!FILES! %1"
shift
goto :collect
:run
echo        %REPO%: !FILES!
%HF% download %REPO% !FILES! --local-dir "%ROOT%\models" || (echo [ERROR] download failed for %REPO% & exit /b 1)
exit /b 0

:dlfail
echo [ERROR] binary download/extract failed. Check internet access to github.com.
exit /b 1
